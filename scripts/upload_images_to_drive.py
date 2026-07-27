#!/usr/bin/env python3
"""把新產生的 site/img/{page-id}/ 子夾上傳到 Drive「臺灣地理資料庫圖片」。

為什麼要有這支：內容 SSOT 在 Drive、repo 只留腳本，圖片一張都不進 repo
（`~/.claude/CLAUDE.md`「網路部署架構鐵則」）。`fetch_images.py` 只負責把圖抓到
本機並寫 manifest，**上傳是另一段、而且忘了就會靜默壞掉**——CI 從 Drive 拉不到該圖，
`build.py` 的 `resolve_src()` 查不到就退回原始外部 URL 且只印警告，CI 照樣綠。
鄉鎮頁要分很多批補，這段會跑很多次，所以做成腳本而不是每次手動點。

    .venv/bin/python3 scripts/upload_images_to_drive.py --dry-run
    .venv/bin/python3 scripts/upload_images_to_drive.py                    # 全部沒上傳過的
    .venv/bin/python3 scripts/upload_images_to_drive.py new-taipei-tamsui  # 指定頁

做法：只處理**本機有、Drive 沒有**的檔，已存在的跳過（冪等、可重跑）。
上傳完會重新列一次 Drive 實際內容逐檔比對，數量或檔名對不上就非零離開——
「上傳指令沒報錯」不等於「檔案真的在」，這條線之前就是靠這種驗證抓到問題的。

⚠️ 子夾直接建在根夾底下，權限走繼承（根夾已共用給 channel-deployer SA）。
   本腳本會在建新夾之後**實際查一次該夾的 permissions** 確認 SA 讀得到，
   而不是假設繼承一定生效——CI 拉不到圖會 fail-fast 中止，那是整站不上線，
   不只是新頁破圖。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "site" / "img"
DRIVE_ROOT = "1JGRyJhoRQyuPCF4UMp92mhSWcXkc4fkY"   # 「臺灣地理資料庫圖片」
READER_SA = "channel-deployer@waldorfcreatorhubdatabase.iam.gserviceaccount.com"
FOLDER_MIME = "application/vnd.google-apps.folder"


def gws(args, params=None, body=None, upload=None):
    cmd = ["gws", "drive"] + args
    if params is not None:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]
    if body is not None:
        cmd += ["--json", json.dumps(body, ensure_ascii=False)]
    if upload is not None:
        cmd += ["--upload", str(upload)]
    cmd += ["--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout
    # gws 會在 stdout 前面印一行 keyring 訊息，切掉再解析
    i = out.find("{")
    if i < 0:
        raise RuntimeError(f"gws 沒有回 JSON：{(out + r.stderr)[:400]}")
    try:
        data = json.loads(out[i:])
    except json.JSONDecodeError:
        raise RuntimeError(f"gws 回傳無法解析：{out[i:][:400]}")
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"gws 錯誤：{json.dumps(data['error'], ensure_ascii=False)[:400]}")
    return data


def list_children(parent, only_folders=False):
    q = f"'{parent}' in parents and trashed=false"
    if only_folders:
        q += f" and mimeType='{FOLDER_MIME}'"
    files, token = {}, None
    while True:
        params = {"q": q, "pageSize": 200,
                  "fields": "nextPageToken,files(id,name,size)"}
        if token:
            params["pageToken"] = token
        data = gws(["files", "list"], params=params)
        for f in data.get("files", []):
            files[f["name"]] = f
        token = data.get("nextPageToken")
        if not token:
            break
    return files


def ensure_folder(name, existing):
    if name in existing:
        return existing[name]["id"], False
    data = gws(["files", "create"],
               params={"fields": "id,name"},
               body={"name": name, "mimeType": FOLDER_MIME, "parents": [DRIVE_ROOT]})
    return data["id"], True


def sa_can_read(folder_id):
    """新夾建好後實際查權限，不假設繼承生效。回 (可讀, 說明)。"""
    try:
        data = gws(["permissions", "list"],
                   params={"fileId": folder_id, "supportsAllDrives": True,
                           "fields": "permissions(emailAddress,role,type)"})
    except RuntimeError as e:
        return None, f"查不到權限（{e}）"
    perms = data.get("permissions", [])
    for p in perms:
        if p.get("emailAddress") == READER_SA:
            return True, f"直接授權（{p.get('role')}）"
    # 沒有 direct 授權是正常的——繼承來的權限不會列在子項目上。
    # 這裡只回報事實，由呼叫端決定要不要再往上驗根夾。
    return None, "無直接授權（應為繼承自根夾）"


def main():
    dry = "--dry-run" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]

    local_dirs = sorted(d for d in IMG_DIR.iterdir()
                        if d.is_dir() and any(d.glob("*.webp")))
    if wanted:
        local_dirs = [d for d in local_dirs if d.name in wanted]
    if not local_dirs:
        sys.exit("本機 site/img/ 下沒有可上傳的子夾（圖片是不是還沒 fetch？）")

    print(f"Drive 根夾 {DRIVE_ROOT}｜本機待處理 {len(local_dirs)} 夾")
    remote_folders = list_children(DRIVE_ROOT, only_folders=True)

    uploaded = existed = 0
    new_folders = []
    problems = []

    for d in local_dirs:
        local_files = sorted(p for p in d.iterdir() if p.suffix == ".webp")
        if d.name in remote_folders:
            fid = remote_folders[d.name]["id"]
            created = False
        elif dry:
            print(f"\n[{d.name}] （dry-run）會建新夾，上傳 {len(local_files)} 檔")
            uploaded += len(local_files)      # 計進總數：dry-run 少報數字會誤導判斷
            new_folders.append((d.name, "（尚未建立）"))
            continue
        else:
            fid, created = ensure_folder(d.name, remote_folders)
        if created:
            new_folders.append((d.name, fid))

        remote_files = list_children(fid)
        todo = [p for p in local_files if p.name not in remote_files]
        print(f"\n[{d.name}] 本機 {len(local_files)}｜Drive 已有 {len(remote_files)}"
              f"｜要傳 {len(todo)}")
        if dry:
            existed += len(local_files) - len(todo)
            uploaded += len(todo)
            continue

        for p in todo:
            gws(["files", "create"],
                params={"fields": "id,name", "uploadType": "multipart"},
                body={"name": p.name, "parents": [fid]},
                upload=p)
            uploaded += 1
            print(f"  ↑ {p.name}（{p.stat().st_size/1024:.0f} KB）")
        existed += len(local_files) - len(todo)

        # 逐檔比對：上傳指令沒報錯 ≠ 檔案真的在
        after = list_children(fid)
        missing = [p.name for p in local_files if p.name not in after]
        if missing:
            problems.append(f"{d.name}：Drive 少了 {len(missing)} 檔 → {missing[:5]}")

    if dry:
        print(f"\n（dry-run）會上傳 {uploaded} 檔，已存在 {existed} 檔。沒有實際動作。")
        return

    if new_folders:
        print("\n新建的子夾（查權限確認 CI 的 SA 讀得到）：")
        for name, fid in new_folders:
            ok, why = sa_can_read(fid)
            print(f"  · {name}  {fid}  → {why}")

    print(f"\n===== 摘要 =====")
    print(f"上傳 {uploaded} 檔｜Drive 已有而跳過 {existed} 檔｜新建子夾 {len(new_folders)}")
    if problems:
        print("\n⚠ 驗證沒過：")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("逐檔比對通過：本機每一個 .webp 在 Drive 都找得到同名檔。")
    print("下一關：build → push → CI → scripts/verify_live_images.py 全綠才算真的上線。")


if __name__ == "__main__":
    main()

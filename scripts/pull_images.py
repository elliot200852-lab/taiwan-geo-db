#!/usr/bin/env python3
"""從 Google Drive 拉取站台圖片到 site/img/（增量：只下載 Drive 上有變的檔）。

內容 SSOT 在 Drive、repo 只留腳本（~/.claude/CLAUDE.md「網路部署架構鐵則」）。
對照 drive-manifest.yaml 的 <本機相對路徑>: <Drive folder ID> 逐夾遞迴下載。

用 Python 而非照抄 creator-hub 的 pull-app-drive.js（Node）：本 repo 是純 Python、
CI 已有 setup-python，且避開 node-fetch 誤判 socket "Premature close" 那類
Node 版本坑（見 david-showcase deploy.yml 的 node-version 釘版註解）。

增量快取（2026-10-27 起）：
  以前每次部署都把 ~2,000 張、300 多 MB 從頭一張一張下載，build 與 verify 兩個 job
  各拉一次，一次部署約一小時，其中 build.py 本身只要 3 秒。現在：
  - 下載的檔先放 .drive-cache/<本機相對路徑>/，旁邊的 state.json 記每個檔的 Drive md5；
    CI 用 actions/cache 把 .drive-cache 帶到下一次部署。
  - 每次仍完整列一遍 Drive（平行列夾），md5 跟 state.json 一樣而且快取裡有檔就沿用，
    不一樣或新檔才下載；Drive 上已刪的檔從快取移除。
  - 最後把 Drive 上現有的檔從快取複製到目的地。
  快取放在 site/ 外面，是因為 site/img/manifest.json 在 repo 裡，直接快取 site/img
  會在還原時用舊版蓋掉它。本機跑也會建 .drive-cache（約 300 MB、已 gitignore），隨時可刪。

認證：
  CI   → 環境變數 GOOGLE_SERVICE_ACCOUNT_KEY（單行 SA key JSON）
  本機 → GOOGLE_APPLICATION_CREDENTIALS（key 檔路徑）

⚠ 兩道 fail-fast 刻意保留，不要拿掉（照 2026-07-14 植物誌 handoff）：
  1. Drive 資料夾列到 0 檔 → 中止建置，以免空頁／破圖上線
  2. 在 GitHub Actions 上卻沒有憑證 → 中止；只有本機允許 skip
build.py 只讀 manifest.json、不 stat 實體檔，缺圖時會 silently 退回原始外部 URL，
所以 build 綠不代表圖在——這兩道閘是唯一擋得住破圖上線的地方。
"""
import concurrent.futures as cf
import hashlib
import io
import json
import os
import pathlib
import random
import shutil
import sys
import threading
import time

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build as build_service
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "drive-manifest.yaml"
CACHE = ROOT / ".drive-cache"
STATE = CACHE / "state.json"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
# 同時連 Drive 的條數。429 有 with_retry 退避接住，不必再往上加。
WORKERS = 8

TRANSIENT = ("Premature close", "ECONNRESET", "ETIMEDOUT", "socket hang up",
             "500", "502", "503", "504", "429", "rateLimitExceeded",
             "userRateLimitExceeded", "backendError", "internalError",
             "md5 不符")


def is_transient(exc):
    if isinstance(exc, HttpError) and exc.resp.status in (429, 500, 502, 503, 504):
        return True
    return any(t.lower() in str(exc).lower() for t in TRANSIENT)


def with_retry(fn, what, attempts=6):
    """指數退避：1s→2s→4s→8s→16s（cap 20s）。權限／404 直接拋，不重試。"""
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            if i == attempts - 1 or not is_transient(e):
                raise
            delay = min(2 ** i, 20) + random.uniform(0, 0.5)
            print(f"  ! {what} 第 {i+1} 次失敗（{str(e)[:100]}），{delay:.1f}s 後重試",
                  flush=True)
            time.sleep(delay)


def load_credentials():
    raw = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY") or "").strip()
    if raw.startswith("{"):
        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=SCOPES)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path and pathlib.Path(path).exists():
        return service_account.Credentials.from_service_account_file(
            path, scopes=SCOPES)
    return None


def service_factory(creds):
    """每條 thread 各建一個 Drive service：底層 httplib2 不是 thread-safe。"""
    local = threading.local()

    def get():
        if not hasattr(local, "svc"):
            local.svc = build_service("drive", "v3", credentials=creds,
                                      cache_discovery=False)
        return local.svc
    return get


def list_children(svc, folder_id):
    out, token = [], None
    while True:
        def _call():
            return svc.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, size, md5Checksum, modifiedTime)",
                pageSize=1000, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()

        resp = with_retry(_call, f"list {folder_id}")
        out.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return out


def list_tree(get_svc, root_id, pool):
    """一層一層平行列夾。回傳 {夾內相對路徑: Drive 檔案 dict}。"""
    files = {}
    level = [(root_id, "")]
    while level:
        listed = pool.map(lambda f: list_children(get_svc(), f[0]), level)
        nxt = []
        for (_, prefix), children in zip(level, listed):
            for item in children:
                rel = prefix + item["name"]
                if item["mimeType"] == FOLDER_MIME:
                    nxt.append((item["id"], rel + "/"))
                    continue
                if rel in files:
                    print(f"  ⚠ Drive 上有同名檔 {rel}，以後列到的為準", flush=True)
                files[rel] = item
        level = nxt
    return files


def fingerprint(item):
    """判斷「Drive 上這個檔變了沒」的依據。webp 一定有 md5；沒有就退回大小＋修改時間。"""
    return item.get("md5Checksum") or f"{item.get('size')}@{item.get('modifiedTime')}"


def download_file(svc, item, dest):
    def _call():
        buf = io.BytesIO()
        req = svc.files().get_media(fileId=item["id"], supportsAllDrives=True)
        dl = MediaIoBaseDownload(buf, req, chunksize=5 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
        data = buf.getvalue()
        want = item.get("md5Checksum")
        if want and hashlib.md5(data).hexdigest() != want:
            raise IOError(f"md5 不符（下載不完整）：{dest.name}")
        return data

    data = with_retry(_call, f"download {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return len(data)


def sync_folder(get_svc, pool, rel, folder_id, state):
    """把 Drive 夾同步到 .drive-cache/<rel>，再複製到 ROOT/<rel>。

    不刪目的地既有檔——site/img/manifest.json 是 build.py 的輸入、住在同一夾但
    SSOT 在 repo，清空會把它一起掃掉。Drive 上已刪的檔只從快取移除。"""
    remote = list_tree(get_svc, folder_id, pool)
    # fail-fast #1：列到 0 檔＝夾空了或 SA 權限掉了，中止以免破圖上線
    if not remote:
        print(f"✗ {rel} 在 Drive 上列到 0 檔——中止建置以免破圖上線。"
              f"檢查夾 {folder_id} 是否還共用給該 SA。", file=sys.stderr)
        sys.exit(1)

    mirror = CACHE / rel
    known = state.get(rel, {})
    todo = [p for p, item in remote.items()
            if known.get(p) != fingerprint(item) or not (mirror / p).is_file()]
    stale = [p for p in known if p not in remote]

    got = 0
    futures = [pool.submit(lambda p: download_file(get_svc(), remote[p], mirror / p), p)
               for p in todo]
    for i, fut in enumerate(cf.as_completed(futures), 1):
        got += fut.result()
        if i % 50 == 0:
            print(f"  … 已下載 {i}/{len(todo)} 檔", flush=True)
    for p in stale:
        (mirror / p).unlink(missing_ok=True)

    dest = ROOT / rel
    for p in remote:
        (dest / p).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mirror / p, dest / p)

    state[rel] = {p: fingerprint(item) for p, item in sorted(remote.items())}
    print(f"✓ {rel}：Drive 上 {len(remote)} 檔｜新下載 {len(todo)} 檔 / "
          f"{got/1048576:.1f} MB｜沿用快取 {len(remote) - len(todo)} 檔｜"
          f"快取移除 {len(stale)} 檔", flush=True)
    return len(remote)


def main():
    creds = load_credentials()
    if creds is None:
        # fail-fast #2：CI 上沒憑證＝設定壞了，絕不讓它靜靜產出破圖站
        if os.environ.get("GITHUB_ACTIONS"):
            print("✗ CI 上找不到 GOOGLE_SERVICE_ACCOUNT_KEY，中止建置。",
                  file=sys.stderr)
            sys.exit(1)
        print("⚠ 本機無 Drive 憑證，略過拉取（沿用既有 site/img/）。")
        return

    spec = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    get_svc = service_factory(creds)

    grand = 0
    with cf.ThreadPoolExecutor(WORKERS) as pool:
        for rel, folder_id in (spec.get("files") or {}).items():
            print(f"→ 同步 {rel}（Drive {folder_id}）", flush=True)
            grand += sync_folder(get_svc, pool, rel, folder_id, state)

    # 全部成功才寫 state：中途失敗的話下次會把沒記到的檔重抓一次，不會誤用半成品。
    # sort_keys 讓內容相同時檔案也相同——CI 拿它的雜湊當快取 key。
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True),
                     encoding="utf-8")
    print(f"完成：共 {grand} 檔")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""從 Google Drive 拉取站台圖片到 site/img/。

內容 SSOT 在 Drive、repo 只留腳本（~/.claude/CLAUDE.md「網路部署架構鐵則」）。
對照 drive-manifest.yaml 的 <本機相對路徑>: <Drive folder ID> 逐夾遞迴下載。

用 Python 而非照抄 creator-hub 的 pull-app-drive.js（Node）：本 repo 是純 Python、
CI 已有 setup-python，且避開 node-fetch 誤判 socket "Premature close" 那類
Node 版本坑（見 david-showcase deploy.yml 的 node-version 釘版註解）。

認證：
  CI   → 環境變數 GOOGLE_SERVICE_ACCOUNT_KEY（單行 SA key JSON）
  本機 → GOOGLE_APPLICATION_CREDENTIALS（key 檔路徑）

⚠ 兩道 fail-fast 刻意保留，不要拿掉（照 2026-07-14 植物誌 handoff）：
  1. 資料夾拉到 0 檔 → 中止建置，以免空頁／破圖上線
  2. 在 GitHub Actions 上卻沒有憑證 → 中止；只有本機允許 skip
build.py 只讀 manifest.json、不 stat 實體檔，缺圖時會 silently 退回原始外部 URL，
所以 build 綠不代表圖在——這兩道閘是唯一擋得住破圖上線的地方。
"""
import io
import json
import os
import pathlib
import random
import sys
import time

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build as build_service
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "drive-manifest.yaml"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

TRANSIENT = ("Premature close", "ECONNRESET", "ETIMEDOUT", "socket hang up",
             "500", "502", "503", "504", "429", "rateLimitExceeded",
             "userRateLimitExceeded", "backendError", "internalError")


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


def list_children(svc, folder_id):
    out, token = [], None
    while True:
        def _call():
            return svc.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageSize=100, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()

        resp = with_retry(_call, f"list {folder_id}")
        out.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return out


def download_file(svc, file_id, dest):
    def _call():
        buf = io.BytesIO()
        req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        dl = MediaIoBaseDownload(buf, req, chunksize=5 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
        return buf.getvalue()

    data = with_retry(_call, f"download {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def pull_folder(svc, folder_id, dest_dir):
    """遞迴下載。回傳 (檔數, 總 bytes)。不刪目的地既有檔——site/img/manifest.json
    是 build.py 的輸入、住在同一夾但 SSOT 在 repo，清空會把它一起掃掉。"""
    n, total = 0, 0
    for item in list_children(svc, folder_id):
        target = dest_dir / item["name"]
        if item["mimeType"] == FOLDER_MIME:
            sub_n, sub_b = pull_folder(svc, item["id"], target)
            n += sub_n
            total += sub_b
        else:
            total += download_file(svc, item["id"], target)
            n += 1
            if n % 50 == 0:
                print(f"  … {n} 檔", flush=True)
    return n, total


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
    svc = build_service("drive", "v3", credentials=creds, cache_discovery=False)

    grand = 0
    for rel, folder_id in (spec.get("files") or {}).items():
        dest = ROOT / rel
        print(f"→ 拉取 {rel}（Drive {folder_id}）", flush=True)
        n, total = pull_folder(svc, folder_id, dest)
        # fail-fast #1：拉到 0 檔＝夾空了或 SA 權限掉了，中止以免破圖上線
        if n == 0:
            print(f"✗ {rel} 從 Drive 拉到 0 檔——中止建置以免破圖上線。"
                  f"檢查夾 {folder_id} 是否還共用給該 SA。", file=sys.stderr)
            sys.exit(1)
        print(f"✓ {rel}：{n} 檔 / {total/1048576:.1f} MB", flush=True)
        grand += n
    print(f"完成：共 {grand} 檔")


if __name__ == "__main__":
    main()

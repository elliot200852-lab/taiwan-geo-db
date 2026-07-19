#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料來源標題抓取器 — 為 content/**/*.md frontmatter 的裸 `sources:` URL 清單
批次抓取網頁 <title>，寫出 scripts/source-titles.yaml（URL -> 中文標題對照）。

母本零改動：content/**/*.md 只讀不寫。source-titles.yaml 屬 build 輸入，
與 site/img/manifest.json 同性質（build.py 讀取、缺檔或缺項一律 fallback 裸 URL）。

用法：
    .venv/bin/python3 scripts/fetch_source_titles.py

行為：
  - 掃 content/**/*.md，收集 frontmatter `sources:` 的所有 URL（去重）。
  - 併發抓取（<=4 併發、同一 host 序列化＋節流間隔，避免打爆單一站台）。
  - 每個 URL 最多重試 2 次（共 3 次嘗試）、timeout 15s。
  - 標題清理：HTML entity 解碼、收合空白、砍常見尾綴（維基百科全稱→簡稱等）。
  - 失敗（非 200／無 <title>／標題為空／亂碼／疑似人機驗證頁）的 URL 不寫入
    正式對照表，改列在檔尾註解區，並在終端機印出清單供人工複查。
  - 已存在於 source-titles.yaml 且仍在最新 URL 集合內的成功項目，重跑時保留
    （避免每次重抓全部、也讓人工補洞不會被下一次批次抓取蓋掉——除非該 URL
    這次抓到了新標題，以新結果為準；人工補洞請直接編輯 source-titles.yaml，
    重跑本腳本只會覆蓋「這次有抓到」的 URL，其餘保留原值）。
  - curl 安全 fallback：不少台灣 .gov.tw／機關站的憑證缺 Subject Key Identifier
    擴充欄位，Python 3.14 綁定的新版 OpenSSL 對這類憑證的鏈驗證過嚴，直接判定
    SSLError；同一憑證用系統 curl（macOS 走 SecureTransport／系統信任鏈）可以
    正常完整驗證通過（非 MITM，純屬 TLS 實作差異，已人工核對）。requests 遇到
    SSLError 時改呼叫系統 `curl`（**一律不加 -k/--insecure，完整憑證驗證**）
    重抓一次；curl 也失敗（憑證真的有問題／逾時／其他錯誤）就照一般失敗處理。
"""
import html
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
OUT_YAML = ROOT / "scripts" / "source-titles.yaml"

MAX_WORKERS = 4
MIN_HOST_INTERVAL = 0.6  # 同一 host 兩次請求間至少間隔（秒）
TIMEOUT = 15
ATTEMPTS = 3  # 含首次，共重試 2 次
MAX_BYTES = 300_000  # 找不到 </title> 時的下載上限，避免整頁抓光

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 疑似人機驗證／擋爬蟲頁的標題關鍵字，出現就視為失敗（不是真標題）
BLOCKED_TITLE_MARKERS = (
    "just a moment", "attention required", "cloudflare",
    "406 not acceptable", "存取被拒", "access denied", "驗證您是否為真人",
    "are you a robot", "未授權", "forbidden",
)

# 標題尾綴清理規則：(比對 regex, 取代字串)
SUFFIX_RULES = [
    (re.compile(r"\s*[-－–—]\s*維基百科，自由的百科全書\s*$"), " - 維基百科"),
    (re.compile(r"\s*[-－–—]\s*Wikipedia\s*$", re.I), " - Wikipedia"),
]

HOST_LOCKS = {}
HOST_LAST = {}
REGISTRY_LOCK = threading.Lock()

SESSION = requests.Session()


# ---- 收集 URL ----
def collect_urls():
    urls = set()
    md_files = sorted(CONTENT.rglob("*.md")) if CONTENT.exists() else []
    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        for s in (fm.get("sources") or []):
            s = (s or "").strip()
            if s.startswith("http://") or s.startswith("https://"):
                urls.add(s)
    return sorted(urls)


# ---- 抓取單一 URL ----
def decode_html_bytes(content, content_type_header):
    charset = None
    if content_type_header:
        m = re.search(r"charset=([\w-]+)", content_type_header, re.I)
        if m:
            charset = m.group(1)
    if not charset:
        head = content[:2048]
        m = re.search(rb'charset=["\']?([\w-]+)', head, re.I)
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    for cs in ([charset] if charset else []) + ["utf-8"]:
        try:
            return content.decode(cs, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


def clean_title(url, raw_title):
    title = html.unescape(raw_title)
    title = re.sub(r"\s+", " ", title).strip()
    for pattern, repl in SUFFIX_RULES:
        title = pattern.sub(repl, title)
    return title.strip()


def is_garbled(title):
    if "�" in title:
        return True
    bad = sum(1 for ch in title if ord(ch) < 0x20 and ch not in "\t")
    return bad > 0


def is_blocked_page(title):
    low = title.lower()
    return any(marker in low for marker in BLOCKED_TITLE_MARKERS)


def title_from_bytes(url, content, content_type_header):
    """共用：從已下載的 bytes 萃取＋清理標題（requests 路徑與 curl fallback 都用這個）。"""
    html_text = decode_html_bytes(content, content_type_header)
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.I | re.S)
    if not m:
        return None, "無 <title> 標籤（可能被截斷或非 HTML）"
    title = clean_title(url, m.group(1))
    if not title:
        return None, "標題為空"
    if is_garbled(title):
        return None, "標題疑似亂碼"
    if is_blocked_page(title):
        return None, f"疑似人機驗證/擋爬蟲頁：{title[:60]}"
    return title, None


def fetch_via_curl(url):
    """安全 TLS fallback：requests（Python 3.14 綁定的 OpenSSL）對缺 SKI 擴充欄位的
    憑證驗證過嚴時，改叫系統 curl 重抓一次。curl 走系統信任鏈（macOS 是
    SecureTransport）獨立驗證，**一律不加 -k/--insecure**——完整驗證憑證鏈與主機名，
    只是驗證實作跟 Python 不同，不是關掉驗證。只有在 requests 丟 SSLError 時才會
    呼叫；curl 本身也失敗（憑證真有問題／逾時／其他網路錯誤）一樣算抓取失敗。"""
    with tempfile.TemporaryDirectory() as td:
        body_path = os.path.join(td, "body")
        header_path = os.path.join(td, "headers")
        cmd = [
            "curl", "-sS", "--max-time", str(TIMEOUT), "-L",
            "-A", HEADERS["User-Agent"],
            "-H", f"Accept-Language: {HEADERS['Accept-Language']}",
            "-H", f"Accept: {HEADERS['Accept']}",
            "-D", header_path,
            "-o", body_path,
            url,
        ]
        try:
            proc = subprocess.run(cmd, timeout=TIMEOUT + 10,
                                   capture_output=True)
        except subprocess.TimeoutExpired:
            return None, "curl fallback 逾時"
        except FileNotFoundError:
            return None, "curl fallback：系統無 curl 可用"
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "ignore").strip()[:150]
            return None, f"curl fallback 失敗（exit {proc.returncode}）：{stderr}"

        header_text = ""
        if os.path.exists(header_path):
            header_text = Path(header_path).read_text(encoding="utf-8", errors="ignore")
        status_lines = re.findall(r"^HTTP/\S+\s+(\d+)", header_text, re.M)
        status = int(status_lines[-1]) if status_lines else None
        if status != 200:
            return None, f"curl fallback HTTP {status}"

        content_type = ""
        m = re.search(r"^Content-Type:\s*(.+?)\s*$", header_text, re.M | re.I)
        if m:
            content_type = m.group(1)

        if not os.path.exists(body_path):
            return None, "curl fallback：無回應內容"
        with open(body_path, "rb") as f:
            content = f.read(MAX_BYTES + 8192)

        return title_from_bytes(url, content, content_type)


def fetch_title_once(url):
    """單次抓取。憑證驗證預設走 requests 全套 CA＋主機名驗證；requests 因憑證問題
    丟 SSLError 時才轉呼叫 fetch_via_curl()（同樣完整驗證、不降級），其餘錯誤原樣
    處理，不做任何關閉驗證的嘗試。"""
    try:
        resp = SESSION.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True,
                            allow_redirects=True)
    except requests.exceptions.SSLError:
        return fetch_via_curl(url)
    try:
        content = b""
        for chunk in resp.iter_content(8192):
            if chunk:
                content += chunk
            if b"</title>" in content.lower() or len(content) > MAX_BYTES:
                break
        status = resp.status_code
        if status != 200:
            return None, f"HTTP {status}"
        return title_from_bytes(url, content, resp.headers.get("Content-Type", ""))
    finally:
        resp.close()


def fetch_title_with_retry(url):
    last_err = None
    for i in range(ATTEMPTS):
        try:
            title, err = fetch_title_once(url)
            if title:
                return title, None
            last_err = err
        except requests.RequestException as e:
            last_err = str(e)[:150]
        if i < ATTEMPTS - 1:
            time.sleep(1.5 * (i + 1))
    return None, last_err


def throttled_fetch(url):
    host = urlparse(url).netloc
    with REGISTRY_LOCK:
        lock = HOST_LOCKS.setdefault(host, threading.Lock())
    with lock:
        last = HOST_LAST.get(host, 0.0)
        wait = MIN_HOST_INTERVAL - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        try:
            return fetch_title_with_retry(url)
        finally:
            HOST_LAST[host] = time.monotonic()


def main():
    force_all = "--all" in sys.argv

    urls = collect_urls()
    total = len(urls)
    print(f"收集到 {total} 條去重 URL（來自 content/**/*.md frontmatter sources）")
    if total == 0:
        print("沒有任何來源 URL，結束。")
        return

    # 保留既有人工補洞／舊抓取成功值：只有「這次抓到新值」才覆蓋
    existing = {}
    if OUT_YAML.exists():
        try:
            loaded = yaml.safe_load(OUT_YAML.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                existing = {k: v for k, v in loaded.items() if isinstance(v, str) and v.strip()}
        except Exception as e:
            print(f"  ! 讀既有 source-titles.yaml 失敗，視為空白重建：{e}")

    # 預設只抓「還沒有標題」的 URL（新增或上次失敗的）；--all 才全部重抓。
    # 已成功的 URL 不會被重新請求，人工補洞也因此絕不會被自動抓取蓋掉。
    todo = urls if force_all else [u for u in urls if u not in existing]
    skipped = total - len(todo)
    if skipped:
        print(f"已有標題略過 {skipped} 條（用 --all 強制全部重抓），本次實際抓取 {len(todo)} 條")

    results = dict(existing)  # url -> title
    failed = {}  # url -> reason
    done = 0
    todo_total = len(todo)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(throttled_fetch, u): u for u in todo}
        for fut in as_completed(futs):
            url = futs[fut]
            done += 1
            try:
                title, err = fut.result()
            except Exception as e:
                title, err = None, f"未預期例外：{e}"
            if title:
                results[url] = title
            else:
                # 抓失敗：若先前有人工補洞／舊抓取成功值仍保留在 results 裡（不清空）
                failed[url] = err or "未知錯誤"
            if done % 10 == 0 or done == todo_total:
                print(f"  進度 {done}/{todo_total}（成功 {len(results)}、失敗 {len(failed)}）", flush=True)

    # 只保留仍在最新 URL 集合內的項目（URL 被移除就跟著清掉，避免對照表無限增長）
    url_set = set(urls)
    results = {u: t for u, t in results.items() if u in url_set}

    ok_count = len(results)
    fail_list = sorted(u for u in urls if u not in results)

    lines = []
    lines.append("# 資料來源標題對照表（URL -> 中文標題）")
    lines.append("# 由 scripts/fetch_source_titles.py 產生，build.py 讀取後渲染成")
    lines.append("# 「標題 (host)」連結；查無標題的 URL 一律 fallback 裸連結。")
    lines.append("# 母本 content/**/*.md 不記標題——這裡是唯一 SSOT。")
    lines.append("# 人工補洞：直接在下方加一行 `url: 標題`；重跑本腳本不會清掉人工值，")
    lines.append("# 除非該 URL 這次重新抓到了新標題（以新抓到的為準）。")
    lines.append("")
    dumped = yaml.dump(results, allow_unicode=True, default_flow_style=False,
                        sort_keys=True, width=100)
    lines.append(dumped.rstrip("\n"))
    lines.append("")
    lines.append("# ---- 以下為抓取失敗／查無標題，維持裸 URL fallback（人工複查用）----")
    if fail_list:
        for u in fail_list:
            reason = failed.get(u, "（此 URL 之前也沒有標題，本次未重試或未涵蓋）")
            # 錯誤訊息（尤其 curl stderr）可能夾帶換行，寫進註解前一律壓成單行，
            # 否則沒有 "#" 開頭的殘段會被 YAML 當成真的 mapping key 解析進 data
            # （曾經出過這個坑：curl 的 "More details here: ..." 續行混進成功表）。
            reason = re.sub(r"\s+", " ", reason).strip()
            lines.append(f"# {u}")
            lines.append(f"#   原因：{reason}")
    else:
        lines.append("# （無）")
    lines.append("")

    OUT_YAML.write_text("\n".join(lines), encoding="utf-8")

    print(f"完成：{total} 條 URL，成功 {ok_count} 條，失敗/待補 {len(fail_list)} 條")
    print(f"寫出 {OUT_YAML.relative_to(ROOT)}")
    if fail_list:
        print("失敗清單：")
        for u in fail_list:
            print(f"  - {u}  ({failed.get(u, '?')})")


if __name__ == "__main__":
    main()

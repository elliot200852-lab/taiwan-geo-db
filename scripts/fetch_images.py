#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
認識臺灣地理資料庫 — 圖片自包含化（WebP 落地）

掃 content/{county}/{unit}.md frontmatter 的 images 清單，逐張下載原圖，
用 sips 縮到最長邊 1200px、cwebp 品質 78 轉檔，存成
    site/img/{page-id}/{兩位序號}.webp
並維護 site/img/manifest.json（原始 URL -> 本地相對路徑，相對 site/ 根）。

特性：
  - 增量可重跑：已存在的 .webp 直接跳過（仍補寫 manifest）
  - 下載帶固定 UA、每張間隔 1.5 秒、429 指數退避重試（最多 4 次）
  - 單張失敗不中斷整批，最後列出失敗清單

⚠ 只在本機（macOS）跑；CI 不跑此腳本（圖片已入 repo）。
依賴：sips（系統內建）、/opt/homebrew/bin/cwebp、PyYAML。
"""
import sys, os, re, json, time, subprocess, tempfile
import urllib.request, urllib.error
from pathlib import Path

try:
    import yaml
except ImportError as e:
    sys.exit(f"缺少依賴：{e.name}。請先 `pip install -r requirements.txt`")

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
IMG_DIR = ROOT / "site" / "img"
MANIFEST = IMG_DIR / "manifest.json"

UA = "TeacherOS-geo-db/1.0 (educational; contact: elliot200852@gmail.com)"
CWEBP = "/opt/homebrew/bin/cwebp"
SIPS = "/usr/bin/sips"
MAX_EDGE = 1200
QUALITY = 78
DELAY = 1.5          # 每張下載間隔（秒）
MAX_RETRY = 4        # 429 指數退避重試上限


def load_manifest():
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_manifest(m):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2,
                                   sort_keys=True), encoding="utf-8")


def parse_frontmatter(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def download(url):
    """下載，回傳 bytes；429 指數退避，其他錯誤直接拋。"""
    backoff = 2.0
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < MAX_RETRY:
                wait = backoff ** attempt
                print(f"    · 429，第 {attempt} 次退避 {wait:.0f}s")
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            last_err = e
            raise
    raise last_err


def to_webp(raw_bytes, out_path, url):
    """原始 bytes -> sips 縮圖 -> cwebp。回傳 True/False。"""
    suffix = os.path.splitext(url.split("?")[0])[1] or ".img"
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "src" + suffix)
        resized = os.path.join(td, "resized.png")
        with open(src, "wb") as f:
            f.write(raw_bytes)
        # sips：縮到最長邊 <= MAX_EDGE，同時統一成 PNG（可吞 gif/jpg/png）
        r = subprocess.run(
            [SIPS, "-Z", str(MAX_EDGE), "-s", "format", "png", src,
             "--out", resized],
            capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(resized):
            print(f"    ! sips 失敗：{r.stderr.strip()[:200]}")
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [CWEBP, "-quiet", "-q", str(QUALITY), resized, "-o", str(out_path)],
            capture_output=True, text=True)
        if r.returncode != 0 or not out_path.exists():
            print(f"    ! cwebp 失敗：{r.stderr.strip()[:200]}")
            return False
        return True


def main():
    if not CWEBP or not os.path.exists(CWEBP):
        sys.exit(f"找不到 cwebp：{CWEBP}（brew install webp）")
    manifest = load_manifest()
    md_files = sorted(CONTENT.rglob("*.md")) if CONTENT.exists() else []

    total = skipped = fetched = 0
    failures = []

    for path in md_files:
        fm = parse_frontmatter(path)
        pid = fm.get("id")
        images = fm.get("images") or []
        if not pid or not images:
            continue
        print(f"[{pid}] {len(images)} 張")
        for idx, img in enumerate(images):
            url = (img.get("url") or "").strip()
            if not url:
                continue
            total += 1
            rel = f"img/{pid}/{idx:02d}.webp"
            out_path = IMG_DIR / pid / f"{idx:02d}.webp"
            if out_path.exists():
                manifest[url] = rel          # 補寫 manifest（可重跑）
                skipped += 1
                continue
            print(f"  ↓ {idx:02d} {url[:80]}")
            try:
                raw = download(url)
            except Exception as e:
                print(f"    ! 下載失敗：{e}")
                failures.append((pid, idx, url, f"download: {e}"))
                time.sleep(DELAY)
                continue
            ok = to_webp(raw, out_path, url)
            if ok:
                manifest[url] = rel
                fetched += 1
                kb = out_path.stat().st_size / 1024
                print(f"    ✓ {rel}（{kb:.0f} KB）")
            else:
                failures.append((pid, idx, url, "convert"))
            time.sleep(DELAY)

    save_manifest(manifest)

    print("\n===== 摘要 =====")
    print(f"總圖數 {total}｜新下載 {fetched}｜已存在跳過 {skipped}｜失敗 {len(failures)}")
    print(f"manifest：{MANIFEST.relative_to(ROOT)}（{len(manifest)} 筆）")
    if failures:
        print("\n失敗清單：")
        for pid, idx, url, why in failures:
            print(f"  - [{pid}] #{idx:02d} {why}  {url}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""逐圖驗證 live 站的圖片都真的在（Drive-pull 遷移的驗收閘）。

為什麼需要這支：build.py 只讀 site/img/manifest.json、不 stat 實體檔；manifest 缺項時
resolve_src() 只印警告就退回原始外部 URL。所以「CI 綠」「頁面產出」都不代表圖在——
唯一能證明遷移成功的是對 live 站逐張抓。這支全綠才准 git rm 本機／repo 的圖。

用法：
  python scripts/verify_live_images.py                      # 驗 live，對照本機 site/img
  python scripts/verify_live_images.py --base <url>          # 換站台
  python scripts/verify_live_images.py --no-size             # 只驗 200＋mime，不比大小
"""
import argparse
import concurrent.futures as cf
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = ROOT / "site" / "pages"
INDEX_HTML = ROOT / "site" / "index.html"
IMG = ROOT / "site" / "img"
DEFAULT_BASE = "https://elliot200852-lab.github.io/taiwan-geo-db"

# 子頁（site/pages/*.html）在 pages/ 目錄下一層，img src 帶 "../" 前綴。
IMG_SRC_SUB = re.compile(r'<img[^>]+src="\.\./(img/[^"]+)"')
# 首頁（site/index.html）在站根，img src 沒有 "../" 前綴（例：site-hero.webp）。
IMG_SRC_ROOT = re.compile(r'<img[^>]+src="(img/[^"]+)"')


def collect_refs():
    """從產出的 HTML 收集實際引用的圖片相對路徑（去重）。
    不直接列 site/img/：fetch_images 的共用圖機制會讓實體檔多於引用
    （曾有孤兒檔 theme-rivers/02.webp），以 HTML 實際引用為準才是使用者會看到的。
    2026-07-20 補洞：site/index.html（首頁 site-hero.webp）先前完全沒被掃到——
    子頁 img src 帶 "../" 前綴、首頁在站根沒有該前綴，兩種路徑都要收。"""
    refs = set()
    for p in sorted(PAGES.glob("*.html")):
        for m in IMG_SRC_SUB.finditer(p.read_text(encoding="utf-8")):
            refs.add(m.group(1))
    if INDEX_HTML.exists():
        for m in IMG_SRC_ROOT.finditer(INDEX_HTML.read_text(encoding="utf-8")):
            refs.add(m.group(1))
    return sorted(refs)


def check(base, rel, want_size):
    url = f"{base}/{rel}"
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "taiwan-geo-db-verify/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type", "")
            if r.status != 200:
                return rel, f"HTTP {r.status}"
            if "image/webp" not in ctype:
                return rel, f"content-type={ctype!r}（非 webp，可能是 404 頁）"
            if want_size is not None and len(body) != want_size:
                return rel, f"大小不符 live={len(body)} 本機={want_size}"
            return rel, None
    except Exception as e:
        return rel, f"{type(e).__name__}: {str(e)[:80]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--no-size", action="store_true")
    args = ap.parse_args()

    refs = collect_refs()
    if not refs:
        print("✗ 從 site/pages/*.html 收不到任何 img 引用——先跑 build.py", file=sys.stderr)
        sys.exit(1)
    print(f"HTML 實際引用 {len(refs)} 張圖，開始驗 {args.base}", flush=True)

    sizes = {}
    if not args.no_size:
        for rel in refs:
            f = ROOT / "site" / rel
            sizes[rel] = f.stat().st_size if f.exists() else None

    bad = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(check, args.base.rstrip("/"), rel, sizes.get(rel))
                for rel in refs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            rel, err = fut.result()
            if err:
                bad.append((rel, err))
            if i % 50 == 0:
                print(f"  … {i}/{len(refs)}（目前 {len(bad)} 壞）", flush=True)

    print()
    if bad:
        print(f"✗ {len(bad)}/{len(refs)} 張有問題：", file=sys.stderr)
        for rel, err in sorted(bad)[:30]:
            print(f"    {rel}: {err}", file=sys.stderr)
        if len(bad) > 30:
            print(f"    …還有 {len(bad)-30} 張", file=sys.stderr)
        sys.exit(1)
    print(f"✓ 全綠：{len(refs)}/{len(refs)} 張都在 live 站且大小相符")


if __name__ == "__main__":
    main()

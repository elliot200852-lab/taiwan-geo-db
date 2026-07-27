#!/usr/bin/env python3
"""鄉鎮頁擴充進度盤點——回答「做到哪了、還剩什麼」。

存在的理由：這條線是分批做的（新北 29 區、其餘縣市之後跟上），中途可能因為
usage limit、關視窗、跨 session 而斷。斷掉之後**不准靠記憶重建進度**，
一律跑這支，它只讀磁碟上的事實：母本在不在、字數夠不夠、圖有沒有、頁產出沒。

    .venv/bin/python3 scripts/towns_status.py                # 全部
    .venv/bin/python3 scripts/towns_status.py new-taipei     # 只看某個縣市
    .venv/bin/python3 scripts/towns_status.py --json         # 機器讀
    .venv/bin/python3 scripts/towns_status.py --check-images # 另外逐張連出去驗 URL（慢）

`--check-images` 存在的理由：母本的圖片授權是由**寫作 agent 填的**，而這是對外公開站，
CC BY 要求正確標示作者——授權編錯比事實編錯更難善後。欄位有沒有填，離線就看得出來；
URL 是不是真的存在，只有連出去才知道。收稿時跑一次，別靠信任。

判準（與 docs/CONTENT-SPEC.md 對齊）：
  母本存在 → 正文 ≥2,500 字 → images ≥6 且每張有 license+author → sources ≥1
  → 頁面已產出 → hero 圖已生（母本沒有 `hero: false`）
任何一項沒過就不算完成，會列在「未完成」裡並說明卡在哪一步。
"""
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
PAGES = ROOT / "site" / "pages"
HERO = ROOT / "site" / "img" / "hero"

MIN_BODY_CHARS = 2500      # CONTENT-SPEC §正文結構
TARGET_BODY_CHARS = 4700   # 宜蘭 12 篇平均 5,100 字，低於此標為「偏短」
MIN_IMAGES = 6             # CONTENT-SPEC：6–10 張


def body_chars(sections):
    """正文中文字數（去空白）。frontmatter 不算。"""
    text = "".join(sections.values())
    return len(re.sub(r"\s", "", text))


def parse(path):
    """回 (frontmatter, sections)。frontmatter 壞掉時回 (None, {"_err": 原因})。

    刻意不讓例外往上拋：這支腳本的用途就是「斷掉之後回來看做到哪」，
    如果一個母本的 YAML 打錯字就讓整支盤點崩掉，那它在最需要的時候剛好不能用。
    寫作 agent 產出的 frontmatter 真的會有壞的——實測撞過 `author: 某某（Flickr: xxx）`
    這種沒加引號的冒號。壞了就把它當成一個「卡在這一步」的項目照常列出來。
    """
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        return None, {"_err": "沒有 --- frontmatter 區塊"}
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        detail = str(e).replace("\n", " ")[:120]
        return None, {"_err": f"YAML 解析失敗（{detail}）"}
    sections, cur, buf = {}, None, []
    for line in m.group(2).splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            if cur is not None:
                sections[cur] = "\n".join(buf).strip()
            cur, buf = h.group(1).strip(), []
        else:
            buf.append(line)
    if cur is not None:
        sections[cur] = "\n".join(buf).strip()
    return fm, sections


_IMG_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif|tiff?)(\?|$)", re.I)


def probe_url(url, tries=5):
    """回 (ok, 描述)。ok＝HTTP 200 且（content-type 是圖 **或** 網址副檔名是圖）。
    只讀 header，不下載內容。

    兩個坑都是實測踩出來的，改判準前先看清楚：

    1. **content-type 不能單獨當判準**。TCMB 的 S3（dcm.s3.hicloud.net.tw）對 .jpg
       一律回 `application/octet-stream`——站上已經上線好幾個月的圖就是這樣回的。
       只認 content-type 會把每一張 TCMB 圖都判成壞圖。
    2. **429 要退避重試，不算失敗**。Wikimedia 對連續 header 請求會擋。
       假警報比沒有檢查更糟：跑一次被騙一次之後，人就開始忽略這支腳本的紅字，
       等於把驗收關掉。
    """
    ext_ok = bool(_IMG_EXT_RE.search(url))
    last = ""
    for attempt in range(tries):
        try:
            last = subprocess.run(
                ["curl", "-sIL", "--max-time", "25", "-o", "/dev/null",
                 "-w", "%{http_code} %{content_type}", url],
                capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:
            last = f"連不上（{type(e).__name__}）"
        if last.startswith("200") and ("image" in last or ext_ok):
            return True, last
        if last.startswith("429") or last.startswith("503"):
            time.sleep(2 ** attempt * 2)   # 2s → 4s → 8s → 16s
            continue
        break
    return False, last


def check_images(units):
    """逐張連出去驗圖片 URL。授權欄位填了不代表圖存在，這一關只有連線才驗得到。"""
    jobs = []
    for u in units:
        for i, img in enumerate(u.get("_images_raw") or []):
            if (img or {}).get("url"):
                jobs.append((u, i, img["url"]))
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=3) as pool:   # 併發壓低，別自己把自己限流
        results = list(pool.map(lambda j: probe_url(j[2]), jobs))
    for (u, i, url), (ok, desc) in zip(jobs, results):
        if not ok:
            u["images_bad"].append(f"#{i}: URL 不可用（{desc}）")
            u["done"] = False
            u["blocked_at"] = "圖片 URL 連不到：" + "；".join(u["images_bad"])


def unit_report(pid, name_hint, md_path):
    """回傳一個單元的狀態 dict。md_path 不存在 → 尚未開始。"""
    r = {"id": pid, "name": name_hint, "md": None, "done": False, "blocked_at": None,
         "chars": 0, "images": 0, "images_bad": [], "sources": 0,
         "page": (PAGES / f"{pid}.html").exists(),
         "hero": (HERO / f"{pid}.webp").exists(), "hero_off": False, "notes": []}

    if md_path is None or not md_path.exists():
        r["blocked_at"] = "母本未寫"
        return r

    r["md"] = str(md_path.relative_to(ROOT))
    fm, sections = parse(md_path)
    if fm is None:
        r["blocked_at"] = "frontmatter 壞掉：" + sections.get("_err", "原因不明")
        return r

    r["name"] = fm.get("name") or name_hint
    r["chars"] = body_chars(sections)
    r["hero_off"] = fm.get("hero") is False

    images = fm.get("images") or []
    r["images"] = len(images)
    r["_images_raw"] = images   # 供 --check-images 連線驗證；輸出前會被剝掉
    for i, img in enumerate(images):
        missing = [k for k in ("url", "license", "author") if not (img or {}).get(k)]
        if missing:
            r["images_bad"].append(f"#{i}: 缺 {'/'.join(missing)}")
    r["sources"] = len(fm.get("sources") or [])

    missing_sections = [s for s in ("定位速覽", "自然地理", "人文地理", "教學特點")
                        if not sections.get(s)]

    # 卡在哪一步（由前往後，第一個沒過的就是卡點）
    if missing_sections:
        r["blocked_at"] = "缺章節：" + "、".join(missing_sections)
    elif r["chars"] < MIN_BODY_CHARS:
        r["blocked_at"] = f"正文只有 {r['chars']} 字（規格要 ≥{MIN_BODY_CHARS}）"
    elif r["images"] < MIN_IMAGES:
        r["blocked_at"] = f"圖只有 {r['images']} 張（規格要 ≥{MIN_IMAGES}）"
    elif r["images_bad"]:
        r["blocked_at"] = "圖片授權欄位不全：" + "；".join(r["images_bad"])
    elif r["sources"] == 0:
        r["blocked_at"] = "沒有 sources"
    elif not r["page"]:
        r["blocked_at"] = "母本齊了但頁面沒產出（跑 build.py）"
    else:
        r["done"] = True

    if r["done"] and r["chars"] < TARGET_BODY_CHARS:
        r["notes"].append(f"偏短（{r['chars']} 字，宜蘭均值約 5,100）")
    if r["done"] and not r["hero"] and not r["hero_off"]:
        r["notes"].append("hero 圖不存在且母本沒標 hero: false → live 會破圖")
    if r["hero_off"]:
        r["notes"].append("hero 暫時關閉（生完情境圖要把母本的 hero: false 拿掉）")
    return r


def collect():
    """從各縣市概論母本的 towns: 欄位長出待辦清單——母本即 SSOT，不掃目錄猜。"""
    out = []
    for county_md in sorted(CONTENT.glob("*/*.md")):
        fm, _ = parse(county_md)
        if not fm or not fm.get("towns"):
            continue
        county_dir = county_md.parent
        # 建 id -> md 路徑對照（同一個縣市資料夾下所有母本）
        by_id = {}
        for sub in sorted(county_dir.glob("*.md")):
            sfm, _ = parse(sub)
            if sfm and sfm.get("id"):
                by_id[sfm["id"]] = sub
        units = [unit_report(t, t, by_id.get(t)) for t in fm["towns"]]
        out.append({
            "county": fm.get("name", county_dir.name),
            "county_id": fm.get("id", ""),
            "county_page": (PAGES / f"{fm.get('id','')}.html").exists(),
            "units": units,
        })
    return out


def main():
    args = [a for a in sys.argv[1:]]
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]

    data = collect()
    if args:
        data = [d for d in data if d["county_id"] in args or d["county"] in args]

    if "--check-images" in sys.argv:
        all_units = [u for d in data for u in d["units"]]
        total = sum(len(u.get("_images_raw") or []) for u in all_units)
        print(f"逐張連線驗圖（{total} 張）…", file=sys.stderr)
        check_images(all_units)

    for d in data:                       # 內部欄位不外流
        for u in d["units"]:
            u.pop("_images_raw", None)

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data:
        print("沒有任何縣市母本帶 towns: 欄位（或指定的縣市不存在）。")
        return

    grand_done = grand_total = 0
    for d in data:
        done = [u for u in d["units"] if u["done"]]
        todo = [u for u in d["units"] if not u["done"]]
        grand_done += len(done)
        grand_total += len(d["units"])
        page_mark = "✓" if d["county_page"] else "✗ 縣市頁未產出"
        print(f"\n{'='*66}")
        print(f"{d['county']}（{d['county_id']}.html {page_mark}）"
              f"　完成 {len(done)}／{len(d['units'])}")
        print("=" * 66)
        if done:
            print("  已完成：")
            for u in done:
                note = ("　⚠ " + "；".join(u["notes"])) if u["notes"] else ""
                print(f"    ✓ {u['name']:<16} {u['chars']:>5} 字 · "
                      f"圖 {u['images']} · 源 {u['sources']}{note}")
        if todo:
            print("  未完成：")
            for u in todo:
                print(f"    ✗ {u['name']:<16} → {u['blocked_at']}")

    print(f"\n{'-'*66}")
    print(f"總計：{grand_done}／{grand_total} 個鄉鎮頁完成")
    print("續做前先讀 docs/HANDOFF-towns-expansion.md（含紅隊關卡與既定決策）。")


if __name__ == "__main__":
    main()

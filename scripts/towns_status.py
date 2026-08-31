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
MAX_IMAGES = 10            # 上限也是規格，第一批有一篇 11 張才被抓到
# CONTENT-SPEC：教學特點佔全文 1/3 以上（本資料庫的核心）。
# 這裡用 0.330 而不是 1/3，是刻意留 0.3 個百分點的容差：一篇 5,000 字的母本，
# 0.3pp 只有 16 個字，卡在小數第三位判生死沒有意義，卻會讓早就上線的頁面在
# 邊界上反覆進出「完成」名單。實際佔比一律印出來，要嚴格看的人自己看數字。
MIN_TEACHING_RATIO = 0.330
MAX_LEDE_CHARS = 150       # CONTENT-SPEC：定位速覽 ≤150 字
# 「字」在這裡算**純漢字**（不含標點、阿拉伯數字、空白）。這不是隨便選的：
# 寫作 agent 自己就是這樣數的，閘門若用「非空白字元」會比它們嚴約 15%，
# 於是每一批都要在「我判超標／它認為沒超」之間多空轉一輪。尺要同一把。
# 附帶事實：既有 12 篇宜蘭用哪種計法都有一半以上超標（純漢字 7 篇、非空白 11 篇），
# 這條規格在那一批根本沒被執行過——所以這裡只當提醒，不擋。
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# David 的硬規則：禁對立翻轉句式（memory feedback_avoid_ai_prose_antithesis）。
# 2026-07-27 第一批獨立驗收在 8 篇裡抓出 15 條，全部是下面這幾種長相。
# 做成自動掃描，免得每一批都要派一支 agent 用肉眼讀。
#
# ⚠️ 第一版寫得太窄、**漏報**：只認「這不是／那不是」開頭，於是
# 「這個數字不是巧合，是…」整句溜過去。會漏報的檢查跟會誤報的一樣傷——
# 前者讓人以為乾淨了，後者讓人不再看紅字，兩種都等於把驗收關掉。
# 現在改成不限定「不是」前面的主詞。
#
# 這支只抓**句式**，抓不到「機械對仗排比」「每段收一句金句」這類要讀才看得出來的問題，
# 也抓不到「臺灣多數平原聚落的起點是水田，林口的起點不是。」這種尾綴否定的變形。
# 它是篩子不是閘門——過了不代表文風沒問題。
_AI_PROSE_PATTERNS = [
    (re.compile(r"不是[^，。；？！\n]{0,30}[，、]\s*而是"), "不是…而是"),
    (re.compile(r"與其說[^，。；\n]{0,30}[，、]\s*不如說"), "與其說…不如說"),
    (re.compile(r"不僅是[^，。；\n]{0,30}[，、]\s*更是"), "不僅是…更是"),
    (re.compile(r"不是[^，。；？！\n]{1,30}[，、]\s*是[^，。；？！\n]{1,40}[。」，]"), "不是 X，是 Y"),
]


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


DUP_BASELINE = ROOT / "docs" / "image-url-dup-baseline.txt"


def check_image_dup(data):
    """新頁圖片 URL 撞任何既有頁＝fail（離線、每次都跑）。

    2026-08-31 立（管線 review Phase 0）：在這之前，防重複用圖靠的是把全站已用
    圖 URL 清單（USED_IMAGES，27 萬字元、1,377 行、逐批在長）塞給每支寫作 agent
    「讀完並記得」——那是拿語言模型做集合運算，塞掉 57% 的輸入額度而且一定會漏。
    集合運算腳本做，agent 一行 URL 都不用讀。

    docs/image-url-dup-baseline.txt＝立閘時已存在的 8 條跨頁共用 URL（縣頁↔主題頁
    的歷史共用，fetch_images.py 對共用 URL 本來就重用同一實體檔）。只豁免這些；
    清單只准縮不准長——新頁要用的圖在站上出現過，就換一張。
    """
    baseline = set()
    if DUP_BASELINE.exists():
        baseline = {ln.strip() for ln in DUP_BASELINE.read_text().splitlines()
                    if ln.strip() and not ln.startswith("#")}
    # ⚠️ 一律用「相對路徑」不用 basename 當身分：站上已有五組跨縣同名檔
    # （taoyuan.md、datong.md、xinyi.md、zhongshan.md、zhongzheng.md 各兩份），
    # basename 比對會讓同名檔之間共用圖被靜默放行（2026-09-01 紅隊抓到）。
    url_files = {}
    for md in CONTENT.rglob("*.md"):
        fm, _ = parse(md)
        for img in (fm or {}).get("images") or []:
            u = (img or {}).get("url")
            if u:
                url_files.setdefault(u, set()).add(str(md.relative_to(ROOT)))
    for d in data:
        for r in d["units"]:
            if not r["md"]:
                continue
            own = r["md"]
            for i, img in enumerate(r.get("_images_raw") or []):
                u = (img or {}).get("url")
                if not u or u in baseline:
                    continue
                others = url_files.get(u, set()) - {own}
                if others:
                    r["images_bad"].append(f"#{i}: 圖 URL 與 {'、'.join(sorted(others))} 重複")
                    r["done"] = False
                    r["blocked_at"] = "圖片跨頁重複：" + "；".join(r["images_bad"])


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
         "chars": 0, "teach_chars": 0, "teach_ratio": 0, "lede_chars": 0,
         "ai_prose": [], "images": 0, "images_bad": [], "sources": 0,
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

    # 教學特點佔比——這是本資料庫的核心，規格明訂 1/3 以上。
    # 第一批有 4 篇因為〈人文地理〉膨脹而被稀釋到 1/3 以下（兩篇硬違規），
    # 所以這一項要自動量，不能靠人讀。
    teach = len(re.sub(r"\s", "", sections.get("教學特點", "")))
    r["teach_chars"] = teach
    r["teach_ratio"] = (teach / r["chars"]) if r["chars"] else 0
    r["lede_chars"] = len(_CJK_RE.findall(sections.get("定位速覽", "")))

    # AI 腔掃描（David 硬規則）
    body_all = "\n".join(sections.values())
    hits = []
    for pat, label in _AI_PROSE_PATTERNS:
        for m in pat.finditer(body_all):
            hits.append(f"{label}：{m.group(0)[:34]}")
    r["ai_prose"] = hits

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
    elif r["teach_ratio"] < MIN_TEACHING_RATIO:
        r["blocked_at"] = (f"教學特點只佔 {r['teach_ratio']*100:.1f}%（規格要 ≥33.3%）"
                           f"——修法是砍〈人文地理〉，不是加教學特點")
    elif r["images"] < MIN_IMAGES:
        r["blocked_at"] = f"圖只有 {r['images']} 張（規格要 ≥{MIN_IMAGES}）"
    elif r["images"] > MAX_IMAGES:
        r["blocked_at"] = f"圖有 {r['images']} 張（規格上限 {MAX_IMAGES}）"
    elif r["images_bad"]:
        r["blocked_at"] = "圖片授權欄位不全：" + "；".join(r["images_bad"])
    elif r["sources"] == 0:
        r["blocked_at"] = "沒有 sources"
    elif not r["page"]:
        r["blocked_at"] = "母本齊了但頁面沒產出（跑 build.py）"
    else:
        r["done"] = True

    if r["ai_prose"]:
        # 不擋（不是規格硬要求，是 David 的文風規則），但一定要看得見
        r["notes"].append(f"AI 腔 {len(r['ai_prose'])} 條：" + "／".join(r["ai_prose"][:2]))
    if r["lede_chars"] > MAX_LEDE_CHARS:
        r["notes"].append(f"定位速覽 {r['lede_chars']} 字，超過 {MAX_LEDE_CHARS}")
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

    check_image_dup(data)   # 離線、便宜，每次都跑

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
                      f"教學 {u['teach_ratio']*100:4.1f}% · "
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

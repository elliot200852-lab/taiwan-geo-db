#!/usr/bin/env python3
"""鄉鎮頁擴充進度盤點——回答「做到哪了、還剩什麼」。

存在的理由：這條線是分批做的（新北 29 區、其餘縣市之後跟上），中途可能因為
usage limit、關視窗、跨 session 而斷。斷掉之後**不准靠記憶重建進度**，
一律跑這支，它只讀磁碟上的事實：母本在不在、字數夠不夠、圖有沒有、頁產出沒。

    .venv/bin/python3 scripts/towns_status.py            # 全部
    .venv/bin/python3 scripts/towns_status.py new-taipei # 只看某個縣市
    .venv/bin/python3 scripts/towns_status.py --json     # 機器讀

判準（與 docs/CONTENT-SPEC.md 對齊）：
  母本存在 → 正文 ≥2,500 字 → images ≥6 且每張有 license+author → sources ≥1
  → 頁面已產出 → hero 圖已生（母本沒有 `hero: false`）
任何一項沒過就不算完成，會列在「未完成」裡並說明卡在哪一步。
"""
import json
import re
import sys
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
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        return None, {}
    fm = yaml.safe_load(m.group(1)) or {}
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
        r["blocked_at"] = "frontmatter 壞掉（沒有 --- 區塊）"
        return r

    r["name"] = fm.get("name") or name_hint
    r["chars"] = body_chars(sections)
    r["hero_off"] = fm.get("hero") is False

    images = fm.get("images") or []
    r["images"] = len(images)
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

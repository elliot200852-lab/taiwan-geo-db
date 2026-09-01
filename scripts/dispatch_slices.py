#!/usr/bin/env python3
"""派工切片產生器——派工端用，寫作 agent 不跑這支。

2026-08-31 管線 review Phase 0 立。取代兩個舊做法：
① 寫作 agent 讀鄰區母本全文（5–7 檔×約 1 萬字元）→ 改由派工端跑
   `--slices`，把鄰區的「說書稿切分提示」抽出來貼進派工單（每檔約 1,200 字）。
② 派工端「回憶並人工比對」已用開場句／收尾句 → 改跑 `--sentences`，
   台帳裡每段裝置的開場句與收尾句直接列出來，照 kaohsiung-writing-plan §8-4
   第 8 點「開場句與收尾約束句一起逐段指定」開規格。

    .venv/bin/python3 scripts/dispatch_slices.py --slices niaosong dashu daliao
    .venv/bin/python3 scripts/dispatch_slices.py --sentences            # 全台帳
    .venv/bin/python3 scripts/dispatch_slices.py --sentences 鳥松 仁武   # 只看某幾區
    .venv/bin/python3 scripts/dispatch_slices.py --titles               # 全站
    .venv/bin/python3 scripts/dispatch_slices.py --titles --county tainan

2026-09-01 補 `--titles`：取代被砍掉的 `collision_check.py`（n-gram 相似度撞題器；
紅隊拿高雄 39 頁實跑證明它數學上是逐字匹配器，短的五年級小標要湊出高分幾乎等於
一字不差，換一個字就放行；抽取器本身在真實語料上還有 9% 抽成「埤」「拆」這種
1–5 字碎片）。改走更簡單也更誠實的路：把全部探究題／五年級小標整句原文攤開，
逐字重複交給 `grep ... | sort | uniq -d`（見 `scripts/check-duplicate-titles.sh`），
「像但不完全一樣」的撞題交給人眼掃這份清單——別假裝有一支腳本能幫你判斷語意相似。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
LEDGERS = [ROOT / "docs" / "devices-used-kaohsiung.txt",
           ROOT / "docs" / "devices-used-east.txt"]

_SENT_SPLIT = re.compile(r"(?<=[。？！])")

# ---------------------------------------------------------------------------
# --titles：探究題／五年級小標純文字清單
# ---------------------------------------------------------------------------

# 抽取規則是照全站實際語料校準的（跑遍 170 檔逐一核對過三種變體），不是憑空假設：
#   ・縣市／區頁（151 檔）：`### 探究問題` 每題「「問題」——說明」或「**問題**（說明）」；
#     `### 五年級即用` 每條「- 【五年級Ｘ】**小標**：說明」。
#   ・跨主題頁 content/themes/*.md（19 檔）：沒有粗體／冒號小標慣例，整條就是一句話，
#     沒有可切的「小標」——切了就是用冒號亂猜，猜錯比不猜更危險，所以整句照抄。
#   ・content/themes/temples.md 的探究題用全形「1。」不是「1.」，且問題不加「」／**。
_ITEM_RE = re.compile(r"^([0-9]+)[.。]\s*(.+?)(?=\n[0-9]+[.。]\s|\Z)", re.M | re.S)
_LEAD_QUOTE_RE = re.compile(r"^「(.+?)」")
_LEAD_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*")
_TRAIL_PAREN_RE = re.compile(r"[（(][^）(]*[）)]\s*$")
_GRADE5_BULLET_RE = re.compile(r"^-\s*【.+?】\s*(.+)$", re.M)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
MIN_LABEL_LEN = 6


def _get_section(text, heading, level):
    """回傳 `{'#'*level} {heading}` 底下的內文，直到下一個同級或更高級標題。"""
    marker = "#" * level
    pattern = (rf"^{marker}\s+{re.escape(heading)}\s*\n"
               rf"(.*?)(?=^#{{1,{level}}}\s|\Z)")
    m = re.search(pattern, text, re.M | re.S)
    return m.group(1) if m else None


def _extract_question(item):
    """探究題每一條的題目原文——不切段落只挑「代表句」，整條原文照抄。

    三種真實體例都要接得住：
      1.「柳營義士路上的芒果樹……」——引導學生……   → 取最前面那組「」
      1. **打開地圖看光復鄉……？**（從兩條水的對比……） → 取最前面那組 **粗體**
      1。 給孩子看「利澤簡老街……」和「北港廟埕……」兩張照片，先不解釋…(從觀察進入假設) → 兩種都沒有，整條照抄只砍尾巴的（…）附註

    「」／**必須出現在題目最開頭**才採信——temples.md 有題目把「」用在句中當引號
    （例：「給孩子看『利澤簡老街正中央的媽祖廟』兩張照片」），若不鎖開頭位置會
    像舊腳本一樣把句中一小段誤判成整題。
    """
    item = item.strip()
    qm = _LEAD_QUOTE_RE.match(item)
    if qm:
        return qm.group(1).strip()
    bm = _LEAD_BOLD_RE.match(item)
    if bm:
        return bm.group(1).strip()
    text = re.split(r"——", item)[0]
    text = _TRAIL_PAREN_RE.sub("", text).strip()
    return text


def _extract_grade5_label(bullet_rest):
    """五年級即用每一條的「小標」——粗體整段照抄（不是粗體裡再挑一組「」）。

    2026-08-31 舊腳本 `collision_check.py` 的臭蟲就在這裡：抓「粗體內最後一組
    「」」，遇到 `**用「埤」字地名讀平原怎麼存水**` 會把整條小標誤抽成「埤」
    兩個字。粗體本身就是小標的完整範圍，不必也不該再往裡面切。
    沒有粗體（跨主題頁體例）就整條照抄，不猜冒號分界（見模組說明）。
    """
    bm = _BOLD_RE.search(bullet_rest)
    return bm.group(1).strip() if bm else bullet_rest.strip()


def _page_id(raw, fallback):
    m = re.search(r"^id:\s*(\S+)\s*$", raw, re.M)
    return m.group(1) if m else fallback


def titles(counties):
    """全站（或 --county 限定）探究題＋五年級小標純文字清單，一行一條、前標頁 id。

    抽不到就報錯印出來、不靜默略過（一頁抽到 0 條，代表格式跟預期不符，
    需要人去看不是讓清單少一頁沒人發現）；抽到但明顯過短（<6 字，多半是
    抽取規則對這頁失效）另外印警告，但值照樣列出來讓人自己判斷。
    """
    if counties:
        dirs = []
        for c in sorted(counties):
            d = CONTENT / c
            if not d.is_dir():
                print(f"⚠ 找不到 content/{c}/ 這個縣市夾")
                continue
            dirs.append(d)
    else:
        dirs = sorted(p for p in CONTENT.iterdir() if p.is_dir())

    total = 0
    warned = 0
    for county_dir in dirs:
        for path in sorted(county_dir.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            page_id = _page_id(raw, path.stem)

            teach = _get_section(raw, "教學特點", level=2)
            if teach is None:
                print(f"⚠ {page_id}（{path.relative_to(ROOT)}）：找不到 `## 教學特點`，跳過")
                continue

            q_section = _get_section(teach, "探究問題", level=3)
            questions = ([_extract_question(m.group(2)) for m in _ITEM_RE.finditer(q_section)]
                         if q_section is not None else [])
            if not questions:
                print(f"⚠ {page_id}：`### 探究問題` 抽不到任何題目——格式可能跟預期不符")

            g_section = _get_section(teach, "五年級即用", level=3)
            grade5 = ([_extract_grade5_label(m.group(1)) for m in _GRADE5_BULLET_RE.finditer(g_section)]
                      if g_section is not None else [])
            if not grade5:
                print(f"⚠ {page_id}：`### 五年級即用` 抽不到任何小標——格式可能跟預期不符")

            for i, q in enumerate(questions, 1):
                flag = ""
                if len(q) < MIN_LABEL_LEN:
                    flag = "　⚠ 過短，人工核對原句"
                    warned += 1
                print(f"{page_id}｜探究題{i}：{q}{flag}")
                total += 1
            for i, g in enumerate(grade5, 1):
                flag = ""
                if len(g) < MIN_LABEL_LEN:
                    flag = "　⚠ 過短，人工核對原句"
                    warned += 1
                print(f"{page_id}｜五年級小標{i}：{g}{flag}")
                total += 1

    print(f"\n━━ 共 {total} 條（{warned} 條過短警告）━━", file=sys.stderr)


def slices(slugs):
    """抽指定頁的 ## 說書稿切分提示 全文——派工單「鄰區分工」段的原料。"""
    for slug in slugs:
        # 站上有跨縣同名檔（taoyuan/datong/xinyi…），slug 可帶縣夾消歧：
        #   dispatch_slices.py --slices kaohsiung/taoyuan
        # 裸 slug 命中多檔＝直接報錯要求消歧，不准靜默取第一個（2026-09-01 紅隊）。
        hits = (list(CONTENT.rglob(f"{slug}.md")) if "/" not in slug
                else [p for p in [CONTENT / f"{slug}.md"] if p.exists()])
        if not hits:
            print(f"⚠ 找不到 content/**/{slug}.md")
            continue
        if len(hits) > 1:
            opts = "、".join(str(p.relative_to(CONTENT))[:-3] for p in hits)
            print(f"⚠ {slug} 命中多檔（{opts}）——用 縣夾/slug 消歧後重跑")
            continue
        raw = hits[0].read_text(encoding="utf-8")
        m = re.search(r"^## 說書稿切分提示\s*\n(.*?)(?=^## |\Z)", raw, re.M | re.S)
        name = re.search(r"^name:\s*(\S+)", raw, re.M)
        print(f"\n### {name.group(1) if name else slug}（{hits[0].relative_to(ROOT)}）")
        print(m.group(1).strip() if m else "（本頁沒有說書稿切分提示）")


def sentences(names):
    """列台帳每段裝置的開場句＋收尾句——「已用開場／收尾說法」封死清單的原料。"""
    for ledger in LEDGERS:
        if not ledger.exists():
            continue
        print(f"\n━━ {ledger.name} ━━")
        town = None
        for block in re.split(r"\n(?=## |> 🗣)", ledger.read_text(encoding="utf-8")):
            h = re.match(r"## (\S+?)（", block)
            if h:
                town = h.group(1)
                continue
            if not block.startswith("> 🗣"):
                continue
            if names and town not in names:
                continue
            body = re.sub(r"^> ?", "", block, flags=re.M).replace("\n", "")
            m = re.search(r"AI 提示：(.+)$", body)
            text = (m.group(1) if m else body).strip()
            sents = [s for s in _SENT_SPLIT.split(text) if s.strip()]
            if not sents:
                continue
            seg = re.search(r"切分段落：([^。]+)", body)
            print(f"\n▪ {town}｜{seg.group(1).strip() if seg else '？'}")
            print(f"  開場：{sents[0].strip()[:80]}")
            print(f"  收尾：{sents[-1].strip()[:80]}")


def main():
    args = sys.argv[1:]
    if "--slices" in args:
        slices([a for a in args if not a.startswith("--")])
    elif "--sentences" in args:
        sentences(set(a for a in args if not a.startswith("--")))
    elif "--titles" in args:
        if "--county" in args:
            i = args.index("--county")
            counties = []
            for a in args[i + 1:]:
                if a.startswith("--"):
                    break
                counties.append(a)
        else:
            counties = []
        titles(counties)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

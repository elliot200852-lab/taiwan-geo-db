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
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
LEDGERS = [ROOT / "docs" / "devices-used-kaohsiung.txt",
           ROOT / "docs" / "devices-used-east.txt"]

_SENT_SPLIT = re.compile(r"(?<=[。？！])")


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
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

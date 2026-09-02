#!/usr/bin/env python3
"""事實機械閘——臺南批起的收稿必經（tainan-writing-plan §3-P-1 第 4 點、§3-P-2）。

它不判斷真假，只做一件語言模型做不穩的集合運算：把正文裡「每一個 4 位數年份、
帶單位的數量詞、引號內的機構名」抽出來編號，要求寫作端逐條回答「這條對應
`sources:` 第幾條」，對不上就退件。後壁批的 17 項 FAIL 有 14 項是這類「寫得出來、
指不到來源」的細節；Sonnet 查核抓不到「要回讀原文再算一次」的錯，所以先把
「有沒有來源可回讀」這一層交給腳本，Sonnet 只需要對著來源驗真假。

    .venv/bin/python3 scripts/fact_gate.py content/tainan/madou.md            # 抽取＋印對照表骨架
    .venv/bin/python3 scripts/fact_gate.py content/tainan/madou.md --map madou-factmap.txt   # 驗對照表

對照表格式（一行一條，寫作 agent 填）：
    <項目#>  <sources 第幾條，可多條逗號分隔 | 待查證 | 互指>
    12  3
    13  3,7
    14  待查證      ← 只有該句正文真的寫了「待查證」才收
    15  互指        ← 只有該句真的指向〈○○〉頁／主題頁（含「〈」）才收
`#` 開頭＝註解。驗證＝每個項目都有答、每個 sources 編號都在範圍內、待查證／互指
兩種免查答案都跟正文對得上。過＝exit 0；不過＝列出缺漏，exit 1。
"""
import re
import sys
from pathlib import Path

import yaml

UNIT = r"(?:平方公里|km²|公頃|公里|公尺|公噸|公斤|甲|人|戶|元|歲|％|%)"
NUM = r"\d[\d,\.]*\s*(?:萬|億)?\s*"
RE_YEAR = re.compile(r"(?<![\d.])(?:1[0-9]{3}|20[0-9]{2})(?:\s*[–\-—~]\s*(?:1[0-9]{3}|20[0-9]{2}))?(?=\s*年)|(?<![\d.])\d{4}-\d{2}(?:-\d{2})?(?!\d)")
RE_QTY = re.compile(r"(?:約|近|逾|超過|不到|達)?\s*" + NUM + UNIT)
RE_ORG = re.compile(r"「([^「」]{2,30}?(?:局|處|署|部|會|廳|所|館|院|社|公司|中心|協會|組合|學校|大學|工作站|管理處|分處|園區|基金會))」")
# 說書稿的固定欄「長度：約 5 分鐘」與速覽的字數規格不是事實主張，分鐘不在單位表裡本來就抓不到。


def split(md: Path):
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        sys.exit(f"{md}: 沒有 frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    body_start = text[: m.end()].count("\n") + 1
    body = text[m.end():]
    return fm, body, body_start


def extract(body: str, body_start: int):
    items, seen = [], set()
    for i, line in enumerate(body.splitlines(), start=body_start):
        if line.startswith("#"):
            continue
        for kind, rx in (("年份", RE_YEAR), ("數量", RE_QTY), ("機構", RE_ORG)):
            for mm in rx.finditer(line):
                key = mm.group(1) if kind == "機構" else mm.group(0).strip()
                if (kind, key) in seen:
                    continue
                seen.add((kind, key))
                s = max(0, mm.start() - 18)
                ctx = line[s: mm.end() + 18].replace("|", "｜")
                items.append({"n": len(items) + 1, "kind": kind, "key": key, "line": i, "ctx": ctx, "text": line})
    return items


def print_table(items, n_sources):
    print(f"# 事實機械閘抽取表（sources 共 {n_sources} 條）——複製到 <slug>-factmap.txt，第二欄填 sources 編號")
    print(f"# 格式：<項目#>  <sources 編號（可逗號多條）| 待查證 | 互指>")
    for it in items:
        print(f"{it['n']:>3}  [{it['kind']}] L{it['line']} {it['key']}    ｜…{it['ctx']}…")
    print(f"# 共 {len(items)} 條")


def verify(items, n_sources, map_path: Path):
    answers = {}
    for raw in map_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit():
            print(f"✗ 對照表格式錯：{raw!r}")
            return 1
        answers[int(parts[0])] = parts[1].strip()

    fails = []
    for it in items:
        a = answers.get(it["n"])
        tag = f"#{it['n']} [{it['kind']}] L{it['line']} {it['key']}"
        if a is None:
            fails.append(f"缺答  {tag}")
            continue
        if a.startswith("待查證"):
            if "待查證" not in it["text"]:
                fails.append(f"答「待查證」但該行正文沒有「待查證」  {tag}")
            continue
        if a.startswith("互指"):
            if "〈" not in it["text"]:
                fails.append(f"答「互指」但該行正文沒有〈○○〉頁指向  {tag}")
            continue
        try:
            idx = [int(x) for x in re.split(r"[,，、\s]+", a) if x]
        except ValueError:
            fails.append(f"答案不是編號  {tag} → {a!r}")
            continue
        bad = [x for x in idx if not (1 <= x <= n_sources)]
        if not idx or bad:
            fails.append(f"sources 編號超出 1–{n_sources}  {tag} → {a!r}")
    extra = sorted(set(answers) - {it["n"] for it in items})
    if extra:
        print(f"⚠ 對照表多出不存在的項目#：{extra}（正文改過後要重抽）")
    if fails:
        print(f"✗ 機械閘未過：{len(fails)}/{len(items)} 條對不上")
        for f in fails:
            print("  " + f)
        return 1
    print(f"✓ 機械閘通過：{len(items)} 條全部指得到（sources {n_sources} 條）")
    return 0


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    md = Path(sys.argv[1])
    fm, body, body_start = split(md)
    sources = fm.get("sources") or []
    items = extract(body, body_start)
    if "--map" in sys.argv:
        sys.exit(verify(items, len(sources), Path(sys.argv[sys.argv.index("--map") + 1])))
    print_table(items, len(sources))


if __name__ == "__main__":
    main()

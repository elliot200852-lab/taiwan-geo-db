#!/usr/bin/env python3
"""事實機械閘——臺南批起的收稿必經（tainan-writing-plan §3-P-1 第 4 點、§3-P-2）。

它把正文與 stats 裡「每一個年份、帶單位的數量詞、機構名」抽出來編號，要求寫作端
逐條回答「對應 `sources:` 第幾條＋該來源裡的一段逐字引文」，然後（--fetch）把來源
抓下來比對引文真的在不在。它保證的是「指得到、引得出」；「指得對」（數字有沒有套錯
範圍、機關有沒有掛錯）仍是查核端的事——別把它當成事實查核的替身。

⚠ 它的盲區（2026-09-02 紅隊實跑）：沒有數字、沒有機構後綴的幻覺（憑空生成的河名、
人名）一條都抓不到；中文數字（「二萬人」「乾隆五十三年」）抓不到——所以派工單要求
數字一律阿拉伯數字（模板 §C）。這些交給 §3-P-1 第三條硬限制與查核端。

    .venv/bin/python3 scripts/fact_gate.py content/tainan/madou.md                      # 抽取，印對照表骨架
    .venv/bin/python3 scripts/fact_gate.py content/tainan/madou.md --map madou-factmap.txt          # 驗格式＋範圍
    .venv/bin/python3 scripts/fact_gate.py content/tainan/madou.md --map madou-factmap.txt --fetch  # 再把來源抓下來比對引文

對照表格式（一行一條，寫作 agent 填；`#` 開頭＝註解）：
    <項目#>  <sources 編號（可逗號多條）>  <該來源裡 ≥8 字的逐字引文>
    12  3  水堀頭遺址位於麻豆區南勢里
    14  待查證      ← 只有該項目前後 20 字內正文真的寫了「待查證」才收
    15  互指        ← 只有該項目前後 20 字內正文真的有〈○○〉頁指向才收
驗證＝每個項目都有答、編號在範圍內、引文 ≥8 字；--fetch 時引文要在來源正文裡找得到
（HTML 去標籤、NFKC、去空白後子字串比對）。抓不到的來源（逾時／xls／pdf）標「?」交查核端，
不算失敗；引文明確不在來源裡＝✗。過＝exit 0；不過＝列出缺漏，exit 1。
"""
import hashlib
import html
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import yaml

UNIT = r"(?:平方公里|km²|公頃|公里|公尺|公噸|公斤|甲|人|戶|元|歲|里|鄰|家|間|座|株|棵|ha|％|%)"
NUM = r"\d[\d,\.]*\s*(?:萬|億)?\s*"
YEAR4 = r"(?:1[0-9]{3}|20[0-9]{2})"
RE_YEAR = re.compile(
    rf"(?<![\d.]){YEAR4}(?:\s*[–\-—~]\s*{YEAR4})?(?=\s*年)"          # 1932 年、1920–1930 年
    rf"|(?<=[（(]){YEAR4}(?=[）)])"                                    # 林百貨（1932）
    rf"|(?<![\d.]){YEAR4}[.\-/]\d{{1,2}}(?:[.\-/]\d{{1,2}})?(?!\d)"    # 2016-02-18、1947.3.13
    rf"|民國\s*\d{{1,3}}\s*年"
    rf"|(?<![\d.]){YEAR4}(?=\s*年代)"
)
RE_QTY = re.compile(NUM + UNIT)
RE_ORG_Q = re.compile(r"「([^「」]{2,30}?(?:局|處|署|部|會|廳|所|館|院|社|公司|中心|協會|組合|學校|大學|工作站|管理處|分處|園區|基金會))」")
RE_ORG_U = re.compile(r"(?<![「\w])([一-鿿]{3,20}?(?:市政府|縣政府|農業局|文化局|水利局|文化資產局|農田水利署|管理處|分處|研究所|水利會|事務所|文化部|經濟部|內政部|監察院|立法院|總督府))")
PREFIX = re.compile(r"^(?:約|近|逾|超過|不到|達|共|計)\s*")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def split(md: Path):
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        sys.exit(f"{md}: 沒有 frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    body_start = text[: m.end()].count("\n") + 1
    return fm, text[m.end():], body_start


def extract(fm, body: str, body_start: int):
    items, seen = [], set()

    def add(kind, key, line_no, line, start, end):
        key = PREFIX.sub("", key).strip()
        sig = (kind, norm(key), line_no)
        if sig in seen:
            return
        seen.add(sig)
        ctx = line[max(0, start - 20): end + 20].replace("|", "｜")
        near = line[max(0, start - 20): end + 20]
        items.append({"n": len(items) + 1, "kind": kind, "key": key, "line": line_no, "ctx": ctx, "near": near})

    stats = fm.get("stats") or {}
    for k in ("population", "area_km2", "density"):
        v = str(stats.get(k, ""))
        if v:
            add("stats", f"{k}: {v}", 0, v, 0, len(v))

    for i, line in enumerate(body.splitlines(), start=body_start):
        if line.startswith("#"):
            continue
        for kind, rx in (("年份", RE_YEAR), ("數量", RE_QTY), ("機構", RE_ORG_Q), ("機構", RE_ORG_U)):
            for mm in rx.finditer(line):
                key = mm.group(1) if mm.groups() and mm.group(1) else mm.group(0)
                add(kind, key, i, line, mm.start(), mm.end())
    return items


def print_table(items, n_sources):
    print(f"# 事實機械閘抽取表（sources 共 {n_sources} 條）——複製到 <slug>-factmap.txt 填第二、三欄")
    print("# 格式：<項目#>  <sources 編號（可逗號多條）>  <該來源裡 ≥8 字逐字引文>   或  <項目#> 待查證 / 互指")
    for it in items:
        where = "stats" if it["line"] == 0 else f"L{it['line']}"
        print(f"{it['n']:>3}  [{it['kind']}] {where} {it['key']}    ｜…{it['ctx']}…")
    print(f"# 共 {len(items)} 條")


_cache = {}


def fetch_text(url: str, cache_dir: Path) -> str | None:
    if url in _cache:
        return _cache[url]
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / (hashlib.md5(url.encode()).hexdigest() + ".txt")
    if f.exists():
        _cache[url] = f.read_text(encoding="utf-8")
        return _cache[url]
    if "tcmb.culture.tw" in url or re.search(r"\.(xls|xlsx|ods|pdf|zip)(\?|$)", url, re.I):
        _cache[url] = None      # TCMB 禁打；二進位檔不比對
        return None
    try:
        r = subprocess.run(["curl", "-sL", "-m", "20", "-A", "Mozilla/5.0 (fact_gate)", url],
                           capture_output=True, timeout=25)
        raw = r.stdout.decode("utf-8", "ignore")
    except Exception:
        _cache[url] = None
        return None
    if r.returncode != 0 or not raw or "<html" not in raw.lower() and len(raw) < 200:
        _cache[url] = None
        return None
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = norm(html.unescape(txt))   # 先解 entity（含 &#x8CC7; 大寫十六進位——關廟批實測漏掉會整頁亂碼）
    f.write_text(txt, encoding="utf-8")
    _cache[url] = txt
    return txt


def verify(items, sources, map_path: Path, do_fetch: bool, cache_dir: Path):
    answers = {}
    for raw in map_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit():
            print(f"✗ 對照表格式錯：{raw!r}")
            return 1
        answers[int(parts[0])] = (parts[1].strip(), parts[2].strip() if len(parts) > 2 else "")

    n_sources = len(sources)
    fails, unverifiable, hits = [], 0, 0
    for it in items:
        tag = f"#{it['n']} [{it['kind']}] L{it['line']} {it['key']}"
        a = answers.get(it["n"])
        if a is None:
            fails.append(f"缺答  {tag}")
            continue
        ans, quote = a
        if ans.startswith("待查證"):
            if "待查證" not in it["near"]:
                fails.append(f"答「待查證」但該項目前後 20 字內正文沒有「待查證」  {tag}")
            continue
        if ans.startswith("互指"):
            if "〈" not in it["near"]:
                fails.append(f"答「互指」但該項目前後 20 字內正文沒有〈○○〉頁指向  {tag}")
            continue
        try:
            idx = [int(x) for x in re.split(r"[,，、]+", ans) if x]
        except ValueError:
            fails.append(f"答案不是編號  {tag} → {ans!r}")
            continue
        bad = [x for x in idx if not (1 <= x <= n_sources)]
        if not idx or bad:
            fails.append(f"sources 編號超出 1–{n_sources}  {tag} → {ans!r}")
            continue
        q = norm(re.sub(r"[「」『』，。、；：！？（）()\[\]\"'…—–\-]", "", quote))
        if len(q) < 8:
            fails.append(f"引文不足 8 字（去標點）  {tag} → {quote!r}")
            continue
        if not do_fetch:
            continue
        found, fetched_any = False, False
        for x in idx:
            txt = fetch_text(sources[x - 1], cache_dir)
            if txt is None:
                continue
            fetched_any = True
            if norm(quote) in txt or q in re.sub(r"[「」『』，。、；：！？（）()\[\]\"'…—–\-]", "", txt):
                found = True
                break
        if found:
            hits += 1
        elif not fetched_any:
            unverifiable += 1
            print(f"?  無法取得來源（逾時／二進位／TCMB），交查核端人工開  {tag} → sources {idx}")
        else:
            fails.append(f"引文不在來源正文裡  {tag} → sources {idx} 引文 {quote[:30]!r}")

    extra = sorted(set(answers) - {it["n"] for it in items})
    if extra:
        print(f"⚠ 對照表多出不存在的項目#：{extra}（正文改過後要重抽）")
    if fails:
        print(f"✗ 機械閘未過：{len(fails)}/{len(items)} 條對不上")
        for f in fails:
            print("  " + f)
        return 1
    tail = f"；--fetch 引文命中 {hits}、無法取得 {unverifiable}" if do_fetch else "（未 --fetch，引文尚未比對來源）"
    print(f"✓ 機械閘通過：{len(items)} 條全部指得到（sources {n_sources} 條）{tail}")
    return 0


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    md = Path(sys.argv[1])
    fm, body, body_start = split(md)
    sources = [str(s) for s in (fm.get("sources") or [])]
    items = extract(fm, body, body_start)
    if "--map" in sys.argv:
        cache = Path.home() / "MyWork/_workspace/geo-tn-b2/.source-cache"
        sys.exit(verify(items, sources, Path(sys.argv[sys.argv.index("--map") + 1]),
                        "--fetch" in sys.argv, cache))
    print_table(items, len(sources))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""產出首頁「定位找鄉鎮」用的鄉鎮界線查表 site/data/taiwan-towns-lookup.json。

來源＝taiwan-atlas（docs/PLAN.md 選定的行政區界圖資，MIT，源自內政部國土測繪中心
鄉鎮市區界線）的 towns-10t.json，版本釘死。只在界線要更新時手動跑一次，CI 不跑：

    python3 scripts/build_town_lookup.py            # 從 jsDelivr 抓釘死版本
    python3 scripts/build_town_lookup.py towns.json # 用本機檔

輸出格式（前端 js/locate.js 解碼）：
  s／o＝量化比例與平移（經度, 緯度）；towns[]＝{c 縣市, t 鄉鎮, r 環陣列}，
  每個環＝[x0, y0, dx1, dy1, ...] 量化整數＋差分。外環與洞不分，前端用奇偶規則判斷。
名稱一律「台」→「臺」，與 pages-index.json 對齊；每個鄉鎮頁都要對得到界線，否則 fail。
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data" / "taiwan-towns-lookup.json"
PAGES_INDEX = ROOT / "site" / "data" / "pages-index.json"
ATLAS_VERSION = "2021.9.20"
ATLAS_URL = f"https://cdn.jsdelivr.net/npm/taiwan-atlas@{ATLAS_VERSION}/towns-10t.json"


def norm(s):
    return s.replace("台", "臺")


def load_topo(argv):
    if len(argv) > 1:
        return json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    with urllib.request.urlopen(ATLAS_URL, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv):
    topo = load_topo(argv)
    arcs = []
    for a in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in a:
            x += dx
            y += dy
            pts.append((x, y))
        arcs.append(pts)

    def arc(i):
        return arcs[i] if i >= 0 else arcs[~i][::-1]

    def ring(idx):
        out = []
        for k, i in enumerate(idx):
            p = arc(i)
            out.extend(p if k == 0 else p[1:])
        return out

    towns = []
    for g in topo["objects"]["towns"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        enc = []
        for poly in polys:
            for idx in poly:
                r = ring(idx)
                d = [r[0][0], r[0][1]]
                for (a, b), (c, e) in zip(r, r[1:]):
                    d += [c - a, e - b]
                enc.append(d)
        towns.append({
            "c": norm(g["properties"]["COUNTYNAME"]),
            "t": norm(g["properties"]["TOWNNAME"]),
            "r": enc,
        })

    # fail-fast：每個鄉鎮頁都要對得到一塊界線，否則定位永遠只會退回縣市頁。
    have = {(t["c"], t["t"]) for t in towns}
    pages = json.loads(PAGES_INDEX.read_text(encoding="utf-8"))["pages"]
    missing = [p["id"] for p in pages
               if p["county"] != "臺灣" and p["name"] != p["county"]
               and (norm(p["county"]), norm(p["name"])) not in have]
    if missing:
        sys.exit(f"鄉鎮頁對不到界線：{missing}")

    tf = topo["transform"]
    out = {
        "_source": f"taiwan-atlas {ATLAS_VERSION}（MIT, dkaoster）← 內政部國土測繪中心鄉鎮市區界線"
                   "（政府資料開放授權條款第 1 版）；由 scripts/build_town_lookup.py 產出",
        "s": tf["scale"],
        "o": tf["translate"],
        "towns": towns,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫出 {OUT.relative_to(ROOT)}：{len(towns)} 鄉鎮市區，{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv)

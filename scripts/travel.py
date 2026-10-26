#!/usr/bin/env python3
"""
旅遊地圖（首頁「旅遊地圖」分頁）— 分區資料 → 靜態頁

資料：travel/<city>/zones.yaml（分區規劃）＋ travel/<city>/<zone>-*.yaml（一區一檔）
產出：site/travel/<city>/index.html（城市頁）、site/travel/<city>/<zone>.html（分區頁）、
      site/data/travel-index.json（首頁分頁讀）
定位快取：travel/<city>/<zone>.geo.json（Nominatim 查到的座標；手動釘點寫在 yaml 的 ll）

產出 commit 進 repo（CI 的 build.py 不碰 site/travel/）。站上只放文字資料、不放任何圖片。

用法：
  python3 scripts/travel.py status                 # 各城市各區進度、定位覆蓋率
  python3 scripts/travel.py new kh-02              # 依 zones.yaml 產生該區 yaml 骨架
  python3 scripts/travel.py geocode kh-01          # 補定位（每秒 1 次，已查過的跳過；--retry 重查失敗的）
  python3 scripts/travel.py build                  # 重建全部旅遊頁
一區的完整流程：new → 填資料 → geocode → build → 打開頁面看 → commit＋push（CI 自動上線）
"""
import sys, re, json, time, html, argparse, urllib.parse, urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "travel"
OUT = ROOT / "site" / "travel"
OUT_INDEX = ROOT / "site" / "data" / "travel-index.json"

UA = "taiwan-geo-db-travel/1.0 (https://elliot200852-lab.github.io/taiwan-geo-db/)"
KH_BBOX = (22.40, 23.50, 120.10, 121.10)   # 高雄市大致範圍：lat_min, lat_max, lng_min, lng_max

# 類別 → 顯示名與圖釘色（色值取自 style.css 色票的同族色，太近的拉開）
CATS = {
    "start": ("起點", "#2c4459"),
    "food":  ("餐廳・夜市", "#b5473c"),
    "snack": ("小吃", "#c96a2b"),
    "noodle": ("牛肉麵", "#8f4f28"),
    "drink": ("飲料", "#c79a2e"),
    "cafe":  ("咖啡", "#6b4a35"),
    "veg":   ("素食", "#5f8a3a"),
    "gift":  ("伴手禮", "#8a5a9e"),
    "night": ("夜生活", "#3b3f8f"),
    "spa":   ("按摩", "#c0587a"),
    "shop":  ("逛街", "#9c3d6e"),
    "eco":   ("自然", "#3f7a4f"),
    "art":   ("藝文", "#b5603c"),
    "sight": ("景點", "#3f5e7a"),
    "port":  ("港・水岸", "#2b7a8f"),
    "rain":  ("雨天備案", "#5c6f86"),
    "info":  ("資訊", "#5c5850"),
}
LINE_COLOR = {"R": "#d7213f", "O": "#f39a1e", "C": "#7cb342"}

esc = lambda s: html.escape(str(s), quote=True)


# ---------- 載入 ----------
def load_city(city_id):
    plan = yaml.safe_load((DATA / city_id / "zones.yaml").read_text(encoding="utf-8"))
    return plan

def zone_file(city_id, zone):
    files = sorted((DATA / city_id).glob(f"{zone['id']}-*.yaml"))
    return files[0] if files else None

def load_zone(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def cities():
    return sorted(p.name for p in DATA.iterdir() if (p / "zones.yaml").exists())

def find_zone(zone_id):
    for c in cities():
        plan = load_city(c)
        for z in plan["zones"]:
            if z["id"] == zone_id:
                return c, plan, z
    sys.exit(f"✗ 找不到分區 {zone_id}（看 travel/*/zones.yaml）")

def iter_items(zdata):
    for sec in zdata.get("sections", []):
        for g in sec.get("groups", []):
            for it in g.get("items", []):
                yield sec, g, it

def item_key(it):
    return f"{it.get('zh','')}|{it.get('addr','')}"

def geo_path(city_id, zone_id):
    return DATA / city_id / f"{zone_id}.geo.json"


# ---------- 定位 ----------
def _nominatim(params):
    params = dict(params, format="jsonv2", limit=1, countrycodes="tw", **{"accept-language": "zh-TW"})
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(1.1)   # Nominatim 使用政策：每秒最多 1 次
    if not data:
        return None
    d = data[0]
    lat, lng = float(d["lat"]), float(d["lon"])
    a, b, c, e = KH_BBOX
    if not (a <= lat <= b and c <= lng <= e) or "高雄" not in d.get("display_name", ""):
        return None
    return lat, lng, d.get("display_name", "")

def _parse_addr(addr):
    """'新興區林森一路132之3號5樓' → ('新興區', '林森一路', '132-3')；巷弄併進路名。"""
    a = re.sub(r"^高雄市", "", addr or "")
    m = re.match(r"^(\S+?區)?(.*)$", a)
    dist, rest = (m.group(1) or ""), m.group(2)
    rest = re.sub(r"(\d+樓|B\d+|RF|對面|內|海側廣場).*$", "", rest).strip()
    mm = re.match(r"^(.*?)(\d+)(?:[之-](\d+))?號", rest)
    if not mm:
        return dist, rest, None
    road, n1, n2 = mm.group(1), mm.group(2), mm.group(3)
    return dist, road, (f"{n1}-{n2}" if n2 else n1)

ZONE_CENTER = None   # cmd_geocode 設定；界路門牌（行政區對不上）離分區中心 4 km 內才收

def _near(ll, km=4.0):
    if not ll or not ZONE_CENTER:
        return False
    dy = (ll[0] - ZONE_CENTER[0]) * 111.0
    dx = (ll[1] - ZONE_CENTER[1]) * 102.0
    return (dx * dx + dy * dy) ** 0.5 <= km

def _norm_num(t):
    return re.sub(r"號$", "", t.strip()).replace("之", "-")

def judge(it, prec, label, ll=None):
    """自動定位結果把關：回傳最後精度（house／poi／road）或 None（不收）。
    house：標籤前兩段要有同一個門牌號，否則降成 road；road：標籤要含地址的行政區；
    poi：標籤含行政區，或標籤第一段跟名稱有兩字以上重疊（跨區的界路／界河景點）。"""
    dist, road, num = _parse_addr(it.get("addr", ""))
    toks = [t.strip() for t in label.split(",")]
    in_dist = (not dist) or dist in label
    if prec == "house":
        if num and any(_norm_num(t) == num for t in toks[:2]):
            named = not re.search(r"\d", toks[0])          # 第一段是店名／館名＝OSM 有這個點
            return "house" if (in_dist or named or _near(ll)) else None
        return "road" if (in_dist and road and road.split("巷")[0] in label) else None
    if prec == "poi":
        name = (it.get("q") or re.sub(r"[（(].*?[）)]", "", it.get("zh", ""))).split()[0]
        overlap = sum(1 for ch in set(name) if ch in toks[0])
        return "poi" if (in_dist or overlap >= 2) else None
    if prec == "road":
        return "road" if in_dist else None
    return None

def geocode_item(it, city="高雄市"):
    """依序試：手動 q → 門牌（結構化）→ 店名 → 路段，每一個結果都過 judge()。回傳 dict 或 None。"""
    tried = []
    if it.get("q"):
        tried.append(("poi", {"q": f"{it['q']} {city}"}))
    dist, road, num = _parse_addr(it.get("addr", ""))
    if road and num:
        tried.append(("house", {"street": f"{num} {road}", "city": city}))
    name = re.sub(r"[（(].*?[）)]", "", it.get("zh", "")).strip()
    if name and not it.get("q"):
        tried.append(("poi", {"q": f"{name} {dist} {city}".replace("  ", " ")}))
    if road:
        tried.append(("road", {"q": f"{road} {dist} {city}".replace("  ", " ")}))
    fallback = None
    for prec, params in tried:
        try:
            hit = _nominatim(params)
        except Exception as ex:  # 網路錯就換下一個，不中斷整批
            print(f"   ! {ex}")
            hit = None
        if not hit:
            continue
        got = judge(it, prec, hit[2], hit[:2])
        rec = {"ll": [round(hit[0], 6), round(hit[1], 6)], "prec": got, "label": hit[2][:80]}
        if got in ("house", "poi"):
            return rec
        if got == "road" and not fallback:
            fallback = rec
    return fallback

def cmd_geocode(zone_id, retry=False, recheck=False):
    city_id, plan, z = find_zone(zone_id)
    path = zone_file(city_id, z)
    if not path:
        sys.exit(f"✗ {zone_id} 還沒有資料檔，先跑 new")
    zdata = load_zone(path)
    global ZONE_CENTER
    ZONE_CENTER = zdata.get("center")
    gp = geo_path(city_id, zone_id)
    cache = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else {}
    todo = []
    for _, g, it in iter_items(zdata):
        if g.get("cat") == "info" or it.get("ll"):
            continue
        k = item_key(it)
        if k in cache and cache[k] and recheck:
            v = cache[k]
            if judge(it, v["prec"], v["label"], v["ll"]) != v["prec"]:
                cache.pop(k)          # 舊結果過不了把關 → 重查
        if k in cache and (cache[k] or not retry):
            continue
        todo.append(it)
    print(f"→ {zone_id}：要查 {len(todo)} 筆（快取 {len(cache)} 筆）")
    for i, it in enumerate(todo, 1):
        r = geocode_item(it, plan.get("city", "高雄市"))
        cache[item_key(it)] = r
        print(f"  [{i}/{len(todo)}] {it.get('zh')}：{r['prec'] if r else '✗ 查無'}")
        gp.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    miss = [k for k, v in cache.items() if not v]
    print(f"✓ 完成。查無 {len(miss)} 筆：" + "、".join(k.split('|')[0] for k in miss))
    if miss:
        print("  → 在 yaml 該筆加 q:（較好查的名稱）或 ll: [緯度, 經度] 後再跑 geocode --retry")


# ---------- 輸出 ----------
def gmap_url(it, city):
    q = f"{it.get('zh','')} {city}{it.get('addr','')}" if it.get("addr") else f"{it.get('zh','')} {city}"
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)

def tel_href(tel):
    t = str(tel)
    main, _, ext = t.partition("#")
    digits = re.sub(r"\D", "", main)
    if digits.startswith("0"):
        digits = "+886" + digits[1:]
    return f"tel:{digits}" + (f",{re.sub(r'[^0-9]', '', ext)}" if ext else "")

def mrt_badges(codes):
    out = []
    for c in codes or []:
        c = str(c)
        col = LINE_COLOR.get(c[0], "#888")
        out.append(f'<span class="tv-mrt" style="--lc:{col}">{esc(c)}</span>')
    return "".join(out)

def render_item(it, cat, city, idx, pin):
    head = ""
    if it.get("n"):
        head += f'<span class="tv-no" style="--cc:{CATS[cat][1]}">{esc(it["n"])}</span>'
    head += f'<span class="tv-zh">{esc(it.get("zh",""))}</span>'
    if it.get("en"):
        head += f' <span class="tv-en">{esc(it["en"])}</span>'
    rows = []
    if it.get("addr"):
        rows.append(f'<div class="tv-row"><span class="tv-k">地址</span>'
                    f'<a href="{gmap_url(it, city)}" target="_blank" rel="noopener">{esc(it["addr"])}</a></div>')
    if it.get("mrt") or it.get("exit"):
        rows.append(f'<div class="tv-row"><span class="tv-k">捷運</span><span>{mrt_badges(it.get("mrt"))}'
                    f'{(" " + esc(it["exit"])) if it.get("exit") else ""}</span></div>')
    if it.get("hours"):
        hs = "<br>".join(esc(h) for h in it["hours"])
        rows.append(f'<div class="tv-row"><span class="tv-k">時間</span><span>{hs}</span></div>')
    if it.get("tel"):
        rows.append(f'<div class="tv-row"><span class="tv-k">電話</span>'
                    f'<a href="{tel_href(it["tel"])}">{esc(it["tel"])}</a></div>')
    if it.get("note"):
        rows.append(f'<div class="tv-note">{esc(it["note"])}</div>')
    tags = ""
    if it.get("src") == "web":
        tags += '<span class="tv-tag" title="紙本翻拍被裁掉，依飯店線上版補">線上版補</span>'
    if pin:
        approx = ' tv-pin--approx' if pin["prec"] in ("road", "interp") else ''
        tags += (f'<button type="button" class="tv-pin{approx}" data-pin="{idx}" '
                 f'title="{"約略位置（只對到路段）" if approx else "在地圖上看"}">📍 地圖</button>')
    return (f'<article class="tv-item" id="p{idx}" data-cat="{cat}">'
            f'<h4 class="tv-h">{head}</h4>{"".join(rows)}'
            f'{f"<div class=tv-tags>{tags}</div>" if tags else ""}</article>')

def page_shell(title, body, depth, extra_head="", extra_js=""):
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Noto+Serif+TC:wght@500;700;900&display=swap" rel="stylesheet">
  {extra_head}
  <link rel="stylesheet" href="{up}css/style.css">
  <link rel="stylesheet" href="{up}css/travel.css">
</head>
<body class="tv-body">
  <div class="site-bar">
    <a class="site-bar-name" href="{up}index.html">認識臺灣——人文與自然地理資料庫</a>
    <span class="site-bar-tag">旅遊地圖</span>
  </div>
  <main class="page-wrap tv-wrap">
{body}
  </main>
  <div class="geo-fab" id="geo-fab">
    <div class="geo-fab-actions">
      <button type="button" class="geo-fab-btn" data-fab="share" aria-label="分享網址" title="分享網址">⤴</button>
      <button type="button" class="geo-fab-btn" data-fab="back" aria-label="回上一頁" title="回上一頁">←</button>
    </div>
    <button type="button" class="geo-fab-toggle" aria-label="導覽選單" aria-expanded="false" title="導覽選單">◎</button>
  </div>
  <div class="copy-toast" id="copy-toast">網址已複製</div>
  <script src="{up}js/fab.js"></script>
{extra_js}
</body>
</html>
"""

def interpolate(zdata, geo):
    """只對到路段（road）的點：拿同一條路上已定位（house／poi／手動）的門牌做線性內插，精度標 interp。
    兩側都有已知門牌才內插；只有單側且門牌差 ≤ 20 號就貼著它放。都沒有就維持 road。"""
    known = {}
    for _, g, it in iter_items(zdata):
        pin = {"ll": it["ll"], "prec": "manual"} if it.get("ll") else geo.get(item_key(it))
        if not pin or pin["prec"] == "road":
            continue
        _, road, num = _parse_addr(it.get("addr", ""))
        if road and num:
            known.setdefault(road, []).append((float(num.replace("-", ".")), pin["ll"]))
    out = dict(geo)
    for _, g, it in iter_items(zdata):
        k = item_key(it)
        pin = geo.get(k)
        if it.get("ll") or not pin or pin["prec"] != "road":
            continue
        _, road, num = _parse_addr(it.get("addr", ""))
        pts = sorted(known.get(road, []))
        if not (road and num and pts):
            continue
        n = float(num.replace("-", "."))
        lo = [p for p in pts if p[0] <= n]
        hi = [p for p in pts if p[0] >= n]
        ll = None
        if lo and hi:
            (n1, a), (n2, b) = lo[-1], hi[0]
            t = 0 if n2 == n1 else (n - n1) / (n2 - n1)
            ll = [round(a[0] + (b[0] - a[0]) * t, 6), round(a[1] + (b[1] - a[1]) * t, 6)]
        else:
            nn, a = min(pts, key=lambda p: abs(p[0] - n))
            if abs(nn - n) <= 20:
                ll = a
        if ll:
            out[k] = dict(pin, ll=ll, prec="interp")
    return out

def render_zone(city_id, plan, z, zdata, geo):
    city = plan["city"]
    geo = interpolate(zdata, geo)
    pins, sec_html, toc = [], [], []
    idx = 0
    for sec in zdata.get("sections", []):
        toc.append(f'<a href="#{esc(sec["id"])}">{esc(sec["title"])}</a>')
        groups = []
        for g in sec.get("groups", []):
            cat = g.get("cat", "info")
            cards = []
            for it in g.get("items", []):
                idx += 1
                pin = None
                if it.get("ll"):
                    pin = {"ll": it["ll"], "prec": "manual"}
                else:
                    gv = geo.get(item_key(it))
                    if gv:
                        pin = gv
                if pin and cat != "info":
                    pins.append({"i": idx, "ll": pin["ll"], "prec": pin["prec"], "cat": cat,
                                 "n": it.get("n"), "zh": it.get("zh"), "addr": it.get("addr", ""),
                                 "g": gmap_url(it, city)})
                cards.append(render_item(it, cat, city, idx, pin if cat != "info" else None))
            gnote = f'<p class="tv-gnote">{esc(g["note"])}</p>' if g.get("note") else ""
            groups.append(f'<section class="tv-group"><h3 class="tv-gh" style="--cc:{CATS.get(cat, CATS["info"])[1]}">'
                          f'{esc(g["name"])}</h3>{gnote}<div class="tv-grid">{"".join(cards)}</div></section>')
        lead = f'<p class="tv-lead">{esc(sec["lead"])}</p>' if sec.get("lead") else ""
        sec_html.append(f'<section class="tv-sec" id="{esc(sec["id"])}"><h2>{esc(sec["title"])}</h2>{lead}{"".join(groups)}</section>')

    # 捷運
    tr = zdata.get("transit")
    if tr:
        toc.append('<a href="#transit">捷運與輕軌</a>')
        lines = []
        for ln in tr["lines"]:
            chips = "".join(f'<span class="tv-st"><b style="--lc:{ln["color"]}">{esc(c)}</b>{esc(n)}</span>'
                            for c, n in ln["stations"])
            lines.append(f'<div class="tv-line"><h3 style="--lc:{ln["color"]}">{esc(ln["name"])}'
                         f' <small>{esc(ln["en"])}</small></h3><div class="tv-sts">{chips}</div></div>')
        tf = "".join(f"<li>{esc(t)}</li>" for t in tr.get("transfers", []))
        note = f'<p class="tv-gnote">{esc(tr["note"])}</p>' if tr.get("note") else ""
        sec_html.append(f'<section class="tv-sec" id="transit"><h2>捷運與輕軌</h2>{"".join(lines)}'
                        f'<h3 class="tv-gh">轉乘與怎麼到</h3><ul class="tv-tf">{tf}</ul>{note}</section>')

    used = []
    for p in pins:
        if p["cat"] not in used:
            used.append(p["cat"])
    chips = "".join(f'<button type="button" class="tv-chip on" data-cat="{c}" style="--cc:{CATS[c][1]}">{CATS[c][0]}</button>'
                    for c in used)
    n_items = sum(1 for _, g, _it in iter_items(zdata) if g.get("cat") != "info")
    n_pins = len(pins)
    n_road = sum(1 for p in pins if p["prec"] in ("road", "interp"))
    body = f"""
    <nav class="crumbs"><a href="../../index.html#travel">旅遊地圖</a> › <a href="index.html">{esc(city)}</a> › <strong>第 {z['order']} 區</strong></nav>
    <header class="tv-head">
      <p class="eyebrow">旅遊地圖・{esc(city)}・第 {z['order']} 區</p>
      <h1>{esc(zdata['name'])}</h1>
      <p class="tv-sub">{esc(zdata.get('subtitle',''))}</p>
    </header>
    <div class="tv-mapbox">
      <div id="tv-map" aria-label="分區地圖"></div>
      <div class="tv-chips" id="tv-chips">{chips}</div>
      <p class="tv-mapnote">共 {n_items} 筆，地圖上 {n_pins} 點（{n_road} 點只對到路段、位置是推估，以空心圈表示）。點地址開 Google 地圖導航最準。</p>
    </div>
    <nav class="tv-toc">{''.join(toc)}</nav>
    {''.join(sec_html)}
    <footer class="tv-foot">
      <p>資料來源：{esc(zdata.get('source',''))}。營業時間僅供參考，請依現場為主。</p>
      <p>地圖底圖 © OpenStreetMap 貢獻者；定位用 Nominatim 自動比對，可能有偏差。最後更新 {esc(zdata.get('updated',''))}。</p>
    </footer>
"""
    head = '<link rel="stylesheet" href="../../vendor/leaflet.css">'
    js = f"""  <script src="../../vendor/leaflet.js"></script>
  <script>window.TV_PINS = {json.dumps(pins, ensure_ascii=False)}; window.TV_CATS = {json.dumps({k: v[1] for k, v in CATS.items()})};
  window.TV_VIEW = {json.dumps({"center": zdata.get("center"), "zoom": zdata.get("zoom", 14)})};</script>
  <script src="../../js/travel.js"></script>"""
    return page_shell(f"{zdata['name']}｜{city}旅遊地圖 — 認識臺灣", body, 2, head, js)

def render_city(city_id, plan, built):
    cards = []
    for z in plan["zones"]:
        done = z["id"] in built
        st = {"done": "已上線", "next": "下一區", "planned": "規劃中"}.get(z.get("status"), "")
        if done:
            st = "已上線"
        tag = f'<span class="tv-st-tag tv-st-{ "done" if done else z.get("status","planned")}">{st}</span>'
        dist = "・".join(z.get("districts", []))
        inner = (f'<div class="tv-zc-h"><span class="tv-zc-no">{z["order"]}</span>'
                 f'<span class="tv-zc-name">{esc(z["name"])}</span>{tag}</div>'
                 f'<div class="tv-zc-d">{esc(dist)}</div><p class="tv-zc-s">{esc(z.get("scope",""))}</p>')
        if done:
            cards.append(f'<a class="tv-zc tv-zc--on" href="{z["id"]}.html">{inner}</a>')
        else:
            cards.append(f'<div class="tv-zc">{inner}</div>')
    body = f"""
    <nav class="crumbs"><a href="../../index.html#travel">旅遊地圖</a> › <strong>{esc(plan['city'])}</strong></nav>
    <header class="tv-head">
      <p class="eyebrow">旅遊地圖</p>
      <h1>{esc(plan['city'])}</h1>
      <p class="tv-sub">{esc(plan.get('intro',''))}</p>
    </header>
    <div class="tv-zones">{''.join(cards)}</div>
"""
    return page_shell(f"{plan['city']}旅遊地圖 — 認識臺灣", body, 2)

def cmd_build():
    index = {"cities": []}
    for c in cities():
        plan = load_city(c)
        built = {}
        for z in plan["zones"]:
            path = zone_file(c, z)
            if not path:
                continue
            zdata = load_zone(path)
            gp = geo_path(c, z["id"])
            geo = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else {}
            out = OUT / c / f"{z['id']}.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(render_zone(c, plan, z, zdata, geo), encoding="utf-8")
            built[z["id"]] = zdata
            print(f"  ✓ {out.relative_to(ROOT)}")
        (OUT / c / "index.html").write_text(render_city(c, plan, built), encoding="utf-8")
        print(f"  ✓ site/travel/{c}/index.html")
        index["cities"].append({
            "id": c, "name": plan["city"], "en": plan.get("city_en", ""),
            "href": f"travel/{c}/index.html", "intro": plan.get("intro", ""),
            "zones_total": len(plan["zones"]), "zones_done": len(built),
            "zones": [{"name": z["name"], "href": f"travel/{c}/{z['id']}.html", "order": z["order"]}
                      for z in plan["zones"] if z["id"] in built],
        })
    OUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✓ {OUT_INDEX.relative_to(ROOT)}")

def cmd_status():
    for c in cities():
        plan = load_city(c)
        print(f"== {plan['city']} ==")
        for z in plan["zones"]:
            path = zone_file(c, z)
            if path:
                zdata = load_zone(path)
                items = [it for _, g, it in iter_items(zdata) if g.get("cat") != "info"]
                gp = geo_path(c, z["id"])
                geo = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else {}
                pinned = sum(1 for it in items if it.get("ll") or geo.get(item_key(it)))
                print(f"  {z['id']} {z['name']}：{len(items)} 筆，定位 {pinned}/{len(items)}")
            else:
                print(f"  {z['id']} {z['name']}：[{z.get('status')}] 尚無資料")

SKELETON = """# 旅遊地圖・{city}・第 {order} 區：{name}
# 範圍（zones.yaml）：{scope}
# 欄位同 kh-01-central-park.yaml；查不到的欄位留空，不要猜。營業時間以官網／Google 商家頁核對。
id: {id}
city: {city}
city_id: {city_id}
order: {order}
name: {name}
subtitle: {districts}
districts: [{districts_list}]
center: [22.62, 120.30]   # 改成這區中心
zoom: 15
source: （寫資料來源）
updated: {today}

sections:
  - id: food
    title: 食
    groups:
      - name: 在地小吃
        cat: snack
        items: []
  - id: play
    title: 樂・態・藝・景・港
    groups:
      - {{name: 景點, cat: sight, items: []}}
      - {{name: 藝文, cat: art, items: []}}
      - {{name: 自然, cat: eco, items: []}}
      - {{name: 港・水岸, cat: port, items: []}}
  - id: rainy
    title: 雨天備案
    groups:
      - {{name: 雨天備案, cat: rain, items: []}}
"""

def cmd_new(zone_id):
    city_id, plan, z = find_zone(zone_id)
    if zone_file(city_id, z):
        sys.exit(f"✗ {zone_id} 已有資料檔：{zone_file(city_id, z).relative_to(ROOT)}")
    slug = re.sub(r"[^a-z0-9]+", "-", z.get("slug", "zone").lower()).strip("-") or "zone"
    path = DATA / city_id / f"{zone_id}-{slug}.yaml"
    path.write_text(SKELETON.format(
        city=plan["city"], city_id=city_id, id=zone_id, order=z["order"], name=z["name"],
        scope=z.get("scope", ""), districts="・".join(z.get("districts", [])),
        districts_list=", ".join(z.get("districts", [])), today=time.strftime("%Y-%m-%d")), encoding="utf-8")
    print(f"✓ 骨架：{path.relative_to(ROOT)}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status"); sp.add_parser("build")
    p = sp.add_parser("new"); p.add_argument("zone")
    p = sp.add_parser("geocode"); p.add_argument("zone"); p.add_argument("--retry", action="store_true", help="重查失敗的")
    p.add_argument("--recheck", action="store_true", help="快取裡過不了把關的也重查")
    a = ap.parse_args()
    if a.cmd == "status": cmd_status()
    elif a.cmd == "build": cmd_build()
    elif a.cmd == "new": cmd_new(a.zone)
    elif a.cmd == "geocode": cmd_geocode(a.zone, a.retry, a.recheck)

if __name__ == "__main__":
    main()

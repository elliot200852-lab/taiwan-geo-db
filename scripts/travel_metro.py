"""
旅遊地圖・捷運＋輕軌合併路線圖：travel/<city>/metro.yaml → site/data/metro-<city>.js

由 travel.py build 呼叫。產出的 JS 設 window.METRO = {title, svg, view, st, ...}，
前端 site/js/metro.js 拿它做「頂部導航鍵 → 全螢幕路線圖（縮放、拖曳、點站看轉乘）」。
同一城市所有頁面（城市頁＋每一區）共用這一份。
"""
import json, math, html
from pathlib import Path

import yaml

esc = lambda s: html.escape(str(s), quote=True)
W, H = 1110, 1420
R_ST, R_END = 12, 16          # 一般站／端點站圓半徑
FONT = 15                     # 站名字級


def _fillet(pts, r, closed=False):
    """折線轉角圓角化（以頂點為控制點的二次曲線）。"""
    n = len(pts)
    if n < 3 and not closed:
        return "M" + " L".join(f"{x},{y}" for x, y in pts)

    def cut(a, b, d):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        d = min(d, L / 2)
        return (a[0] + dx * d / L, a[1] + dy * d / L)

    seq = pts + [pts[0], pts[1]] if closed else pts
    out = []
    if closed:
        start = cut(seq[0], seq[1], r)
        out.append(f"M{start[0]:.1f},{start[1]:.1f}")
        rng = range(1, len(seq) - 1)
    else:
        out.append(f"M{pts[0][0]},{pts[0][1]}")
        rng = range(1, n - 1)
    for i in rng:
        p, c, nx = seq[i - 1], seq[i], seq[i + 1]
        a, b = cut(c, p, r), cut(c, nx, r)
        out.append(f"L{a[0]:.1f},{a[1]:.1f} Q{c[0]},{c[1]} {b[0]:.1f},{b[1]:.1f}")
    if closed:
        out.append("Z")
    else:
        out.append(f"L{pts[-1][0]},{pts[-1][1]}")
    return " ".join(out)


def _snap(pt, pts, closed=False):
    """站點吸附到路線折線上最近的點。"""
    segs = list(zip(pts, pts[1:] + ([pts[0]] if closed else [])))
    best, bd = pt, 1e9
    for a, b in segs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy or 1
        t = max(0, min(1, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / L2))
        q = (a[0] + t * dx, a[1] + t * dy)
        d = math.hypot(q[0] - pt[0], q[1] - pt[1])
        if d < bd:
            best, bd = q, d
    return (round(best[0], 1), round(best[1], 1)) if bd < 14 else pt


def _split(name):
    if "(" in name:
        main, _, rest = name.partition("(")
        return main, "(" + rest
    return name, ""


def _label(x, y, name, spec, r, size=FONT, fill="#2b2a26", weight=700):
    if spec in ("-", None, ""):
        return ""
    side, _, rest = str(spec).partition(":")
    off, _, dy = rest.partition(":")
    d = float(off) if off else r + 6
    y += float(dy) if dy else 0
    main, sub = _split(name)
    sub_small = f'<tspan font-size="{size * .66:.0f}" font-weight="500">{esc(sub)}</tspan>' if sub else ""
    if side == "rot":
        return (f'<text class="mt-lb" transform="translate({x + r * .55:.1f},{y - r * .95:.1f}) rotate(-45)" '
                f'font-size="{size}" font-weight="{weight}" fill="{fill}">{esc(main)}{sub_small}</text>')
    k = .72
    pos = {
        "l": (x - d, y + size * .35, "end"), "r": (x + d, y + size * .35, "start"),
        "t": (x, y - d + 2, "middle"), "b": (x, y + d + size * .8, "middle"),
        "tl": (x - d * k, y - d * k, "end"), "tr": (x + d * k, y - d * k, "start"),
        "bl": (x - d * k, y + d * k + size * .7, "end"), "br": (x + d * k, y + d * k + size * .7, "start"),
    }[side]
    tx, ty, anc = pos
    if sub and side in ("l", "r"):
        return (f'<text class="mt-lb" x="{tx:.1f}" y="{ty - 5:.1f}" text-anchor="{anc}" font-size="{size}" '
                f'font-weight="{weight}" fill="{fill}">{esc(main)}'
                f'<tspan x="{tx:.1f}" dy="{size * .85:.1f}" font-size="{size * .66:.0f}" font-weight="500">{esc(sub)}</tspan></text>')
    return (f'<text class="mt-lb" x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anc}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}">{esc(main)}{sub_small}</text>')


def build_svg(m):
    lines = {ln["id"]: ln for ln in m["lines"]}
    pair_of = {}
    for a, b in m.get("transfers", []):
        pair_of[a] = b
        pair_of[b] = a

    # 站點座標
    st = {}
    for ln in m["lines"]:
        pts = [tuple(p) for p in ln["path"]]
        for code, name, x, y, lab in ln["stations"]:
            xy = (x, y) if code in pair_of else _snap((x, y), pts, ln.get("loop", False))
            st[code] = {"zh": name, "line": ln["id"], "xy": xy, "lab": lab}

    rail, track, boxes, dots, labels = [], [], [], [], []

    # 臺鐵、高鐵（底層虛線）
    for rl in m.get("rail", []):
        d = _fillet([tuple(p) for p in rl["path"]], 30)
        rail.append(f'<path d="{d}" fill="none" stroke="{rl["color"]}" stroke-width="7" stroke-linejoin="round"/>'
                    f'<path d="{d}" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="9 7"/>')
        for name, x, y, lab in rl.get("stations", []):
            rail.append(f'<g class="mt-tra"><circle cx="{x}" cy="{y}" r="8" fill="#fff" stroke="{rl["color"]}" stroke-width="3"/>'
                        f'<text x="{x}" y="{y + 3.5}" text-anchor="middle" font-size="9" font-weight="700" fill="{rl["color"]}">鐵</text></g>')
            labels.append(_label(x, y, name, lab, 8, size=11, fill="#6f6b8c", weight=500))

    # 捷運、輕軌
    for ln in m["lines"]:
        d = _fillet([tuple(p) for p in ln["path"]], 34, ln.get("loop", False))
        track.append(f'<path class="mt-track" data-line="{ln["id"]}" d="{d}" fill="none" stroke="{ln["color"]}" '
                     f'stroke-width="10" stroke-linejoin="round" stroke-linecap="round"/>')

    # 轉乘框
    for a, b in m.get("transfers", []):
        (ax, ay), (bx, by) = st[a]["xy"], st[b]["xy"]
        x0, x1 = min(ax, bx) - R_ST - 5, max(ax, bx) + R_ST + 5
        boxes.append(f'<rect x="{x0}" y="{ay - R_ST - 5}" width="{x1 - x0}" height="{2 * R_ST + 10}" rx="7" '
                     f'fill="#fff" stroke="#2b2a26" stroke-width="2.5"/>')

    # 站
    for ln in m["lines"]:
        codes = [s[0] for s in ln["stations"]]
        ends = set() if ln.get("loop") else {codes[0], codes[-1]}
        for code in codes:
            s = st[code]
            x, y = s["xy"]
            col = ln["color"]
            end = code in ends and code not in pair_of
            r = R_END if end else R_ST
            fs = 11 if end else (8 if len(code) >= 4 else 9.5)
            circ = (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{col}"/>' if end else
                    f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{col}" stroke-width="3.5"/>')
            tcol = "#fff" if end else "#2b2a26"
            dots.append(f'<g class="mst" data-c="{code}"><circle class="mt-hit" cx="{x}" cy="{y}" r="22" fill="transparent"/>'
                        f'{circ}<text x="{x}" y="{y + fs * .36:.1f}" text-anchor="middle" font-size="{fs}" '
                        f'font-weight="800" fill="{tcol}">{esc(code)}</text></g>')
            lab = _label(x, y, s["zh"], s["lab"], r)
            if lab:
                labels.append(lab.replace('class="mt-lb"', f'class="mt-lb" data-c="{code}"', 1))

    marks = []
    for mk in m.get("marks", []):
        marks.append(f'<text x="{mk["x"]}" y="{mk["y"]}" text-anchor="{mk.get("anchor", "start")}" font-size="13" '
                     f'font-weight="700" fill="#3f5e7a">{esc(mk["text"])}</text>')
        if mk.get("sub"):
            marks.append(f'<text x="{mk["x"]}" y="{mk["y"] + 15}" font-size="11" fill="#3f5e7a">{esc(mk["sub"])}</text>')

    # 圖例
    lg = [f'<g class="mt-legend" transform="translate(660,70)">',
          '<rect width="400" height="318" rx="16" fill="#fff" stroke="#e1dccf" stroke-width="2"/>',
          f'<text x="28" y="48" font-size="26" font-weight="900" fill="#2b2a26">{esc(m.get("title", "路線圖"))}</text>']
    yy = 92
    for ln in m["lines"]:
        lg.append(f'<line x1="28" y1="{yy - 5}" x2="88" y2="{yy - 5}" stroke="{ln["color"]}" stroke-width="10" stroke-linecap="round"/>'
                  f'<text x="102" y="{yy}" font-size="19" font-weight="800" fill="#2b2a26">{esc(ln["name"])}'
                  f'<tspan font-size="14" font-weight="500" fill="#5c5850">　{esc(ln.get("sub", ""))}</tspan></text>')
        yy += 38
    lg.append(f'<rect x="28" y="{yy - 20}" width="60" height="30" rx="6" fill="#fff" stroke="#2b2a26" stroke-width="2.5"/>'
              f'<circle cx="45" cy="{yy - 5}" r="9" fill="#fff" stroke="#e0004d" stroke-width="3"/>'
              f'<circle cx="71" cy="{yy - 5}" r="9" fill="#fff" stroke="#7ac143" stroke-width="3"/>'
              f'<text x="102" y="{yy}" font-size="17" font-weight="700" fill="#2b2a26">轉乘站（框起來的兩站同一站）</text>')
    yy += 40
    for rl in m.get("rail", []):
        lg.append(f'<line x1="28" y1="{yy - 5}" x2="88" y2="{yy - 5}" stroke="{rl["color"]}" stroke-width="7"/>'
                  f'<line x1="28" y1="{yy - 5}" x2="88" y2="{yy - 5}" stroke="#fff" stroke-width="3" stroke-dasharray="9 7"/>'
                  f'<text x="102" y="{yy}" font-size="17" font-weight="700" fill="#2b2a26">{esc(rl["name"])}</text>')
        yy += 32
    lg.append(f'<circle cx="58" cy="{yy - 5}" r="14" fill="none" stroke="#2c4459" stroke-width="4"/>'
              f'<text x="102" y="{yy}" font-size="17" font-weight="700" fill="#2c4459">本頁這一區在這裡</text>')
    lg.append("</g>")

    svg = (f'<svg class="mt-svg" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="{esc(m.get("title", ""))}">'
           f'<rect width="{W}" height="{H}" fill="#fffdf7"/>'
           f'{"".join(rail)}{"".join(track)}{"".join(boxes)}<g class="mt-here-layer"></g>{"".join(dots)}'
           f'{"".join(labels)}{"".join(marks)}{"".join(lg)}</svg>')
    return svg, st


def build_metro(root, city_id, plan, built):
    """有 travel/<city>/metro.yaml 才產；回傳前端 script 的站內路徑（相對 site/），沒有就回 None。"""
    src = root / "travel" / city_id / "metro.yaml"
    if not src.exists():
        return None
    m = yaml.safe_load(src.read_text(encoding="utf-8"))
    svg, st = build_svg(m)
    colors = {ln["id"]: ln["color"] for ln in m["lines"]}
    names = {ln["id"]: ln["name"] for ln in m["lines"]}
    notes = m.get("notes", {})

    # 哪些分區用到這站（zones.yaml 的 stations）
    zones_at = {}
    for z in plan["zones"]:
        for c in z.get("stations", []):
            zones_at.setdefault(c, []).append({"order": z["order"], "name": z["name"],
                                               "href": f'{z["id"]}.html' if z["id"] in built else None})
    unknown = sorted({c for z in plan["zones"] for c in z.get("stations", []) if c not in st})
    if unknown:
        raise SystemExit(f"✗ zones.yaml 有 metro.yaml 沒有的站號：{', '.join(unknown)}")

    out_st = {}
    for code, s in st.items():
        out_st[code] = {"zh": s["zh"], "l": s["line"], "xy": s["xy"]}
        if notes.get(code):
            out_st[code]["note"] = notes[code]
        if zones_at.get(code):
            out_st[code]["zones"] = zones_at[code]
    data = {"title": m.get("title", ""), "updated": str(m.get("updated", "")), "source": m.get("source", ""),
            "view": [0, 0, W, H], "colors": colors, "names": names, "st": out_st, "svg": svg}
    out = root / "site" / "data" / f"metro-{city_id}.js"
    out.write_text("/* 由 scripts/travel.py build 依 travel/" + city_id + "/metro.yaml 產生，勿手改 */\n"
                   "window.METRO = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"  ✓ {out.relative_to(root)}（{len(st)} 站）")
    return f"data/metro-{city_id}.js"

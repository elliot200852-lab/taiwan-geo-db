#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
認識臺灣地理資料庫 — 內容頁建置器
把 content/{county}/{unit}.md（frontmatter + 章節）轉成 site/pages/{id}.html，
並輸出 site/data/pages-index.json 供首頁地圖判斷哪些區已有內容。

用法：
    python3 scripts/build.py            # 掃 content/，建有什麼建什麼
掃到什麼建什麼；content/ 為空時只清空 pages/ 並寫出空索引。
規範見 docs/CONTENT-SPEC.md。
"""
import sys, os, re, json, html
from pathlib import Path

try:
    import markdown
    import yaml
except ImportError as e:
    sys.exit(f"缺少依賴：{e.name}。請先 `pip install -r requirements.txt`"
             f"（建議用 venv：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt）")

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
OUT_PAGES = ROOT / "site" / "pages"
OUT_INDEX = ROOT / "site" / "data" / "pages-index.json"
OUT_THEMES = ROOT / "site" / "data" / "themes-index.json"
IMG_MANIFEST = ROOT / "site" / "img" / "manifest.json"

# 主題頁（通論地理，橫看全島）放在 content/themes/ 下；縣市/鄉鎮頁（區域地理）放其餘資料夾。
THEME_DIR = "themes"

def is_theme(path):
    return path.parent.name == THEME_DIR

MD = markdown.Markdown(extensions=["extra", "sane_lists"])

# 原始 URL -> 本地相對路徑（相對 site/ 根，例 "img/yilan-dongshan/00.webp"）
# 由 scripts/fetch_images.py 維護；缺檔時退回原 URL 並印警告。
def load_img_manifest():
    if IMG_MANIFEST.exists():
        try:
            return json.loads(IMG_MANIFEST.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! 讀 manifest 失敗，改用原始 URL：{e}")
    return {}

IMG_MAP = load_img_manifest()

def md2html(text):
    MD.reset()
    return MD.convert(text.strip()) if text and text.strip() else ""

def esc(s):
    return html.escape(str(s), quote=True)

# ---- 解析母本 ----
def parse_file(path):
    raw = path.read_text(encoding="utf-8")
    fm, body = {}, raw
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if m:
        fm = yaml.safe_load(m.group(1)) or {}
        body = m.group(2)
    # 依 level-2 標題切章節
    sections = {}
    cur = None
    buf = []
    for line in body.splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            if cur is not None:
                sections[cur] = "\n".join(buf).strip()
            cur = h.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if cur is not None:
        sections[cur] = "\n".join(buf).strip()
    return fm, sections

# ---- 五年級 badge ----
def badgeify(html_str):
    html_str = html_str.replace("【五年級地理】", '<span class="badge">五年級地理</span> ')
    html_str = html_str.replace("【五年級歷史】", '<span class="badge hist">五年級歷史</span> ')
    return html_str

# ---- 圖片 ----
def resolve_src(raw_url):
    """有本地 webp 就用相對路徑（pages/ 下 -> ../img/...），否則保留原 URL 並警告。"""
    local = IMG_MAP.get((raw_url or "").strip())
    if local:
        return f"../{local}"
    if raw_url:
        print(f"  ! 無本地 webp，保留原 URL：{raw_url[:80]}")
    return raw_url


def figure_html(img):
    url = esc(resolve_src(img.get("url", "")))
    title = img.get("title", "")
    author = img.get("author", "")
    license_ = img.get("license", "")
    source = img.get("source", "")
    bits = []
    if title:
        bits.append(f'<span class="cap-title">{esc(title)}</span>')
    meta = " · ".join(esc(x) for x in [author, license_, source] if x)
    if meta:
        bits.append(meta)
    cap = "<br>".join(bits)
    return (f'<figure class="geo-fig"><img src="{url}" alt="{esc(title)}" loading="lazy">'
            f'<figcaption>{cap}</figcaption></figure>')

def figures_for(images, section_name):
    return "\n".join(figure_html(i) for i in images
                     if (i.get("section") or "").strip() == section_name)

def figures_unplaced(images, placed_sections):
    """回傳未掛在指定章節（含空 section）的圖片 figure HTML。"""
    figs = [i for i in images if (i.get("section") or "").strip() not in placed_sections]
    if not figs:
        return ""
    inner = "\n".join(figure_html(i) for i in figs)
    return (f'<section class="gallery"><h2>圖像</h2>'
            f'<div class="gallery-grid">{inner}</div></section>')

# ---- 交叉連結：縣市頁反向注入的「延伸主題」chips ----
def related_themes_block(related):
    """related：[{theme_id, chip, hook}]。渲染成縣市頁的延伸主題 chip 列。"""
    if not related:
        return ""
    chips = "\n".join(
        f'<a class="theme-chip" href="{esc(r["theme_id"])}.html" '
        f'title="{esc(r.get("hook",""))}">{esc(r["chip"])}</a>'
        for r in related
    )
    return (
        '<section class="related-themes">'
        '<h2>延伸主題</h2>'
        '<p class="rt-note">從這個地方，橫看全臺灣的地理現象：</p>'
        f'<div class="theme-chips">{chips}</div></section>'
    )

# ---- 組頁 ----
def render_page(fm, sections, related_themes=None):
    name = esc(fm.get("name", "（未命名）"))
    county = esc(fm.get("county", ""))
    unit_type = esc(fm.get("type", ""))
    eyebrow = " · ".join(x for x in [county, unit_type] if x)

    stats = fm.get("stats") or {}
    stat_labels = {"population": "人口", "area_km2": "面積 (km²)", "density": "人口密度"}
    stat_cards = "".join(
        f'<div class="stat-card"><div class="k">{stat_labels.get(k, esc(k))}</div>'
        f'<div class="v">{esc(v)}</div></div>'
        for k, v in stats.items() if v
    )
    stat_block = f'<div class="stats">{stat_cards}</div>' if stat_cards else ""

    lede = md2html(sections.get("定位速覽", ""))

    images = fm.get("images") or []
    nature_html = md2html(sections.get("自然地理", "")) + figures_for(images, "自然地理")
    human_html = md2html(sections.get("人文地理", "")) + figures_for(images, "人文地理")

    teaching_html = badgeify(md2html(sections.get("教學特點", "")))
    story_html = md2html(sections.get("說書稿切分提示", ""))

    # 未指定 section 的圖片 → 圖像廊
    placed = {"自然地理", "人文地理"}
    gallery_imgs = [i for i in images if (i.get("section") or "").strip() not in placed]
    gallery_html = ""
    if gallery_imgs:
        figs = "\n".join(figure_html(i) for i in gallery_imgs)
        gallery_html = (f'<section class="gallery"><h2>圖像</h2>'
                        f'<div class="gallery-grid">{figs}</div></section>')

    # 頁尾來源
    sources = fm.get("sources") or []
    src_items = "\n".join(
        f'<li><a href="{esc(s)}" target="_blank" rel="noopener">{esc(s)}</a></li>'
        for s in sources
    )
    src_block = f'<h3>資料來源</h3><ul>{src_items}</ul>' if src_items else ""

    # 頂部 sticky 導航列：宜蘭鄉鎮頁回宜蘭、其餘回臺灣地圖
    county_raw = fm.get("county", "")
    if county_raw == "宜蘭縣":
        back_href, back_label = "../index.html?county=宜蘭縣", "回到宜蘭縣"
    else:
        back_href, back_label = "../index.html", "回臺灣地圖"
    topbar = (
        '<nav class="topbar">'
        '<button type="button" class="nav-btn" onclick="history.back()">&larr; 上一頁</button>'
        f'<a class="nav-btn" href="{back_href}">{back_label}</a>'
        '<button type="button" class="nav-btn" id="share-btn">分享網址</button>'
        '<button type="button" class="nav-btn" onclick="location.reload()">重新整理</button>'
        '</nav>'
    )

    teaching_section = ""
    if teaching_html:
        teaching_section = (
            '<section class="teaching">'
            '<h2>教學特點</h2>'
            '<p class="core-note">本資料庫的核心：探究問題、跨科連結，與可直接帶進五年級課堂的素材。</p>'
            f'{teaching_html}</section>'
        )

    story_section = ""
    if story_html:
        story_section = (f'<section class="storyteller"><h2>說書稿切分提示</h2>{story_html}</section>')

    # 有延伸主題才佔位；無則零位元組（避免對未連結的縣市頁造成空白行 diff）
    related_html = related_themes_block(related_themes)
    related_block = (related_html + "\n\n    ") if related_html else ""

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} — 認識臺灣</title>
  <link rel="stylesheet" href="../css/style.css">
</head>
<body>
  <div class="page-wrap">
    {topbar}

    <header class="page-header">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{name}</h1>
      <div class="lede">{lede}</div>
      {stat_block}
    </header>

    <div class="geo-cols">
      <section class="geo-block nature">
        <h2>自然地理</h2>
        {nature_html}
      </section>
      <section class="geo-block human">
        <h2>人文地理</h2>
        {human_html}
      </section>
    </div>

    {teaching_section}

    {story_section}

    {related_block}{gallery_html}

    <footer class="page-foot">
      {src_block}
      <div class="credit">
        圖資：內政部國土測繪中心／dkaoster taiwan-atlas（MIT 授權）。
        圖片版權屬各原作者，授權標示如圖說。本頁為教師備課資料庫。
      </div>
    </footer>
  </div>

  <div class="copy-toast" id="copy-toast">已複製連結</div>
  <script>
    (function () {{
      var btn = document.getElementById('share-btn');
      var toast = document.getElementById('copy-toast');
      if (!btn) return;
      function showToast() {{
        if (!toast) return;
        toast.classList.add('show');
        setTimeout(function () {{ toast.classList.remove('show'); }}, 1500);
      }}
      btn.addEventListener('click', function () {{
        var url = window.location.href;
        if (navigator.share) {{
          navigator.share({{ title: document.title, url: url }}).catch(function () {{}});
        }} else if (navigator.clipboard) {{
          navigator.clipboard.writeText(url).then(showToast).catch(function () {{}});
        }}
      }});
    }})();
  </script>
</body>
</html>
"""

# ---- 組主題頁（通論地理，橫看全島）----
THEME_SPECIAL = {"定位速覽", "教學特點", "說書稿切分提示"}

def region_locator_block(regions, region_names):
    """主題頁 → 縣市頁：把 frontmatter 的 regions 渲染成「這個現象在哪裡看得到」。"""
    if not regions:
        return ""
    cards = []
    for r in regions:
        rid = (r.get("id") or "").strip()
        if not rid:
            continue
        label = region_names.get(rid, r.get("name") or rid)
        hook = r.get("hook", "")
        cards.append(
            f'<a class="locator-card" href="{esc(rid)}.html">'
            f'<span class="loc-place">{esc(label)}</span>'
            f'<span class="loc-hook">{esc(hook)}</span></a>'
        )
    if not cards:
        return ""
    return (
        '<section class="locator">'
        '<h2>這個現象在哪裡看得到</h2>'
        '<div class="locator-grid">' + "\n".join(cards) + '</div></section>'
    )

def render_theme(fm, sections, region_names):
    name = esc(fm.get("name", "（未命名主題）"))
    layer = fm.get("layer", "")
    layer_sub = fm.get("layer_sub", "")
    theme_group = fm.get("theme_group", "")
    eyebrow = " · ".join(esc(x) for x in [layer, layer_sub, theme_group] if x)

    lede = md2html(sections.get("定位速覽", ""))
    images = fm.get("images") or []

    # 正文章節：依文件順序渲染（排除定位速覽/教學特點/說書稿），圖片依 section 掛入
    body_parts = []
    body_sections = []
    for title, content in sections.items():
        if title in THEME_SPECIAL:
            continue
        body_sections.append(title)
        inner = md2html(content) + figures_for(images, title)
        body_parts.append(
            f'<section class="theme-block"><h2>{esc(title)}</h2>{inner}</section>'
        )
    body_html = "\n".join(body_parts)

    teaching_inner = badgeify(md2html(sections.get("教學特點", "")))
    teaching_section = ""
    if teaching_inner:
        teaching_section = (
            '<section class="teaching"><h2>教學特點</h2>'
            '<p class="core-note">本資料庫的核心：探究問題、跨科連結，與可直接帶進五年級課堂的素材。</p>'
            f'{teaching_inner}</section>'
        )

    story_inner = md2html(sections.get("說書稿切分提示", ""))
    story_section = (
        f'<section class="storyteller"><h2>說書稿切分提示</h2>{story_inner}</section>'
        if story_inner else ""
    )

    locator_html = region_locator_block(fm.get("regions") or [], region_names)

    # 未掛章節的圖片 → 圖像廊
    placed = set(body_sections)
    gallery_html = figures_unplaced(images, placed)

    sources = fm.get("sources") or []
    src_items = "\n".join(
        f'<li><a href="{esc(s)}" target="_blank" rel="noopener">{esc(s)}</a></li>'
        for s in sources
    )
    src_block = f'<h3>資料來源</h3><ul>{src_items}</ul>' if src_items else ""

    topbar = (
        '<nav class="topbar">'
        '<button type="button" class="nav-btn" onclick="history.back()">&larr; 上一頁</button>'
        '<a class="nav-btn" href="../index.html#themes">回主題總覽</a>'
        '<a class="nav-btn" href="../index.html">回臺灣地圖</a>'
        '<button type="button" class="nav-btn" id="share-btn">分享網址</button>'
        '<button type="button" class="nav-btn" onclick="location.reload()">重新整理</button>'
        '</nav>'
    )

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} — 認識臺灣</title>
  <link rel="stylesheet" href="../css/style.css">
</head>
<body>
  <div class="page-wrap theme-page">
    {topbar}

    <header class="page-header">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{name}</h1>
      <div class="lede">{lede}</div>
    </header>

    {body_html}

    {teaching_section}

    {locator_html}

    {story_section}

    {gallery_html}

    <footer class="page-foot">
      {src_block}
      <div class="credit">
        圖資：內政部國土測繪中心／dkaoster taiwan-atlas（MIT 授權）。
        圖片版權屬各原作者，授權標示如圖說。本頁為教師備課資料庫。
      </div>
    </footer>
  </div>

  <div class="copy-toast" id="copy-toast">已複製連結</div>
  <script>
    (function () {{
      var btn = document.getElementById('share-btn');
      var toast = document.getElementById('copy-toast');
      if (!btn) return;
      function showToast() {{
        if (!toast) return;
        toast.classList.add('show');
        setTimeout(function () {{ toast.classList.remove('show'); }}, 1500);
      }}
      btn.addEventListener('click', function () {{
        var url = window.location.href;
        if (navigator.share) {{
          navigator.share({{ title: document.title, url: url }}).catch(function () {{}});
        }} else if (navigator.clipboard) {{
          navigator.clipboard.writeText(url).then(showToast).catch(function () {{}});
        }}
      }});
    }})();
  </script>
</body>
</html>
"""

def main():
    OUT_PAGES.mkdir(parents=True, exist_ok=True)
    # 清掉舊 pages（只清 .html，保留其他）
    for old in OUT_PAGES.glob("*.html"):
        old.unlink()

    md_files = sorted(CONTENT.rglob("*.md")) if CONTENT.exists() else []

    # ---- 第一遍：解析所有母本，分出區域頁與主題頁，建反向索引 ----
    regions_parsed = []     # [(path, fm, sections)]
    themes_parsed = []      # [(path, fm, sections)]
    seen = {}
    region_names = {}       # id -> name（供主題頁 locator 顯示地名）
    for path in md_files:
        try:
            fm, sections = parse_file(path)
        except Exception as e:
            print(f"  ! 解析失敗 {path.relative_to(ROOT)}: {e}")
            continue
        pid = fm.get("id")
        if not pid:
            print(f"  ! 略過（frontmatter 無 id）：{path.relative_to(ROOT)}")
            continue
        if pid in seen:
            print(f"  ! 略過（id「{pid}」與 {seen[pid]} 重複）：{path.relative_to(ROOT)}")
            continue
        seen[pid] = str(path.relative_to(ROOT))
        if is_theme(path):
            themes_parsed.append((path, fm, sections))
        else:
            regions_parsed.append((path, fm, sections))
            region_names[pid] = fm.get("name", "")

    # 反向索引：region_id -> [{theme_id, chip, hook}]（主題頁 frontmatter 是唯一來源，縣市母本零改動）
    reverse = {}
    for path, fm, _ in themes_parsed:
        tid = fm.get("id")
        chip = fm.get("chip_label") or fm.get("name", "")
        for r in (fm.get("regions") or []):
            rid = (r.get("id") or "").strip()
            if not rid:
                continue
            reverse.setdefault(rid, []).append(
                {"theme_id": tid, "chip": chip, "hook": r.get("hook", "")}
            )

    # ---- 第二遍：渲染 ----
    index = []
    built = 0
    for path, fm, sections in regions_parsed:
        pid = fm["id"]
        out = OUT_PAGES / f"{pid}.html"
        out.write_text(render_page(fm, sections, reverse.get(pid)), encoding="utf-8")
        index.append({
            "id": pid,
            "name": fm.get("name", ""),
            "county": fm.get("county", ""),
            "type": fm.get("type", ""),
        })
        built += 1
        print(f"  + {path.relative_to(ROOT)} -> site/pages/{pid}.html")

    themes_index = []
    for path, fm, sections in themes_parsed:
        pid = fm["id"]
        # 驗證 regions 指向的地名頁確實存在，缺的印警告（避免主題頁連到 404）
        for r in (fm.get("regions") or []):
            rid = (r.get("id") or "").strip()
            if rid and rid not in region_names:
                print(f"  ! 主題「{pid}」的 region「{rid}」找不到對應地名頁（會連到不存在的頁）")
        out = OUT_PAGES / f"{pid}.html"
        out.write_text(render_theme(fm, sections, region_names), encoding="utf-8")
        themes_index.append({
            "id": pid,
            "name": fm.get("name", ""),
            "layer": fm.get("layer", ""),
            "layer_sub": fm.get("layer_sub", ""),
            "theme_group": fm.get("theme_group", ""),
        })
        built += 1
        print(f"  + {path.relative_to(ROOT)} -> site/pages/{pid}.html（主題）")

    OUT_INDEX.write_text(
        json.dumps({"pages": index}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    OUT_THEMES.write_text(
        json.dumps({"themes": themes_index}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"完成：建了 {built} 頁（地名 {len(index)}、主題 {len(themes_index)}）；"
          f"索引 {OUT_INDEX.relative_to(ROOT)} + {OUT_THEMES.relative_to(ROOT)}。")

if __name__ == "__main__":
    main()

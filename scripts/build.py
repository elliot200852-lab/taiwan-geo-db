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

MD = markdown.Markdown(extensions=["extra", "sane_lists"])

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
def figure_html(img):
    url = esc(img.get("url", ""))
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

# ---- 組頁 ----
def render_page(fm, sections):
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
    <nav class="topbar"><a href="../index.html">&larr; 回地圖</a></nav>

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

    {gallery_html}

    <footer class="page-foot">
      {src_block}
      <div class="credit">
        圖資：內政部國土測繪中心／dkaoster taiwan-atlas（MIT 授權）。
        圖片版權屬各原作者，授權標示如圖說。本頁為教師備課資料庫。
      </div>
    </footer>
  </div>
</body>
</html>
"""

def main():
    OUT_PAGES.mkdir(parents=True, exist_ok=True)
    # 清掉舊 pages（只清 .html，保留其他）
    for old in OUT_PAGES.glob("*.html"):
        old.unlink()

    index = []
    seen = {}
    md_files = sorted(CONTENT.rglob("*.md")) if CONTENT.exists() else []
    built = 0
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
        out = OUT_PAGES / f"{pid}.html"
        out.write_text(render_page(fm, sections), encoding="utf-8")
        index.append({
            "id": pid,
            "name": fm.get("name", ""),
            "county": fm.get("county", ""),
            "type": fm.get("type", ""),
        })
        built += 1
        print(f"  + {path.relative_to(ROOT)} -> site/pages/{pid}.html")

    OUT_INDEX.write_text(
        json.dumps({"pages": index}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"完成：建了 {built} 頁，索引 {OUT_INDEX.relative_to(ROOT)}（{len(index)} 筆）。")

if __name__ == "__main__":
    main()

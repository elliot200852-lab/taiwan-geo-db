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
import urllib.request
from urllib.parse import urlparse
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
OUT_SEARCH = ROOT / "site" / "data" / "search-index.json"
OUT_SITEMAP = ROOT / "site" / "sitemap.xml"
IMG_MANIFEST = ROOT / "site" / "img" / "manifest.json"
SOURCE_TITLES_FILE = ROOT / "scripts" / "source-titles.yaml"

# live 站絕對網址（無結尾斜線）：og:image／sitemap.xml 的絕對 URL 都靠這個組。
SITE_BASE_URL = "https://elliot200852-lab.github.io/taiwan-geo-db"

# 反向鏈：taiwan-arts-db 人物頁（唯讀引用，見 _governance/protocols/cross-repo-reference.md）。
# 本機優先讀同層 sibling repo（~/MyWork 下兩 repo 平行放）；CI 沒有 sibling 時改抓
# GitHub raw（taiwan-arts-db 為 public repo，免憑證）。零硬編人名——arts-db 之後新增
# 人物 pin，下次 build 就自動長出對應卡片。
ARTS_DB_SIBLING = ROOT.parent / "taiwan-arts-db" / "content" / "map.yaml"
ARTS_DB_RAW_URL = "https://raw.githubusercontent.com/elliot200852-lab/taiwan-arts-db/main/content/map.yaml"
ARTS_DB_BASE = "https://elliot200852-lab.github.io/taiwan-arts-db/"

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

# 資料來源 URL -> 中文標題對照（由 scripts/fetch_source_titles.py 產生／人工補洞）。
# 屬 build 輸入而非內容，與 img manifest 同性質；缺檔或讀取失敗一律 fallback 裸 URL，
# 不得讓 build 掛掉。母本 content/**/*.md 的 sources 維持純 URL，零改動。
def load_source_titles():
    if SOURCE_TITLES_FILE.exists():
        try:
            data = yaml.safe_load(SOURCE_TITLES_FILE.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                return data
            print(f"  ! source-titles.yaml 內容非對照表格式，來源連結全部退回裸 URL")
        except Exception as e:
            print(f"  ! 讀 source-titles.yaml 失敗，來源連結全部退回裸 URL：{e}")
    return {}

SOURCE_TITLES = load_source_titles()

def source_host(url):
    """網域短形式：去 www.，供來源連結後綴顯示（如「(tcmb.culture.tw)」）。"""
    try:
        netloc = urlparse(url).netloc
    except Exception:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc

def source_link_html(url):
    """單條資料來源的 <a>：查得到中文標題就顯示「標題 (host)」，查不到就維持
    裸 URL（原行為，向下相容）。"""
    title = (SOURCE_TITLES.get(url) or "").strip()
    href = esc(url)
    if title:
        host = esc(source_host(url))
        host_span = f' <span class="src-host">({host})</span>' if host else ""
        return (f'<a href="{href}" target="_blank" rel="noopener">{esc(title)}</a>'
                f'{host_span}')
    return f'<a href="{href}" target="_blank" rel="noopener">{esc(url)}</a>'

# ---- 反向鏈資料：taiwan-arts-db 人物 pin（唯讀，arts-db 側零改動）----
def load_arts_people():
    """讀 arts-db 的 content/map.yaml，取 type=person 的 pin，依 county 分組成
    {county: [{name, hook, url}, ...]}。county 值即 geo-db 的頁面 id（已核對一致）。

    兩道 fail-fast（照 pull_images.py 的紀律，別拿掉）：
      1. 本機與 GitHub raw 都抓不到 → CI 上中止；本機允許略過（沒網路仍可看舊站）。
      2. 抓到檔案卻解析出 0 位 person pin → 一律中止（資料格式壞了，不是合法的「沒有人物」）。
    """
    raw_text, source = None, ""
    if ARTS_DB_SIBLING.exists():
        try:
            raw_text = ARTS_DB_SIBLING.read_text(encoding="utf-8")
            source = f"本機 sibling {ARTS_DB_SIBLING}"
        except Exception as e:
            print(f"  ! 讀本機 arts-db map.yaml 失敗：{e}")
    if raw_text is None:
        try:
            with urllib.request.urlopen(ARTS_DB_RAW_URL, timeout=20) as resp:
                raw_text = resp.read().decode("utf-8")
                source = f"GitHub raw {ARTS_DB_RAW_URL}"
        except Exception as e:
            msg = f"  ! 抓 arts-db map.yaml 失敗（本機 sibling 與 GitHub raw 都不通）：{e}"
            if os.environ.get("GITHUB_ACTIONS"):
                print(msg, file=sys.stderr)
                sys.exit(1)
            print(msg + "——本機略過「這裡的人物」區塊。")
            return {}

    try:
        data = yaml.safe_load(raw_text) or {}
    except Exception as e:
        msg = f"  ! 解析 arts-db map.yaml 失敗：{e}"
        if os.environ.get("GITHUB_ACTIONS"):
            print(msg, file=sys.stderr)
            sys.exit(1)
        print(msg + "——本機略過「這裡的人物」區塊。")
        return {}

    by_county = {}
    for pin in (data.get("pins") or []):
        if pin.get("type") != "person":
            continue
        county = (pin.get("county") or "").strip()
        name = (pin.get("name") or "").strip()
        link = (pin.get("link") or "").strip()
        if not (county and name and link):
            continue
        by_county.setdefault(county, []).append({
            "name": name,
            "hook": (pin.get("hook") or "").strip(),
            "url": ARTS_DB_BASE + link,
        })

    total = sum(len(v) for v in by_county.values())
    if total == 0:
        print("  ! arts-db map.yaml 讀到了但解析出 0 位 person pin——資料異常，中止建置。",
              file=sys.stderr)
        sys.exit(1)
    print(f"  arts-db 人物反向鏈：{source}，{total} 位、涵蓋 {len(by_county)} 個縣市頁")
    return by_county

def md2html(text):
    MD.reset()
    return MD.convert(text.strip()) if text and text.strip() else ""

def esc(s):
    return html.escape(str(s), quote=True)

# ---- 浮動導覽小浮標（FAB）：所有子頁面共用，取代舊 sticky topbar ----
# 圖示為 24x24 line icon，靠 CSS 以 currentColor 上色（fill:none）。
_HOME_SVG   = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11l9-8 9 8"/><path d="M5 9.5V20h14V9.5"/></svg>'
_UP_SVG     = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14"/><path d="M12 20V8"/><path d="M7 13l5-5 5 5"/></svg>'
_SHARE_SVG  = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="12" r="2.2"/>'
               '<circle cx="18" cy="5.5" r="2.2"/><circle cx="18" cy="18.5" r="2.2"/>'
               '<path d="M8 11 16 6.6"/><path d="M8 13l8 4.4"/></svg>')
_BACK_SVG   = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5"/><path d="M12 5l-7 7 7 7"/></svg>'
_COMPASS_SVG= '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M15.6 8.4l-2 5.2-5.2 2 2-5.2z"/></svg>'

# ---- 視覺改版 v1（docs/DESIGN-SPEC.md，2026-07-19）共用片段 ----
# 字體：與 taiwan-arts-db 同套 Google Fonts（§3）。
_FONTS_HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500'
    '&family=Noto+Serif+TC:wght@500;700;900&display=swap" rel="stylesheet">'
)

# 等高線角飾（§4.4）：inline SVG，內嵌模板不產生資產檔，aria-hidden、置於 .page-header 右上角。
_CONTOUR_SVG = (
    '<svg class="contour-orn" viewBox="0 0 160 160" aria-hidden="true" focusable="false">'
    '<path d="M20 92 Q8 52 44 30 Q86 6 122 34 Q152 58 136 96 Q118 138 74 140 Q28 142 20 92Z"/>'
    '<path d="M36 90 Q28 56 56 40 Q90 21 114 42 Q136 60 122 90 Q107 120 74 122 Q40 124 36 90Z"/>'
    '<path d="M52 87 Q46 63 66 51 Q89 37 106 53 Q121 66 110 86 Q99 107 74 108 Q50 109 52 87Z"/>'
    '</svg>'
)

# 比例尺分隔線（§4.3）：取代大段落之間的分隔。
_SCALE_BAR = '<div class="scale-rule" aria-hidden="true"></div>'

def site_bar():
    """子頁站識別列（§5b）：新增區塊，加在 render_page()/render_theme() 模板最前。"""
    return (
        '<div class="site-bar">'
        '<a class="site-bar-name" href="../index.html">認識臺灣——人文與自然地理資料庫</a>'
        '<span class="site-bar-tag">教師備課用</span>'
        '</div>'
    )

def page_hero_fig(pid, alt_name):
    """情境 hero 圖（§6）：無條件輸出 <img>，不做存在檔案檢查——缺圖靠 verify_live_images.py 抓。
    不加圖說（2026-07-19 David 拍板：一看就知道是繪圖，不需標註；史料照 geo-fig 的
    figcaption 作者／授權／來源不受影響）。"""
    return (
        f'<figure class="page-hero"><img src="../img/hero/{esc(pid)}.webp" '
        f'alt="{esc(alt_name)}情境示意圖" loading="lazy"></figure>'
    )

def fab_block(home_href=None, up_href=None, up_label="上一層", rel_js="../js/fab.js"):
    """回傳浮標 + toast + fab.js 引用。home/up 為 None 時省略該鈕（首頁用）。"""
    actions = []
    if home_href:
        actions.append(f'<a class="geo-fab-btn" href="{home_href}" '
                       f'aria-label="回首頁" title="回首頁">{_HOME_SVG}</a>')
    if up_href:
        lbl = esc(up_label)
        actions.append(f'<a class="geo-fab-btn" href="{up_href}" '
                       f'aria-label="{lbl}" title="{lbl}">{_UP_SVG}</a>')
    actions.append(f'<button type="button" class="geo-fab-btn" data-fab="share" '
                   f'aria-label="分享網址" title="分享網址（可用時複製網址）">{_SHARE_SVG}</button>')
    actions.append(f'<button type="button" class="geo-fab-btn" data-fab="back" '
                   f'aria-label="回上一頁" title="回上一頁">{_BACK_SVG}</button>')
    acts = "\n        ".join(actions)
    return (
        f'<div class="geo-fab" id="geo-fab">\n'
        f'      <div class="geo-fab-actions">\n        {acts}\n      </div>\n'
        f'      <button type="button" class="geo-fab-toggle" aria-label="導覽選單" '
        f'aria-expanded="false" title="導覽選單">{_COMPASS_SVG}</button>\n'
        f'    </div>\n'
        f'    <div class="copy-toast" id="copy-toast">網址已複製</div>\n'
        f'    <script src="{rel_js}"></script>'
    )

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

# ---- 站內檢索索引（site/data/search-index.json）----
# 供首頁 js/search.js 做 client-side 全文檢索；純文字，不含 markdown/HTML 語法。
_SI_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$", re.M)
_SI_LINK_IMG_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_SI_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_SI_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_SI_CODE_RE = re.compile(r"`([^`]+)`")
_SI_HEADER_RE = re.compile(r"^#{1,6}\s+", re.M)
_SI_QUOTE_RE = re.compile(r"^>\s?", re.M)
_SI_UL_RE = re.compile(r"^\s*[-*+]\s+", re.M)
_SI_OL_RE = re.compile(r"^\s*\d+\.\s+", re.M)
_SI_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SI_WS_RE = re.compile(r"\s+")

def strip_markdown_plain(text):
    """把一段 markdown 正文去語法後留純文字：去表格線、連結／圖片語法（保留文字）、
    粗斜體記號、行內 code 記號、標題井字、引用/清單前綴、殘留 HTML 標籤，空白正規化。"""
    if not text:
        return ""
    t = text
    t = _SI_TABLE_SEP_RE.sub(" ", t)
    t = _SI_LINK_IMG_RE.sub(r"\1", t)
    t = _SI_BOLD_RE.sub(r"\1", t)
    t = _SI_ITALIC_RE.sub(r"\1", t)
    t = _SI_CODE_RE.sub(r"\1", t)
    t = _SI_HEADER_RE.sub("", t)
    t = _SI_QUOTE_RE.sub("", t)
    t = _SI_UL_RE.sub("", t)
    t = _SI_OL_RE.sub("", t)
    t = t.replace("|", " ")
    t = _SI_HTML_TAG_RE.sub(" ", t)
    return _SI_WS_RE.sub(" ", t).strip()

def section_body_text(sections):
    """章節標題（純文字保留）＋ 去語法正文，合併成單一字串。"""
    parts = []
    for title, content in sections.items():
        if title:
            parts.append(title)
        stripped = strip_markdown_plain(content)
        if stripped:
            parts.append(stripped)
    return _SI_WS_RE.sub(" ", " ".join(parts)).strip()

def meta_description(sections, limit=100):
    """從「定位速覽」章節抽純文字前 limit 字，供 <meta name="description"> 與
    og:description 共用（A-list #3）。只抽取既有欄位、不新寫任何文案；沿用站內檢索
    索引同一支 strip_markdown_plain() 去 markdown 符號。53 頁全部有此章節（已核對），
    抽不到時回傳空字串，呼叫端據此省略該 meta 標籤而不是印出空 content。"""
    plain = strip_markdown_plain(sections.get("定位速覽", ""))
    return plain[:limit].strip()

def meta_tags_html(title_html, desc_plain, hero_abs_url):
    """<head> 內 description ＋ Open Graph 共用區塊（A-list #3）。
    title_html：已 esc 過、與 <title> 同值的 HTML；desc_plain：未 esc 的純文字（本函式負責 esc）。
    og:type 固定 article（縣市／主題內容頁）；og:image 指向該頁 hero 的絕對 URL。"""
    desc_html = esc(desc_plain) if desc_plain else ""
    lines = []
    if desc_html:
        lines.append(f'<meta name="description" content="{desc_html}">')
    lines.append(f'<meta property="og:title" content="{title_html}">')
    if desc_html:
        lines.append(f'<meta property="og:description" content="{desc_html}">')
    lines.append('<meta property="og:type" content="article">')
    lines.append(f'<meta property="og:image" content="{esc(hero_abs_url)}">')
    return "\n  ".join(lines)

def region_eyebrow_plain(fm):
    """縣市／鄉鎮頁眉標純文字版，邏輯與 render_page() 內 eyebrow 完全一致（未 esc）。"""
    name = fm.get("name", "")
    county = fm.get("county", "")
    unit_type = fm.get("type", "")
    if unit_type == "總覽":
        return "全島總覽"
    elif county == name:
        return " · ".join(x for x in ["縣市誌", unit_type] if x)
    else:
        return " · ".join(x for x in [county, unit_type] if x)

def theme_eyebrow_plain(fm):
    """主題頁眉標純文字版，邏輯與 render_theme() 內 eyebrow 完全一致（未 esc）。"""
    return " · ".join(x for x in [fm.get("layer", ""), fm.get("layer_sub", ""), fm.get("theme_group", "")] if x)

def build_search_index(regions_parsed, themes_parsed):
    """組 site/data/search-index.json 的 records 陣列。url 與既有 pages-index.json／
    themes-index.json 消費端一致，皆為 pages/{id}.html（相對首頁）。"""
    records = []
    for _path, fm, sections in regions_parsed:
        pid = fm.get("id", "")
        kw = [str(t) for t in (fm.get("tags_g5") or [])]
        county = fm.get("county", "")
        if county and county not in kw:
            kw.append(county)
        records.append({
            "id": pid,
            "url": f"pages/{pid}.html",
            "title": fm.get("name", ""),
            "sub": region_eyebrow_plain(fm),
            "kw": kw,
            "body": section_body_text(sections),
        })
    for _path, fm, sections in themes_parsed:
        pid = fm.get("id", "")
        kw = [str(t) for t in (fm.get("tags_g5") or [])]
        for extra in (fm.get("layer"), fm.get("layer_sub"), fm.get("theme_group"), fm.get("chip_label")):
            if extra and extra not in kw:
                kw.append(extra)
        records.append({
            "id": pid,
            "url": f"pages/{pid}.html",
            "title": fm.get("name", ""),
            "sub": theme_eyebrow_plain(fm),
            "kw": kw,
            "body": section_body_text(sections),
        })
    records.sort(key=lambda r: r["id"])
    return records

def build_sitemap(regions_parsed, themes_parsed):
    """組 site/sitemap.xml：絕對 URL，含首頁與全部子頁（A-list #4）。
    頁面清單直接沿用 regions_parsed／themes_parsed（與 pages-index.json／themes-index.json
    同一份解析結果），不重新掃檔，避免兩份清單日後跑不同步。"""
    urls = [f"{SITE_BASE_URL}/"]
    for _path, fm, _sections in regions_parsed:
        pid = fm.get("id", "")
        if pid:
            urls.append(f"{SITE_BASE_URL}/pages/{pid}.html")
    for _path, fm, _sections in themes_parsed:
        pid = fm.get("id", "")
        if pid:
            urls.append(f"{SITE_BASE_URL}/pages/{pid}.html")
    items = "\n".join(f"  <url><loc>{esc(u)}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{items}\n"
        "</urlset>\n"
    )

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

# ---- 反向鏈：縣市頁 → taiwan-arts-db 人物頁「這裡的人物」----
def local_people_block(people):
    """people：[{name, hook, url}]，來自 load_arts_people() 依 county 分組後的清單。
    連往 arts-db 是跨站，卡片一律 target=_blank 並標明出處，不假裝是站內連結。"""
    if not people:
        return ""
    cards = "\n".join(
        f'<a class="people-card" href="{esc(p["url"])}" target="_blank" rel="noopener">'
        f'<span class="pc-name">{esc(p["name"])}</span>'
        f'<span class="pc-hook">{esc(p["hook"])}</span>'
        f'<span class="pc-src">臺灣人文藝術資料庫 →</span></a>'
        for p in people
    )
    return (
        '<section class="local-people">'
        '<h2>這裡的人物</h2>'
        '<p class="lp-note">從這個地方，認識影響臺灣藝文的人：</p>'
        f'<div class="people-grid">{cards}</div></section>'
    )

# ---- 組頁 ----
def render_page(fm, sections, related_themes=None, local_people=None):
    name = esc(fm.get("name", "（未命名）"))
    county = esc(fm.get("county", ""))
    unit_type = esc(fm.get("type", ""))
    if unit_type == "總覽":
        eyebrow = "全島總覽"
    elif county == name:
        eyebrow = " · ".join(x for x in ["縣市誌", unit_type] if x)
    else:
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
    src_items = "\n".join(f'<li>{source_link_html(s)}</li>' for s in sources)
    src_block = f'<h3>資料來源</h3><ul>{src_items}</ul>' if src_items else ""

    # 浮標「上一層」目標：概論→總論 tab、宜蘭鄉鎮→宜蘭縣地圖、其餘縣市→分縣市 tab。
    county_raw = fm.get("county", "")
    pid_cur = fm.get("id", "")
    ptype_cur = fm.get("type", "")
    if pid_cur == "taiwan" or ptype_cur == "總覽":
        up_href, up_label = "../index.html#general", "回總論"
    elif county_raw == "宜蘭縣":
        up_href, up_label = "../index.html?county=宜蘭縣#counties", "回宜蘭縣地圖"
    else:
        up_href, up_label = "../index.html#counties", "回分縣市"
    fab = fab_block(home_href="../index.html#general", up_href=up_href, up_label=up_label)

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

    # 有 arts-db 人物 pin 才佔位；無則零位元組（同上，沒有人物的縣市頁不長空區塊）
    people_html = local_people_block(local_people)
    people_block = (people_html + "\n\n    ") if people_html else ""

    pid = fm.get("id", "")
    hero_fig = page_hero_fig(pid, fm.get("name", ""))
    # 比例尺分隔線（§4.3）：只在對應的兩段都存在時才佔位，避免孤立分隔線
    seam_teach_story = _SCALE_BAR if (teaching_section and story_section) else ""

    title_html = f"{name} — 認識臺灣"
    meta_tags = meta_tags_html(title_html, meta_description(sections), f"{SITE_BASE_URL}/img/hero/{pid}.webp")

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_html}</title>
  {meta_tags}
  {_FONTS_HEAD}
  <link rel="stylesheet" href="../css/style.css">
</head>
<body>
  {site_bar()}
  <main class="page-wrap">
    <header class="page-header">
      {_CONTOUR_SVG}
      <div class="eyebrow">{eyebrow}</div>
      <h1>{name}</h1>
      <div class="lede">{lede}</div>
      {stat_block}
    </header>

    {hero_fig}

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

    {_SCALE_BAR}

    {teaching_section}

    {seam_teach_story}

    {story_section}

    {related_block}{gallery_html}

    {people_block}<footer class="page-foot">
      {src_block}
      <div class="credit">
        圖資：內政部國土測繪中心／dkaoster taiwan-atlas（MIT 授權）。
        圖片版權屬各原作者，授權標示如圖說。本頁為教師備課資料庫。
      </div>
    </footer>
  </main>

  {fab}
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
    # 比例尺分隔線（§4.3）：主題頁 theme-block 之間
    body_html = f"\n{_SCALE_BAR}\n".join(body_parts)

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
    src_items = "\n".join(f'<li>{source_link_html(s)}</li>' for s in sources)
    src_block = f'<h3>資料來源</h3><ul>{src_items}</ul>' if src_items else ""

    fab = fab_block(home_href="../index.html#general",
                    up_href="../index.html#themes", up_label="回議題列表")

    pid = fm.get("id", "")
    hero_fig = page_hero_fig(pid, fm.get("name", ""))

    title_html = f"{name} — 認識臺灣"
    meta_tags = meta_tags_html(title_html, meta_description(sections), f"{SITE_BASE_URL}/img/hero/{pid}.webp")

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_html}</title>
  {meta_tags}
  {_FONTS_HEAD}
  <link rel="stylesheet" href="../css/style.css">
</head>
<body>
  {site_bar()}
  <main class="page-wrap theme-page">
    <header class="page-header">
      {_CONTOUR_SVG}
      <div class="eyebrow">{eyebrow}</div>
      <h1>{name}</h1>
      <div class="lede">{lede}</div>
    </header>

    {hero_fig}

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
  </main>

  {fab}
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

    # 反向索引：arts-db 人物 pin（county -> [{name, hook, url}]），唯讀、arts-db 側零改動
    arts_people = load_arts_people()

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
        out.write_text(render_page(fm, sections, reverse.get(pid), arts_people.get(pid)),
                       encoding="utf-8")
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

    search_records = build_search_index(regions_parsed, themes_parsed)
    OUT_SEARCH.write_text(
        json.dumps({"records": search_records}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    sitemap_xml = build_sitemap(regions_parsed, themes_parsed)
    OUT_SITEMAP.write_text(sitemap_xml, encoding="utf-8")

    print(f"完成：建了 {built} 頁（地名 {len(index)}、主題 {len(themes_index)}）；"
          f"索引 {OUT_INDEX.relative_to(ROOT)} + {OUT_THEMES.relative_to(ROOT)} + "
          f"{OUT_SEARCH.relative_to(ROOT)}（{len(search_records)} 筆）+ "
          f"{OUT_SITEMAP.relative_to(ROOT)}（{built + 1} 條，含首頁）。")

if __name__ == "__main__":
    main()

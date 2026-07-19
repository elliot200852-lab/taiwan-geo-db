# taiwan-geo-db 視覺改版 v1 設計規格（SSOT）

> 2026-07-19 立。David 拍板：以 taiwan-arts-db 設計語彙為基準的「輿圖風獨立變奏」——與藝文站低反差、
> 但有地理篇自己的特色；54 張情境圖一次到位；站名「認識臺灣——人文與自然地理資料庫」＋左靠小副標「教師備課用」。
> 實作者：改動前先讀完本檔＋docs/DEPLOY.md。與 arts-db docs/DESIGN-SPEC.md 成對參照。

## 0. 定位

- 與 taiwan-arts-db 是**成對站**：同字體系統、同紙感底色、同畫框思維、同鋼筆淡彩插畫，站與站互鏈時視覺不跳。
- 差異化＝**輿圖（antique map）語彙**：圖廓雙線框、經緯細格、比例尺分隔線、等高線角飾、輿圖藍。元素要細、要靜，不做強烈對比。

## 1. 硬規則（違反即打回）

1. `content/**/*.md` 母本正文與 frontmatter **一個字不動**（圖片欄位也不動——hero 走 slug 推導，不進 frontmatter）。
2. 「這裡的人物」反向鏈：`build.py` 的 `load_arts_people()`（含兩道 fail-fast）與 `local_people_block()` **邏輯不動**，只准加 class／改 CSS。arts-db 側零改動。
3. 首頁 hash-router `<script>`、`data-tab` 屬性、`.geo-tab`/`.tab-panel` 的 class 名與 JS 邏輯不動；class/id **只加不改名**。
4. `js/map.js`（Leaflet 路由、pin 定位）不動，只繼承新字體／色彩。
5. `site/img/manifest.json` 鍵值不動；`pull_images.py`／`verify_live_images.py` 的 fail-fast 不拿掉。
6. 350 張史料照的 `figcaption` 授權文字（作者 · 授權 · 來源）**不可簡化或刪除**。
7. 新圖一張都不進 repo——SSOT 在 Drive，CI 拉取（全域 pre-commit hook 會擋，不准繞）。
8. `site/data/*-index.json` 結構欄位不動。build 必須零錯誤跑完；360px 手機可讀。

## 2. 設計 token（`site/css/style.css :root` 全面改寫）

```css
/* 紙與墨（與 arts-db 同族，色值微調向舊輿圖紙） */
--paper:#f7f3e8;      /* 全站底：陳年圖紙米白 */
--paper-2:#efe8d6;    /* 面板底（teaching/storyteller 改用此，取代 #eddfc0） */
--card:#fcf9f0;       /* 卡片底 */
--ink:#2b2a26;        /* 暖墨 */
--ink-soft:#5c5850;
--line:#d9d1bc;
--hair:#e6dfd0;

/* 主輔色（沿用 geo-db 既有 terra/moss，不搬 arts-db 的 night/taupe） */
--terra:#b56a3c;      /* 赭土＝主強調色（呼應 arts-db --ochre 家族） */
--terra-deep:#8f4f28;
--moss:#6d7a4f;       /* 苔綠＝輔助色 */
--gold:#caa14a;       /* 沿用，僅點綴 */

/* 輿圖新色 */
--map-blue:#3f5e7a;      /* 輿圖藍：連結、水系意象（呼應 arts-db --indigo 但更灰、更製圖） */
--map-blue-deep:#2c4459;
--grid:rgba(63,94,122,.07);  /* 經緯格線 */
```

## 3. 字體（與 arts-db 完全同套，低反差的錨）

- 每頁 `<head>` 載入 Google Fonts：`Cormorant+Garamond:ital,wght@0,500;0,600;1,500` ＋ `Noto+Serif+TC:wght@500;700;900`。
- `--serif`＝Noto Serif TC：h1 用 900、h2 用 700、正文維持現行主體字策略（body 不強制改 serif-first，避免 34 頁長文可讀性回退）。
- `--latin`＝"Cormorant Garamond", Georgia, serif：**專用於數字與拉丁字**——stats 的面積/人口數字、年份、頁尾編號。斜體 500 為主。
- `--sans` 沿用給 meta 小字、圖說 credit。

## 4. 輿圖語彙四元素（本站簽名，全站僅此四種裝飾，不再加）

1. **圖廓框（neatline）**：雙線框＝內 1px `--terra` ＋ 外 1px `--terra`（`outline-offset:4px`），用於 (a) 54 張情境 hero 圖框 (b) 350 張史料照新框（取代現行圓角卡片：改直角、白襯紙 `#fffdf8` padding 8px、內一圈 1px `--hair` 髮線、陰影 `0 6px 18px rgba(43,42,38,.10)`——與 arts-db 畫框同構）。圓角 `border-radius:6px` 全站移除改直角（輿圖是直角的）。
2. **經緯細格（graticule）**：`repeating-linear-gradient` 橫直兩向 `--grid` 髮線、間距 64px——只鋪在 index `.site-head` 與子頁 `.page-header` 背景，正文區不鋪。
3. **比例尺分隔線（scale-bar rule）**：取代大區塊間的分隔——寬 120px、高 4px 的黑白相間四格條（CSS gradient 實作）＋兩端細髮線延伸；用於縣市頁「自然地理→人文地理→教學特點」等大段落之間、主題頁 theme-block 之間。h2 底線則改 32px×2px `--terra` 短 rule（arts-db 同款、換色）。
4. **等高線角飾（contour ornament）**：inline SVG（三四條同心不規則閉合曲線，`--ink` 6% 透明度），置於 `.page-header` 右上角，`aria-hidden`。build.py 模板內嵌，不產生資產檔。

## 5. 標頭系統（本次「標頭想清楚」的答案）

### 5a. index `.site-head`（改為左對齊）
```
教師備課用                    ← eyebrow：sans、0.78rem、letter-spacing .32em、--ink-soft、靠左
認識臺灣——人文與自然地理資料庫   ← h1：--serif 900、clamp(1.9rem,4.2vw,3rem)、--ink、靠左
────────────────────────      ← 雙髮線（1px --line ＋ 3px 間隔 1px --hair）
```
- 站名為 David 定稿文案，**逐字用**：「認識臺灣——人文與自然地理資料庫」（全形破折號）；小副標「教師備課用」靠左置於站名上方。
- 背景鋪經緯細格；`<title>` 同步改「認識臺灣——人文與自然地理資料庫」。
- tab 列：`.geo-tab` 保留 class 與 JS，只改視覺——去圓角、去方塊感，改極簡字標＋active 底 2px `--terra`（arts-db §3 同構）。

### 5b. 子頁新增 `.site-bar`（縣市頁＋主題頁，現況缺站識別）
- 頁面最上方一條細站名列：左＝「認識臺灣——人文與自然地理資料庫」（連回 `../index.html`，serif 700、0.9rem）；右＝「教師備課用」（sans、0.72rem、letter-spacing .24em、--ink-soft）。下緣 1px `--hair`。
- 這是**新增區塊**（加在 `render_page()`/`render_theme()` 模板最前），不動既有結構。

### 5c. 子頁 `.page-header`
- 結構不動（eyebrow → h1 → lede → stats），全面改樣式：eyebrow 改 `--terra` sans caps；h1 `--serif` 900 `clamp(2.1rem,4.5vw,3rem)`；lede max-width 62ch；stats 數字用 `--latin` 斜體、標籤用 `--sans` 小字。
- 背景鋪經緯細格＋右上等高線角飾；下接情境 hero 圖（見 §6）。
- 子頁 `<title>` 維持「{地名} — 認識臺灣」不動。

## 6. 情境 hero 圖（54 張，一次到位）

- **配置**：34 縣市/鄉鎮頁＋19 主題頁各一張、index 總論 tab 頂一張 site-hero，共 54。
- **位置**：`figure.page-hero` 緊接 `.page-header` 之後（index 為 `.general-intro` 頂）；`<img>` 寬滿內文欄、`aspect-ratio:21/9; object-fit:cover; max-height:340px`；套圖廓框；圖說靠右 0.72rem：「情境插畫 · AI 生成意象」（每頁必標，不可省）。
- **路徑約定（slug 推導，不進 frontmatter）**：`site/img/hero/{page-id}.webp`；index 用 `site/img/hero/site-hero.webp`。build.py **無條件**為每頁輸出 hero `<img>`（不做存在檢查）——缺圖時 `verify_live_images.py` 必然抓到，杜絕靜默缺圖。
- **風格**：鋼筆淡彩（與 arts-db 76 張同風），限定大地色（赭土/苔綠/輿圖藍/米紙）；畫**地景**——縣市頁畫該地最具代表性的地理景觀（從該頁 lede/自然地理段取材），主題頁畫該主題的意象地景；橫幅寬構圖；不出現文字、不畫可辨識人臉（人物只允許遠景剪影）。
- **prompt 風格前綴（批次腳本統一使用）**：
  > Traditional pen-and-wash illustration (鋼筆淡彩), fine ink linework with light watercolor washes, muted earthy palette of terracotta, moss green, slate blue and cream map-paper tones, wide panoramic landscape composition, aged paper texture, no text, no lettering, no recognizable human faces (distant silhouettes only), style of vintage geographic field sketches
- **生成參數**：gpt-image-2、1536×1024、quality 照 draw skill 預設判級；**並發 2＋失敗退避 35s**（帳號限流 5 張/分）；產出 jpg → `cwebp` 轉 webp（最長邊 1200，與現有圖同規）。
- **先驗後跑**：先生 3 張樣張（site-hero＋1 縣市＋1 主題）給 Fable/David 過目風格，過了才批次跑滿 54。

## 7. 各頁型規格

### index
- `.site-head` 照 §5a；tab 視覺照 §5a；總論 tab 頂 site-hero（§6）；縣市卡/主題卡套 `--card` 底＋直角＋hover `translateY(-2px)+shadow`（arts-db 卡片語言）；Leaflet 地圖區只繼承字體色彩。

### 縣市/鄉鎮頁（`render_page()`）
- `.site-bar`（§5b）→ `.page-header`（§5c）→ `figure.page-hero`（§6）→ 雙欄 `.geo-cols` 維持結構，h2 改短 rule、段間用比例尺分隔線 → `.teaching`/`.storyteller` 面板改 `--paper-2` 底＋左 3px `--terra` 邊 → `.related-themes`/gallery → `.local-people` 只改 CSS（卡片語言同 index 卡）→ `.page-foot`。
- 350 張史料照 `figure.geo-fig`：維持在文字流中的位置與全欄寬（教學可讀優先，不做 340px 浮動），只換圖廓框＋藝廊標籤牌 caption（title serif 700、credit sans letter-spacing .06em），授權文字照舊逐字保留。

### 主題頁（`render_theme()`）
- `.site-bar` → `.page-header` → `page-hero` → `.theme-block` 之間比例尺分隔線 → `.locator` 卡片套新卡片語言 → 其餘同縣市頁。

## 8. 部署整合

- Drive：「臺灣地理資料庫圖片」夾（`1JGRyJhoRQyuPCF4UMp92mhSWcXkc4fkY`）下新增 `hero/` 子夾放 54 張 webp；`drive-manifest.yaml` 若列子夾需同步補。`manifest.json` **不記 hero**（它只管外部 URL 史料照；hero 走 slug 推導）。
- 實作前必讀 `.github/workflows/deploy-pages.yml` 確認 `pull_images.py` 在 build 前執行且會拉到 `hero/`（偵察未讀此檔，這是實作者第一件事）。
- 驗收鏈：本機 build 零錯誤＋反向鏈 diff 零漂移 → push → CI → `verify_live_images.py` 全綠（會自動涵蓋 54 張 hero，因 `<img>` 無條件輸出）→ live 抽驗（index＋2 縣市＋2 主題＋360px 手機檢視）。

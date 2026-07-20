# 部署與圖片來源

`main` 有 push 就跑 `.github/workflows/deploy-pages.yml`，產物送 GitHub Pages：
<https://elliot200852-lab.github.io/taiwan-geo-db/>

```
Drive「臺灣地理資料庫圖片」 ──pull_images.py──> site/img/{page-id}/{NN}.webp
                                                        │
content/{county}/{unit}.md ──build.py──> site/pages/*.html ──> Pages artifact
                              ↑
                    site/img/manifest.json（URL → 路徑，留在 repo）
```

## 圖片不在 repo 裡

2026-07-15 起 350 張 webp 的 SSOT 在 Google Drive，repo 只留腳本
（`~/.claude/CLAUDE.md`「網路部署架構鐵則」：內容走 Drive、repo 管怎麼組裝上架）。
`.gitignore` 擋掉 `site/img/*/`，CI 每次 build 前從 Drive 拉。

| 項目 | 值 |
|---|---|
| Drive 夾 | 「臺灣地理資料庫圖片」`1JGRyJhoRQyuPCF4UMp92mhSWcXkc4fkY`，在 Creator Hub root 下、與「臺灣植物誌」同層 |
| 夾內結構 | 鏡射 `{page-id}/{NN}.webp`，53 子夾 / 350 檔 |
| 讀取者 | `channel-deployer@waldorfcreatorhubdatabase.iam.gserviceaccount.com` |
| repo secret | `GOOGLE_DRIVE_SA_KEY`（SA key JSON；key 本身不留硬碟，要新的就重產） |
| 對照表 | `drive-manifest.yaml` |

**`site/img/manifest.json` 是例外，它留在 repo。** 它住在 `site/img/` 裡面但不是內容，
是 `build.py` 的輸入（原始 URL → `img/…` 相對路徑）。`.gitignore` 只擋子目錄
（`site/img/*/`）就是為了讓它留下；`pull_images.py` 也刻意不清空目的地。

## 為什麼一定要驗 live

`build.py` 的 `resolve_src()` 在 manifest 查不到 URL 時**只印警告、退回原始外部 URL**，
不會 fail。也就是圖全掉了 CI 照樣綠、頁面照樣產出，只是 img 指向 404。

擋這件事的只有兩個地方，都別拿掉：

1. `pull_images.py` 兩道 fail-fast——拉到 0 檔中止、在 CI 上卻沒憑證中止。
2. `scripts/verify_live_images.py`——對 live 站逐張抓，驗 200＋`image/webp`＋大小相符。
   它從 `site/pages/*.html` 實際的 `<img src>` 收集清單，不是列 `site/img/`：
   共用圖機制會讓實體檔多於引用（曾出現孤兒檔 `theme-rivers/02.webp`）。

```bash
python scripts/verify_live_images.py        # 全綠才算部署成功
```

## 加圖片

`scripts/fetch_images.py` **只在本機 macOS 跑**（依賴 `sips` 與 homebrew `cwebp`），
CI 不跑。流程：改 `content/**.md` frontmatter 的 `images` → 跑 fetch_images
（下載、縮到最長邊 1200、轉 webp、寫 manifest）→ **把新圖上傳到 Drive 對應子夾** →
commit `manifest.json` 與 content。忘了上傳 Drive 的話 CI 拉不到，該圖會退回外部 URL。

manifest 的鍵是原始 URL、一個 URL 只存一份實體檔（落在第一個引用它的 page 夾），
所以**子夾名不保證等於引用它的 page-id**——`manifest.json` 是唯一權威，別靠目錄推斷。

## 資料來源標題

`content/**/*.md` frontmatter 的 `sources:` 只放裸 URL（母本零改動）。網頁上要顯示的
中文說明住 `scripts/source-titles.yaml`（URL → 標題對照），跟 `site/img/manifest.json`
一樣是**留在 repo 的 build 輸入例外**，不是內容，不走 Drive。

`build.py` 渲染「資料來源」時查這張表：查得到就顯示「標題 (host)」，查不到就 fallback
成裸 URL（原行為）。檔案不存在或格式壞掉時整體 fallback 裸 URL，不會讓 build 掛掉。

重生／更新：

```bash
.venv/bin/python3 scripts/fetch_source_titles.py   # 批次抓 <title>，寫回 source-titles.yaml
```

`content/**/*.md` 新增或修改 `sources:` 的 URL 之後要重跑一次，才會補上新 URL 的標題。
重跑不會清掉既有的成功項目或人工補洞（只有這次真的重新抓到新標題才覆蓋），抓失敗的
URL 會列在檔尾註解區供人工複查/補值。

## search-core 雙 repo 同步規則

`site/js/search-core.js`（首頁站內檢索的計分／排序核心）與 `taiwan-arts-db` 的
`assets/js/search-core.js` **必須 byte-identical**（2026-07-20 收斂案：兩站原本
各自獨立寫了一份幾乎相同的邏輯，同一個 tie-break bug 修了兩遍才拍板收斂）。

- **改核心邏輯**（計分公式、AND 語意、排序、tie-break）→ 兩個 repo 的
  `search-core.js` 都要改，改完兩份必須逐位元組相同。
- **改單站行為**（權重數值、typeBoosts 啟用與否、資料形狀轉換）→ 只改該站的
  adapter（本站 `site/js/search.js` 的 `GEO_CONFIG`），不動 `search-core.js`。
- `scripts/check-search-core-sync.sh`：本機找得到 sibling repo
  `../taiwan-arts-db` 就 diff 兩份 `search-core.js`，不一致直接 fail；CI
  上通常只 checkout 單一 repo，找不到 sibling 會印提示後略過（不擋 CI）。
  `scripts/test-search.js` 開頭就會跑這支，失敗即整個測試失敗。
- 本站目前**不啟用** `typeBoosts`（該欄位只有 `taiwan-arts-db` 用來壓廣泛詞
  被歌曲洗版），`GEO_CONFIG` 不帶這個欄位即為關閉，排序行為與收斂前完全一致
  （golden test：`scripts/search-golden.json` 收錄 20 組查詢的重構前 top-10，
  `scripts/test-search.js` 逐組比對零回歸）。

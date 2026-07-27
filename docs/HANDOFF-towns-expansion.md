# 鄉鎮頁擴充——交接與續做檢查點（SSOT）

> 2026-07-27 立。這條線會分很多批、跨很多 session 做完，**中途一定會斷**
> （usage limit、關視窗、換機器）。這份檔存在的唯一目的，是讓「斷掉之後接回來」
> 花 5 分鐘而不是重來一次。
>
> **續做的人（包含未來的我）進來第一件事，是跑狀態盤點，不是讀這份檔的進度表。**

```bash
cd ~/MyWork/taiwan-geo-db
.venv/bin/python3 scripts/towns_status.py            # 做到哪了、還剩什麼、卡在哪一步
.venv/bin/python3 scripts/towns_status.py new-taipei # 只看新北
```

進度的**唯一事實來源是磁碟**（母本在不在、字數、圖片授權欄位、頁面產出、hero），
不是任何人的記憶，也不是這份檔案裡寫的數字。這份檔只放**規則與決策**。

---

## 1. 目標

站上目前只有宜蘭縣的 12 個鄉鎮市有專屬頁面，其餘 21 個縣市都只有一頁概論。
要做的是把鄉鎮級頁面逐縣市補齊，並在每個縣市概論頁的標題附近長出轄區連結列。

- **第一批（2026-07-27 進行中）**：新北市 8 區＋宜蘭縣概論頁。
- 之後：新北剩下 21 區 → 其他縣市，一個一個看能不能完成（David 2026-07-27 定調）。

## 2. 既定決策（David 已拍板，續做的人不要重問）

| 項目 | 決定 | 日期 |
|---|---|---|
| 第一批做幾區 | 新北 8 區（29 區一次做不完） | 2026-07-27 |
| 哪 8 區 | **地形教科書優先**：淡水、瑞芳、平溪、烏來、林口、金山、三峽、板橋。一區負責一種地形，8 篇合起來是一套完整的地形課，呼應新北市概論頁自己的「地形寶庫」論點 | 2026-07-27 |
| 圖片深度 | 實景授權圖做完整（下載→webp→上 Drive→寫 manifest）；**AI 情境 hero 留下一輪** | 2026-07-27 |
| 連結列位置 | 縣市頁 `.page-header` 內，**導言（lede）與數據卡（stats）之間** | 2026-07-27 |
| 宜蘭縣 | 補一份縣級概論母本（`content/yilan/_county.md`，id `yilan`）——12 個鄉鎮頁早就寫完了，唯獨缺這個縣自己的整體視野 | 2026-07-27 |

## 3. 機制（build.py 這次新增的東西）

### 3a. 轄區連結列：`towns:` frontmatter
縣市概論母本加 `towns:`，列出轄下鄉鎮頁的 id，**順序即渲染順序**（照地理走，不照筆劃）。

```yaml
towns:
  - new-taipei-banqiao
  - new-taipei-sanchong
  # …
```

`towns_nav_block()` 只渲染「這次 build 真的產出了頁」的項——**還沒寫的鄉鎮不會出現，
所以永遠不會有死連結**，可以放心分批補。計數誠實標成「8 / 29」。
被略過的項會在 build 輸出印一行 `· {縣市} 的轄區「{id}」尚無母本，連結列略過`，
不讓「少了幾個區」變成沒人看得見的事。

這招是抄首頁 `YILAN_TOWNS.filter(ready)` 的既有做法，兩邊語意一致。

### 3b. `hero: false`——暫時關掉情境圖
`docs/DESIGN-SPEC.md` §6 規定 hero `<img>` **無條件輸出**，缺圖必然被
`verify_live_images.py` 抓到，用意是杜絕靜默缺圖。這條規則是對的，不要拿掉。

但新頁的 AI 情境圖還沒生，若照舊無條件輸出，會得到一批破圖，而且
`verify_live_images.py` 會全紅——那等於把整條部署驗收護欄關掉，比破圖更糟。

折衷：母本可寫 `hero: false`，該頁就不輸出 hero `<figure>`。
**預設（沒寫這欄）行為完全不變**，只有明確標記的頁才例外。

> ⚠️ **生完該頁的 hero 圖之後，一定要把母本裡的 `hero: false` 拿掉**，否則圖生了也不會顯示。
> `towns_status.py` 會把還開著這個旗標的頁標出來提醒。

### 3c. 「回上一層」浮標改成通則
原本寫死「county 是宜蘭縣 → 回首頁地圖」，因為當時宜蘭沒有縣頁。
現在改成：**有所屬縣市頁就回縣市頁**（`county_pages` 由 build 第一遍掃出來，
判準是 `fm.county == fm.name`）。副作用是既有 12 個宜蘭鄉鎮頁的上一層，
從「首頁宜蘭地圖」變成「宜蘭縣概論頁」——這是刻意的，新北各區走同一條路徑。

### 3d. 首頁宜蘭卡片
有了縣頁之後，首頁那張 `county-card--towns` 的縣名本身變成可點的連結（進縣概論頁），
12 個鄉鎮 chip 照舊。沒有縣頁時自動退回原本的純標題，不會壞。

## 4. 續做 SOP

1. `cd ~/MyWork/taiwan-geo-db && .venv/bin/python3 scripts/towns_status.py` — 看卡在哪。
2. 讀本檔第 2 節（既定決策）與第 6 節（會咬人的坑）。
3. **跑紅隊關卡**（見第 5 節）——這是必經的，不是形式。
4. 派 subagent 補缺的母本。派工模板見第 7 節，逐字用，不要自己重寫一份鬆的。
5. 母本齊了 → 圖片鏈（第 8 節）→ build → 驗收 → commit + push → 驗 live。

## 5. 紅隊關卡（必經，不准跳過）

David 2026-07-23 立、07-24 制度化：**計劃核可後、第一個實作動作前**，
逐字執行下面這段，攻自己的方案。大架構＝**每個階段動工前都要再跑一次**，
不是只在開頭跑。攻得動→改計劃；攻不動→記一行「攻擊不成立的理由」。

> Make the strongest case that this approach is wrong.
>
> Identify:
> - hidden assumptions
> - failure modes
> - unnecessary complexity
> - scalability or maintenance problems
> - simpler alternatives
>
> Do not defend the current approach.
> Try to convince me not to use it.

2026-07-27 這一輪攻出來、已回頭改進計劃的三條，記在這裡免得下一批又踩：

1. **缺 hero 會讓 `verify_live_images.py` 全紅**，等於關掉部署護欄 → 加 `hero: false` 旗標（§3b）。
2. **圖片授權不能讓寫作 agent 憑印象填**。這是對外公開站，CC BY 要求正確標示作者。
   → 派工模板強制實際打 Wikimedia API 讀 `extmetadata`、TCMB 走本機索引；
   拿不到授權的圖直接不收。`towns_status.py` 會逐張檢查 `url/license/author` 三欄。
3. **宜蘭縣頁不是「純新增」**。加了之後首頁那張卡片要能點進去，否則它是個孤兒頁；
   12 個鄉鎮頁的「上一層」也應該跟著改指縣頁 → §3c、§3d 一起做掉。

## 6. 會咬人的坑

- **新 Drive 子夾一定要共用給 `channel-deployer@waldorfcreatorhubdatabase.iam.gserviceaccount.com`**，
  否則 CI 拉圖 403，`pull_images.py` fail-fast 中止 → **整站部署掛掉，不只新頁**。
  （`drive-manifest.yaml` 的註解自己就寫了這件事。）
- `site/img/manifest.json` 的鍵是**原始 URL**，一個 URL 只存一份實體檔，落在第一個引用它的
  page 夾裡。所以**新頁的 Drive 子夾檔數會少於它引用的圖數**（重複引用既有圖時），
  驗收時別誤判成漏傳。manifest.json 是唯一權威，不要靠目錄推斷。
- `build.py` 的 `resolve_src()` 在 manifest 查不到 URL 時**只印警告、退回原始外部 URL**，
  不會 fail。圖全掉了 CI 照樣綠。擋這件事的只有 `verify_live_images.py`，別拿掉也別忽略它。
- `scripts/fetch_images.py` **只能在本機 macOS 跑**（依賴 `sips` 與 homebrew `cwebp`），
  CI 不跑，也**不能派給 subagent 平行做**——這段是序列的，時間要算進去。
- `content/**/*.md` 新增 `sources:` 之後要重跑
  `.venv/bin/python3 scripts/fetch_source_titles.py`，否則頁尾來源顯示的是裸 URL。

## 7. 派工模板（寫一篇鄉鎮母本）

一支 agent 寫一篇，不要一支包多篇（品質會掉）。每支必須拿到：

- 必讀：`docs/CONTENT-SPEC.md`（權威規範）＋一篇宜蘭母本當**體例標竿**
  （挑性質最接近的：山地原民鄉→`nanao.md`／溫泉鄉→`jiaoxi.md`／老街市鎮→`luodong.md`／
  港市興衰→`toucheng.md`／行政中心城→`yilan.md`）＋該縣市概論母本（避免重複與衝突）。
- 產出路徑、`id`／`name`／`county`／`type`、`hero: false`。
- **這一篇的主軸**：在整組裡負責哪一種地形／哪一條因果鏈。這段要具體寫出來，
  不然 8 篇會寫成 8 篇一樣的東西。
- **正文 4,700–5,500 字**（宜蘭 12 篇均值 5,100，不能明顯短於它）；教學特點佔 1/3 以上。
- 事實紀律：禁止幻覺、`sources` 逐條實際查證過的 URL、人口面積引官方並標年月、
  查不到寫「待查證」。
- 圖片紀律：Wikimedia 打 API 讀 `extmetadata` 取 `LicenseShortName`/`Artist`；
  TCMB 跑 `python3 ~/MyWork/WaldorfTeacherOS-Repo/setup/scripts/tcmb-search.py --search "地名"`；
  每張 `curl -sI` 驗 200；拿不到授權的圖不收。
- 語氣：教師備課用、5–9 年級通識、段落敘事體、禁地方誌流水帳。
  **禁 AI 腔**——不用「不是 A 而是 B」「與其說…不如說」「不僅是…更是」這類對立翻轉句式。
- 邊界：只寫那一個檔；不動 build.py／index.html／任何既有母本；不下載圖片；不 build；不 commit。

## 8. 圖片鏈（母本齊了之後，主對話序列做）

```bash
cd ~/MyWork/taiwan-geo-db
.venv/bin/python3 scripts/fetch_images.py          # 下載→最長邊 1200→webp→寫 manifest
# → 把新產生的 site/img/{page-id}/ 子夾上傳到 Drive「臺灣地理資料庫圖片」
#   (1JGRyJhoRQyuPCF4UMp92mhSWcXkc4fkY)，並確認新夾共用給 channel-deployer SA
.venv/bin/python3 scripts/fetch_source_titles.py   # 補頁尾來源的中文標題
.venv/bin/python3 scripts/build.py                 # 零錯誤才算過
node scripts/test-search.js                        # 檢索 golden 零回歸
git add -u && git commit && git push               # ⚠️ 圖片一張都不進 repo，pre-commit hook 會擋
.venv/bin/python3 scripts/verify_live_images.py    # CI 綠不等於圖在，這支全綠才算部署成功
```

## 9. 完成定義（DoD，逐頁）

一個鄉鎮頁算完成，要同時滿足（`towns_status.py` 就是照這個判的）：

- [ ] 母本存在，四個必要章節齊（定位速覽／自然地理／人文地理／教學特點）
- [ ] 正文 ≥2,500 字（目標 4,700–5,500）
- [ ] `images` ≥6 張，**每張都有 url + license + author**
- [ ] `sources` ≥1 條，且都是實際查證過的 URL
- [ ] `site/pages/{id}.html` 已產出
- [ ] hero 情境圖已生 **或** 母本明確標 `hero: false`
- [ ] live 站上圖片逐張 200（`verify_live_images.py` 綠）

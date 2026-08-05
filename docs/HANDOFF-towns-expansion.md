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

它同時是**規格閘門**，不只是進度表。這些原本要派一支 agent 用讀的才量得出來，現在是腳本的事：
正文字數、`教學特點` 佔比（低於 1/3 直接判未完成）、`定位速覽` 字數、圖片張數上下限與
授權三欄齊不齊、AI 腔句式掃描、hero 旗標。加 `--check-images` 會再逐張連出去驗 URL。

⚠️ **AI 腔掃描只抓句式，不是文風的全部**。它抓不到「機械對仗排比」「每段收一句金句」
這類要讀才看得出來的問題，也抓不到尾綴否定的變形。過了不代表文風沒問題——
它是篩子不是閘門。第一批仍然需要一支 fresh-context agent 讀過才抓得完整。

進度的**唯一事實來源是磁碟**（母本在不在、字數、圖片授權欄位、頁面產出、hero），
不是任何人的記憶，也不是這份檔案裡寫的數字。這份檔只放**規則與決策**。

---

## 0-A. 收官批進行中——下個 session 從這裡接手（2026-08-05 深夜懸置，David 指示斷點交接）

**現況一句話**：收官批 4 篇（大同/中正/大安/信義）**母本已寫完、兩輪查核已做完、圖片鏈已上 Drive，
只剩「套用下方 9 處修正 → 拆 hero 旗標 → 收尾鏈 → 一次 commit」**。全部未 commit（磁碟＝唯一事實）。

### 已完成（不要重做）
- 4 篇母本在 `content/taipei/`（datong/zhongzheng/daan/xinyi.md），towns_status 閘門全綠。
- 紅隊 Stage1+2 已跑（孤兒題材已收：文協/二二八/白恐/鐵道部/臺北車站/華山/五分埔/富陽）。
- 查核 B（文風重複）：兩輪全過——含五處修正（大安拆遷段換「兩通電話」、中正官廳段去猜謎、
  大安對仗句、信義速覽 136 字、信義兩段壓縮）已落檔且覆核通過。
- 查核 A（事實）：報告已出，**其中中正篇 3 處已修**（長野第二名中選、南機場 2105/2107 並陳、巴爾頓「生前」）。
- hero 4 張已生並上 Drive hero/（北門碉堡式、101 竹節各一修才過目檢）；內容圖 39 張已 fetch＋上 Drive
  4 新子夾（SA writer 權限已驗）；manifest.json 755 筆（未 commit）。

### 待辦①：套用查核 A 剩餘 9 處修正（逐字照抄，位置為 2026-08-05 深夜行號）
1. daan.md L124【必修，考證寫反】「是誤以為臺大西側那一段就是瑠公圳第二幹線」→「是誤以為臺大西側那一段就是霧裡薛圳第二支線」
2. daan.md L118【必修】「1922 年 4 月 1 日，臺灣總督府在古亭町設立七年制的臺北高等學校，主要招收在臺日本人子弟。」→「1922 年 4 月 1 日，臺灣總督府設立七年制的高等學校（初期借用臺北一中校舍），主要招收在臺日本人子弟；1926 年遷入古亭町校舍、改稱臺北高等學校。」
3. daan.md L120【必修，查無依據】刪「，組合長是後來的帝大總長幣原坦」
4. daan.md L122「1960 年雷震案後補助被停、著作被查禁、1966 年連教職也停了」→「1960 年雷震案後受牽連，1964 年補助被停、著作被查禁，1966 年連教職也停了」
5. daan.md sources L86–87 兩條臺師大死鏈刪除，補 `https://zh.wikipedia.org/zh-tw/%E6%A2%81%E5%AF%A6%E7%A7%8B%E6%95%85%E5%B1%85`（已驗 200）
6. xinyi.md L115【必修，正文漏了自己 sources 裡的關鍵一步】「隔年復工。」→「隔年復工；1976 年 1 月更名聯勤第二〇六廠。」；L119「（遷往三峽或大溪兩說並存，待覆核）」→「（多數資料指向三峽，另有大溪一說）」
7. xinyi.md L125「約六到七成為外省籍」→「約六成為外省籍」（報導者原文 58%）
8. datong.md L118「卻不被當地同安人接納，只好再遷大稻埕落腳」→「卻不被當地同安人接納（另一說是當時連日大雨、無法築土埆牆建屋），只好再遷大稻埕落腳」；sources 補 `https://zh.wikipedia.org/zh-tw/%E4%BA%8C%E4%BA%8C%E5%85%AB%E4%BA%8B%E4%BB%B6`（天馬茶房查緝細節的直接支撐）
9. zhongzheng.md L50 圖題改「臺北府城北門（承恩門）夜景（五座城門中唯一保持 1884 年原貌者）」（該圖實為國稅局大樓倒影夜景，題文對齊畫面）；L134「是臺北市幼年人口比例最高的行政區」→「幼年人口比例居全市前列」（「最」字缺可逐字核對出處）

### 待辦②：收尾鏈（照抄執行）
```bash
cd ~/MyWork/taiwan-geo-db
sed -i '' '/^hero: false/d' content/taipei/datong.md content/taipei/zhongzheng.md content/taipei/daan.md content/taipei/xinyi.md
.venv/bin/python3 scripts/fetch_source_titles.py
.venv/bin/python3 scripts/build.py                       # 應 95 頁零錯誤
.venv/bin/python3 scripts/towns_status.py taipei         # 12/12 全綠、無 hero 警告
node scripts/refresh-search-golden.js --new taipei-datong taipei-zhongzheng taipei-daan taipei-xinyi --write
node scripts/test-search.js                              # 23 項全過
git add -A && git commit && git push                     # 一次 commit（訊息照前兩批格式，12/12 收官）
gh run watch <run-id> --exit-status                      # CI 約 10–17 分鐘
.venv/bin/python3 scripts/verify_live_images.py          # 應 ~850/850 全綠，這是上線判準
```
然後：更新本檔 §0（臺北 12/12 全席收官）＋memory project_taiwan_geo_db＋清 /tmp/geo-hb 與 /tmp/used-images.txt。
臺北 12/12＝鄉鎮線臺北段結案，記得問 David 要不要 NotebookLM（Gemini Notebook）歸檔、以及下一個縣市點名。

### 本批新欠帳（等 David）
6. 民生社區計畫人口 45,000/55,000/70,000 各方不一（松山頁已並陳），需 1964 原始計畫文件。
7. 中正「幼年人口比例最高」待官方統計覆核（先改保守，見待辦①之 9）。
8. 兵工廠遷廠三峽/大溪兩維基條目互相矛盾（正文已採「多數指向三峽」）。

## 0-B. 上一段落（2026-08-05 晚場：臺北第二批收官）

**一句話（2026-08-05 晚）**：**臺北 8/12 上線**——第二批士林、內湖、南港、松山
（commit 7bde1c2，CI 綠、verify_live_images 807/807），全站鄉鎮頁 49/49。
臺北剩 4 區＝**大同、中正、大安、信義**，正好收官批；動工前必讀模板 §D「臺北二」列
與 §E 全部裝置黑名單（市頁 3＋批一 12＋批二 12——批二的 12 個裝置還沒補進 §E，
**下一批動工前先補**）。第二批紅隊攻出且已證實的坑，收官批直接適用：
- **信義區資產歸屬**：松山菸廠／五分埔／四獸山／台北 101／大巨蛋全在信義區——批二已把
  它們當「反例」用過（songshan.md），信義自己寫的時候注意別跟松山頁的反例段重講。
- **「唸誦史料文本」文類已趨飽和**（士林公文、內湖帳簿、南港照片指認、松山致詞稿），
  收官批的說書裝置優先換別的文類（查核 B 2026-08-05 觀察）。
- 大同與萬華共扛「艋舺→大稻埕」鏈的另一半；中正＝城內（市頁已寫三市街與府城，
  只准往更細一層下錨）；大安、中正的自然地理最薄，適用 David「人文多一點」指示
  （自然可短、教學特點 ≥35% 與字數上限不動）。
- 民生社區「計畫容納人口」45,000／55,000／70,000 各方記載不一（松山頁已並陳），
  需 1964 原始都市計畫文件才能定案——有人翻到就順手回修松山頁。

**一句話（2026-08-05 早）**：臺北第一批 4/12 上線（中山、文山、北投、萬華，commit eb20223，
CI 綠、verify_live_images 765/765）。派工模板已補臺北批分工表與
taipei.md 裝置黑名單（郁永河／同安商人／盆地口白＋五探究題不准重用）；hero 8 張已生
（文山湖、北投煙、南港海、松山古橋各一修，教訓同大屯山三修：具體地標與地質狀態要目檢）。

### 臺北批新增欠帳（等 David 拍板才動）
4. **「一府二鹿三艋舺」市頁措辭**：wanhua.md 查證＝清代文獻查無此語（維基文庫清代方志
   「艋舺」190+ 處、「一府二鹿」0 命中；吳子光《一肚皮集》說無法覆核；最早印刷紀錄
   1930 劉克明《臺灣今古談》作「一府二鹿三艋」）。wanhua.md 已照證據等級寫「後人追述」，
   但 `taipei.md` 正文與龍山寺圖說仍當清代既成事實引用——要不要改，等 David。
   不改則與 xinzhuang.md「一府二鹿三新莊查證教案」證據標準不一致。
5. 貴子坑禁採「確切年份」查不到官方公文（1977 災變後下令有據、「1978」無據，
   四篇已改保守表述）；劍潭《臺灣志略》1732 任職年 vs 1738 成書年混用（低）。

**一句話（2026-07-29）**：**新北 29/29 全席**——收官批 7 區（深坑、石碇、坪林、
雙溪＝山區；三芝、石門、萬里＝北海岸）於 2026-07-29 凌晨上線（commit 6a542cc，
CI 綠、`verify_live_images.py` 720/721，唯一一筆為既有頁暫時連線重置、單獨重驗 200）。
同輪補齊 **13 張情境 hero**（第三批 6 區＋本批 7 區，gpt-image-2 low、上 Drive hero/、
旗標全拆）。查核 A/B 修 6 高 21 中；golden 更新 5 組（純新頁進榜、既有頁排序零改變，
`refresh-search-golden.js --new` 白名單驗證）。順手修 xindian.md 一句
（北勢溪源流在雙溪，非坪林——查核 A 三來源裁決）。

### 欠帳（等 David 拍板才動）
1. **土城說書稿#1**：「隨車員工作日誌」與新店「工地日誌」同族，備選「行車檢查簿」
   已擬好，等 David 一句話（不換也能活）。
2. **tamsui 說書稿「紅毛城自己的口白」與市級頁裝置逐字同族**（第一批遺留，
   查核 B 本輪點名）——要不要換裝置等 David。
3. **面積來源全批不一致**：民政局 29 區面積表 vs 區公所／維基（貢寮 99.97 vs 101.79、
   瑞芳 70.73 vs 72.23、石碇採 144.35 非表值 141.92…）。新頁已在頁內註明歧異；
   要不要全站統一等 David。

### 下一步（等 David 指示才動工）
新北完結。下一個縣市由 David 點名（依既定決策「一個一個看能不能完成」）。
動工照 §4 SOP（紅隊關卡必經）＋§7 派工模板；查核照本輪模式（寫作與查核分開派、
修正另派、一批收齊才 commit）。

### 本輪新增的坑與紀律（新進的必讀）
- `gen_hero_images.py` **要用系統 `python3` 跑，不能用 repo 的 `.venv`**（venv 沒裝
  openai 模組，會 ModuleNotFoundError；2026-07-29 實踩）。
- **heartbeat 檔看門狗實戰通過**：agent 每步 append 一行到 /tmp/geo-hb/{slug}.log，
  `agent-liveness-watch.sh 20 300 <max> <hb 檔們>`；本輪 12 支 agent 零凍死。
  唯一告警是「已完工 agent 的心跳自然停止」造成的誤報——**agent 完工就把它的
  心跳檔從看門狗清單拿掉（rm 檔案重掛）**，並且告警後先驗屍（看稿檔 mtime）再定死因。
- `towns_status.py --check-images` 全站掃描時 Wikimedia thumb URL 也會被暫時 429
  （批量 HEAD 觸發限流）——單獨重測 200 即非死鏈；live 出圖走 Drive，不受影響。
- 派工單必含**外部站活性紀律**與 **TCMB 線上站禁令**（§6b 凍死驗屍＋模板 §F/§G）。
- Wikimedia 圖片 URL 一律用 `/thumb/.../1280px-` 形式，原檔 URL 會被 429（§6）。
- 民政局人口表**115 年 5 月的坪林列有誤**（多 851 人、里鄰數與前後月不符）——
  引人口資料時避開該月坪林列（坪林頁已改用 115-06）。

## 1. 目標

站上原本只有宜蘭縣的 12 個鄉鎮市有專屬頁面，其餘 21 個縣市都只有一頁概論。
要做的是把鄉鎮級頁面逐縣市補齊，並在每個縣市概論頁的標題附近長出轄區連結列。

- **第一批（2026-07-27 完成）**：新北 8 區——淡水、瑞芳、平溪、烏來、林口、金山、三峽、板橋
  ＋補上宜蘭縣概論頁。
- **第二批（2026-07-28 完成 8／8）**：中和、新莊、新店、汐止、八里、鶯歌、貢寮、三重。
- 之後：新北剩下 13 區 → 其他縣市，一個一個看能不能完成（David 2026-07-27 定調）。
  剩下的 13 區＝永和、蘆洲、五股、泰山、樹林、土城、深坑、石碇、坪林、
  三芝、石門、萬里、雙溪。

## 2. 既定決策（David 已拍板，續做的人不要重問）

| 項目 | 決定 | 日期 |
|---|---|---|
| 每批做幾區 | 8 區（29 區一次做不完；第二批同樣 8 區） | 2026-07-27 |
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

**第二批動工前又跑了一次，攻出兩條成立的**（證明每階段都要重跑不是形式）：
① 在第一批的獨立驗收回來之前就派第二批，等於把還沒驗證的模板複製八份——
   改成等驗收報告回來、把它的發現寫進派工模板才發。事後證明這個等待是對的：
   驗收抓到的篇幅失控與教學特點被稀釋，直接改寫了第二批的規格。
② 第二批要開始寫盆地裡的密集市區（三重、新莊、中和），那裡的〈自然地理〉是一片平的，
   第一批那套「戲劇性地形」模板會寫不出東西——改成逐區給不同的破題法。

**⚠️ 派工單本身也會錯，而且錯得很像真的。** 第二批 8 支 agent 更正了我 5 處：
草嶺古道不是入蘭「唯一」陸路（淡蘭古道有三路，更早走嶐嶺）／十三行博物館官方措詞是
「確定擁有煉鐵技術的史前居民**之一**」沒有「唯一」／員山子分洪道在瑞芳不在汐止／
三峽河運中斷主因是 1923 桃園大圳不是石門水庫／新店溪河階的階數與高度差在文獻上查不到
（真正被登錄國家級地景的是「新店曲流」）。
五次的形狀一樣：**派工單寫的是「聽起來很順、很好教」的版本，查證出來的是
「有文獻依據但比較麻煩」的版本。** 派工模板裡「派工單也可能是錯的，以你查到的
官方資料為準並回報」這條，是這一批最有價值的一句，不要拿掉。
（另一個實例：新莊那支查出「一府二鹿三新莊」**查無清代文獻依據**，維基為此版本引用的
唯一來源是新莊區衛生所網頁；照原派工單寫下去就是把地方傳說當史實教給五年級。）

2026-07-27 第一批攻出來、已回頭改進計劃的三條，記在這裡免得下一批又踩：

1. **缺 hero 會讓 `verify_live_images.py` 全紅**，等於關掉部署護欄 → 加 `hero: false` 旗標（§3b）。
2. **圖片授權不能讓寫作 agent 憑印象填**。這是對外公開站，CC BY 要求正確標示作者。
   → 派工模板強制實際打 Wikimedia API 讀 `extmetadata`、TCMB 走本機索引；
   拿不到授權的圖直接不收。`towns_status.py` 會逐張檢查 `url/license/author` 三欄。
3. **宜蘭縣頁不是「純新增」**。加了之後首頁那張卡片要能點進去，否則它是個孤兒頁；
   12 個鄉鎮頁的「上一層」也應該跟著改指縣頁 → §3c、§3d 一起做掉。

## 6. 會咬人的坑

- **`--check-images` 對 Wikimedia「原檔 URL」會穩定回 429**（無 `/thumb/` 路徑的
  `upload.wikimedia.org/wikipedia/commons/X/XX/...` 形式；Wikimedia 對非瀏覽器抓原檔
  強力限流，間隔 3 秒也擋）。這不是死鏈——live 站的圖從 Drive 出、不吃外部 URL。
  舊宜蘭頁有 10 張原檔 URL 長期如此（大同 7、南澳 3），新頁一律用 `/thumb/.../1280px-`
  形式就不會遇到（2026-07-28 實測）。

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

## 6b. 併發與時序（2026-07-27 第一批踩了兩次的坑）

- **agent 還在跑的時候不要 commit 它的產物。** 寫作 agent 會在寫完檔之後繼續縮字、精修，
  它最終版跟中途稿差很多。第一批就是因為中途 commit，導致**獨立驗收報告有一半在驗過期版本**
  （量到 3 篇教學特點不足，最終版其實都過了），白白多繞一圈。
  **一批全部收齊、跑完閘門，再一次 commit。**
- **平行寫作 agent 的暫存檔要各自命名。** 第一批有兩支同時用 scratchpad 的 `fm.yaml`，
  互相覆寫，其中一支差點把別區的 frontmatter 接到自己的正文上（它自己發現並復原）。
  派工模板已加這條。
- **一次最多 20 支 subagent**（`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`）。超過會直接被擋，
  要分梯次發，**發完一定要檢查有沒有哪幾支根本沒發出去**——第二批第一次發 8 支只出去 3 支。
- **背景 agent 沒消息不等於還在跑——死因已查明（2026-07-28 法醫驗屍）。**
  第二批兩支（三重、事實查核）與 07-28 早上三支（查核 A/B、三重重派）共五支全是
  同一死法：**WebFetch 打到掛站的 tcmb.culture.tw，部分請求「不回應也不逾時」，
  整支 agent 卡在永不結束的工具回合裡**——零錯誤、零通知，transcript 尾端特徵是
  最後一個事件停在 `stop=tool_use` 的懸空呼叫（前兩支當時誤診為「跨夜額度中斷」，
  純屬猜測、未驗屍）。三條鐵律：
  ① 派工單必含外部站活性紀律與 TCMB 線上站禁令（writing-brief-template.md §F／§G）。
  ② 派出後立刻掛看門狗：
    `~/MyWork/_scripts/agent-liveness-watch.sh 20 300 120 <transcript 檔們>`
    （靜止 20 分鐘即告警退出，主對話會收到通知）。
  ③ 凍死的 agent **用 SendMessage ping 叫不醒**（訊息要等下一個工具回合送達，而回合
    永遠不會結束）；唯一救法＝**先 TaskStop 再 SendMessage**——會從 transcript 復活、
    context 全保留、從中斷處續跑。07-28 三支都這樣救回，幾十萬 tokens 沒白燒。
- **一個 session 的 WebSearch 有額度上限（200 次）**。第二批後段幾支 agent 全部撞到，
  改用 WebFetch 直打 URL＋Wikipedia/Commons API＋本機 TCMB 索引完成，來源品質沒有降低，
  但要知道有這回事（`CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION`）。
- 資料年月會隨時間漂移：新北市民政局的表每月更新，第一批取 2026-05，晚一點寫的就只拿得到
  2026-06。**每頁自己標明資料年月即可，不必回頭統一**——標錯年月比不同年月更糟。

## 7. 派工模板（寫一篇鄉鎮母本）

**正本＝`docs/writing-brief-template.md`**（共同規範：篇幅比例、文風禁令、數字格式、
地形分工表、圖片與授權、事實紀律、併發安全、回報格式）。派工時讓 agent
**第一步就完整讀那份檔**，派工單本身只寫「哪一區、主軸是什麼、要避開哪一篇鄰區」。
這樣派工單短、規範集中一處，改一次全批生效。

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
- **YAML 值裡有冒號、`#`、引號、開頭是 `-` 或數字時一律用雙引號包起來**。實測撞過
  `author: Minchi Chen（Flickr: minchi_chen）`——全形括號裡那個半形冒號讓整份 frontmatter
  解析失敗，`fetch_images.py` 直接掛掉。派工時就講，比事後修划算。

## 8. 圖片鏈（母本齊了之後，主對話序列做）

```bash
cd ~/MyWork/taiwan-geo-db

# 0. 先驗 YAML——寫作 agent 產出的 frontmatter 真的會壞（見 §7 最後一條），
#    壞了 fetch_images 會直接掛掉，早點知道比較好
.venv/bin/python3 scripts/towns_status.py

# 1. 抓圖。**一定要加 --only 指定這批的 page id**：site/img/*/ 被 gitignore 擋著、
#    本機是空的，不加過濾會把既有 400+ 張全部重下一遍（每張間隔 1.5 秒）
.venv/bin/python3 scripts/fetch_images.py --only new-taipei-xxx new-taipei-yyy

# 2. 上傳 Drive。冪等可重跑；會逐檔比對 Drive 實際內容，並查新夾的權限
.venv/bin/python3 scripts/upload_images_to_drive.py --dry-run     # 先看要傳什麼
.venv/bin/python3 scripts/upload_images_to_drive.py new-taipei-xxx new-taipei-yyy

# 3. 其餘
.venv/bin/python3 scripts/fetch_source_titles.py   # 補頁尾來源的中文標題
.venv/bin/python3 scripts/build.py                 # 零錯誤才算過
node scripts/test-search.js                        # 檢索 golden 零回歸
.venv/bin/python3 scripts/towns_status.py --check-images   # 逐張連線驗，收稿最後一關
git add -u && git commit && git push               # ⚠️ 圖片一張都不進 repo，pre-commit hook 會擋
.venv/bin/python3 scripts/verify_live_images.py    # CI 綠不等於圖在，這支全綠才算部署成功
```

**為什麼上傳要獨立一支腳本**：`fetch_images.py` 只把圖抓到本機並寫 manifest，
上傳是另一段、而且**忘了就會靜默壞掉**——CI 從 Drive 拉不到該圖，`build.py` 的
`resolve_src()` 查不到只印警告就退回原始外部 URL，CI 照樣綠、頁面照樣產出。
擋得住的只有 `verify_live_images.py`。

## 9. 完成定義（DoD，逐頁）

一個鄉鎮頁算完成，要同時滿足（`towns_status.py` 就是照這個判的）：

- [ ] 母本存在，四個必要章節齊（定位速覽／自然地理／人文地理／教學特點）
- [ ] 正文 ≥2,500 字（目標 4,700–5,500）
- [ ] `images` ≥6 張，**每張都有 url + license + author**
- [ ] `sources` ≥1 條，且都是實際查證過的 URL
- [ ] `site/pages/{id}.html` 已產出
- [ ] hero 情境圖已生 **或** 母本明確標 `hero: false`
- [ ] live 站上圖片逐張 200（`verify_live_images.py` 綠）

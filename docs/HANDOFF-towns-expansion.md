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

## 0. 下一個 session 從這裡開始（2026-07-28 02:30 交接）

**一句話**：新北 15 區＋宜蘭縣概論全部寫完、圖全部上 Drive、build 與檢索測試全綠，
但**還沒 push**，因為獨立事實查核沒跑完（兩次派出的 agent 都死了——當時誤診為
「跨夜額度中斷」，2026-07-28 法醫驗屍查明真因是 TCMB 掛站的懸死 WebFetch，見 §6b）。

### 開工三件事
```bash
cd ~/MyWork/taiwan-geo-db
.venv/bin/python3 scripts/towns_status.py          # 現況（磁碟是唯一事實來源）
git log --oneline -3                                # 看有沒有 push 出去
git status --porcelain | wc -l                      # 有沒有未提交的
```

### 必須先做、做完才准 push（**這是 push 的前置閘門，不是建議**）
1. **獨立事實查核**：派 fresh-context agent 查 16 篇新母本
   （新北 15 區＋`content/yilan/_county.md`）的高風險事實。**這是要拿去教五年級的內容，
   而且是對外公開站。** 每篇抽 4–6 條最容易被編得像真的：地名語源、年代、人口數字、
   族群敘述、地質成因機制、以及「最／唯一／第一」這種絕對宣稱。
   要求它**實際打開該篇 `sources:` 裡的 URL 對照**，正文寫的東西若在自己列的來源裡找不到，
   那本身就是問題。16 篇建議拆 2–3 支 agent，不要一支包完。
2. 查核抓到的問題修完 → `build` → `test-search` → commit → **push** → CI →
   `verify_live_images.py` 全綠才算真的上線。

### 還沒做的
- **三重區母本**（`content/new-taipei/sanchong.md`）：第二批唯一沒生出來的，
  agent 跑到一半就因額度中斷死掉。派工單內容見 §7 與 `docs/writing-brief-template.md`，
  主軸＝「淡水河左岸的河灘低地＋二重疏洪道『主動讓地給水』＋中南部移民北上第一站」，
  要避開板橋（堤防與抽水站，機制對照）與中和（跨國移民 vs 島內移民）。
- **16 張 AI 情境 hero**：15 區＋宜蘭縣。母本目前都掛 `hero: false`。
  ⚠️ **生完一定要把該篇母本的 `hero: false` 拿掉**，否則圖生了也不會顯示。
  依生圖三鐵則，動手前要 David 當次同意。

### 等 David 拍板的
- **既有 12 篇宜蘭母本有 33 處「不是 A 而是 B」違規**（三星 7、礁溪 5、五結 5、羅東 4…），
  新寫的 16 篇是 0 處。宜蘭那批寫於 2026-07-14，與該規則立下同日，
  應是規則還沒套進本 repo 就寫完了。要不要一併清掉，David 還沒回答。
  跑 `scripts/towns_status.py` 就會列出來。

## 1. 目標

站上原本只有宜蘭縣的 12 個鄉鎮市有專屬頁面，其餘 21 個縣市都只有一頁概論。
要做的是把鄉鎮級頁面逐縣市補齊，並在每個縣市概論頁的標題附近長出轄區連結列。

- **第一批（2026-07-27 完成）**：新北 8 區——淡水、瑞芳、平溪、烏來、林口、金山、三峽、板橋
  ＋補上宜蘭縣概論頁。
- **第二批（2026-07-28 完成 7／8）**：中和、新莊、新店、汐止、八里、鶯歌、貢寮。
  **三重未完成**（見 §0）。
- 之後：新北剩下 14 區 → 其他縣市，一個一個看能不能完成（David 2026-07-27 定調）。
  剩下的 14 區＝三重、永和、蘆洲、五股、泰山、樹林、土城、深坑、石碇、坪林、
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

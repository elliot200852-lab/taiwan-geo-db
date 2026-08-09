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

## 0-KH. 高雄批總計畫（2026-08-09 立；動工前先讀這節）

**David 拍板的節奏（2026-08-09）**：38 區分 4 個 session 做——**每個 session 最多 12 區
（4 批×3 支寫作輪替）；12 區全鏈走完（查核→修正→圖片鏈→hero→發布→verify 全綠）
就寫 handoff、換新 session 續做**。理由＝防長 session 漂移：context 一長，規格執行會走樣，
臺東 16 區單 session 已在邊緣。寫作一批 3 支（在 David 2026-08-06「一次最多 4 支」上限內）。

### Session 切分
| Session | 批次 | 內容 |
|---|---|---|
| KH-S1 | 高雄一～四 | 12 區 |
| KH-S2 | 高雄五～八 | 12 區 |
| KH-S3 | 高雄九～十二 | 12 區 |
| KH-S4 | 高雄十三＋收官 | 末 2 區＋縣頁 towns: 全列＋NotebookLM 歸檔（先問 David）＋worktree/分支清理 |

38 區逐區主軸與批次分組＝`writing-brief-template.md` §D 高雄節（分組原則：同批 3 區
地理性質異質——平行寫作讀不到彼此的稿；莫拉克敏感頁分散到不同批）。

### 每個 session 的固定流程（KH-S2 起照抄，不要重新發明）
1. 開工：`~/MyWork/_scripts/dispatch-preflight.sh ~/MyWork/taiwan-geo-db` →
   在 **worktree 內**跑 `towns_status.py kaohsiung`（縣頁 `towns:` 38 條已於 KH-S1 先行加入，
   盤點從第一天就量得到 N/38）→ git fetch 確認前 session 已推 main → 讀本節＋§6／§6b 坑單。
2. **紅隊關卡（§5）每 session 動工前重跑**，攻不動才發批。
3. worktree `_workspace/geo-kh-wt`（分支 kh-towns）續用；不存在就從 origin/kh-towns 重開。
   **本批全鏈（寫作、圖片鏈、build、發布前驗證）一律在 worktree 內跑**——§8 的
   `cd ~/MyWork/taiwan-geo-db` 對高雄批一律讀作 `cd ~/MyWork/taiwan-geo-db/_workspace/geo-kh-wt`。
   `check-search-core-sync` 需要 sibling：`_workspace/taiwan-arts-db` symlink（KH-S1 已建；
   不在就重建，**它不在時該腳本靜默 exit 0＝fail-open，等於守衛沒跑**）。
4. 每批 3 支 Opus 寫作（派工單＝模板全文＋§D 該區行＋used-images 重生檔＋
   `docs/devices-used-kaohsiung.txt`）；**收稿閘＝跑 towns_status 後由主對話逐項對照批規格線
   人工核數字**——腳本只硬擋下限（≥2,500 字／教學 ≥33%／圖 6–10 三欄），**4,500–5,200 上限、
   35%、速覽 ≤150 它不擋只顯示**，超線退回該支自修（字數以腳本口徑為準，agent 自量低估約 20%）。
   過閘才 commit 進 kh-towns，一批一 commit（斷點保險）。
5. 4 批收齊（12 區）→ 查核 A（事實，Sonnet；**敏感頁必須逐字比對 `content/themes/typhoon.md`
   莫拉克段的傷亡數字口徑**，placenames/migration 等主題頁高雄段一併對）＋
   查核 B（文風/撞題，Sonnet，**拆兩支各 6 頁**——單支讀 6 萬字對 200 個裝置會自己漂移）→
   修正（Sonnet；重寫等級才升 Opus）→ 複驗。
6. 圖片鏈照 §8 序列跑（在 worktree 內）→ 本 session 12 張 hero（Sonnet 從各頁定位速覽起草
   prompt、append `hero-prompts.yaml` → `gen_hero_images.py` 用**系統 python3**、low、並發 2、
   逐張目檢地標與地質狀態）。**生圖授權：David 2026-08-09 已為高雄整條線授權
   （gpt-image-2 嚴格 low），後續 session 沿用、不必重問。**
7. 發布：git fetch → rebase main → build 零錯誤 → `node scripts/test-search.js`
   （golden `refresh --new` 純新頁白名單、既有排序零改變；縣頁只在 KH-S1 因加 `towns:` 進一次
   白名單，之後不再動縣頁）→ `towns_status.py --check-images`（批量 429＝假陽性單獨重驗）→
   commit → push kh-towns:main → CI（28–30 分是常態，別誤判卡死）→
   `verify_live_images.py` 全綠才算上線。
8. handoff：更新本節「進度斷點」（完成區、commit hash、verify 數字、欠帳、下一批批號）＋
   本 session 36 個新說書裝置 append 進 `docs/devices-used-kaohsiung.txt`（持久化，/tmp 會被清）＋
   **隱性狀態清單逐項確認**（worktree 路徑與分支、arts-db symlink、devices txt、
   hero-prompts.yaml 累積狀態、scratchpad 內會被清掉的檔）→ commit push → 收 session。

### 驗收標準（開跑前立，2026-08-09）
- 正例：每批收稿當場 towns_status 全過（4,500–5,200 字腳本口徑、教學特點 ≥35%、
  定位速覽 ≤150、圖 6–10 且 url/license/author 三欄齊、sources 實查）。
- 反例：寫作 agent 灌水或 YAML 壞＝該批收稿閘當場抓，不留到批末；圖漏上 Drive＝
  `verify_live_images.py` 逐張 200 抓（**CI 綠不算上線**）。
- 抽驗：每 session fresh-context 查核 A/B＋檢索 golden 零回歸＋live 全綠。

### 高雄批特有紀律
- **敏感頁（莫拉克傷亡）＝5 支 A 級**：那瑪夏、六龜、甲仙、桃源、杉林（大愛園區）——比照
  花蓮光復慣例：只寫多來源交叉查證過的事實、保守表述、標明資料時點、寧缺勿錯。
  分散在不同批**循序寫**（寫完驗完一支才動下一支）；每支後寫的派工單必附
  `content/themes/typhoon.md` 莫拉克段＋已完成的前面莫拉克頁當口徑對照；
  **KH-S4 收官加一道五頁莫拉克口徑一致性複查（Sonnet 小支）**。
- **三個市中心小區（前金／新興／苓雅）主軸必須切開**，§D 明寫分界，不然會寫成三篇一樣的。
- 市級頁三裝置（馬卡道少年種竹／高雄港口白／美濃反水庫青年）＋五探究題不准重用（模板 §E 高雄節）。
- **說書裝置文類由派工端統一指定**（38 區×3 裝置配置表＝模板 §D 高雄節附表）；
  擬人地形／物件口白全站已飽和，本批一支都不准用。
- 人口＝高雄市民政局戶籍人口統計月報表1，**取當時最新可得月、照實標**（2026-08 實查只到
  115-03；⚠ 該站錯誤參數也回 HTTP 200、內容是「資料有誤」，要開檔驗月份字串）。
  縣頁加總鎖死**不承諾**（跨 session 月份會漂，照花蓮前例「各頁自標年月」）。
- 小區（前金／新興／鹽埕等）**寫不滿寧取 4,500 下緣、禁灌水**——腳本抓得到砍、抓不到灌，
  灌水是本批規格的預設失敗方向。
- WebSearch 每 session 有 200 次共用上限（§6b 實證）：派工單明講省著用、優先 WebFetch
  直打官方 URL 與 API；查核 A 排最後、最吃搜尋，前段就要省。
- 圖片量能（228–380 張新圖、38 個新 Drive 子夾）是全批唯一沒有前例的規模——
  **第一批＝小樣校準**：三區收稿時把「湊滿 6 張合規授權圖」的實際難度回報進度斷點，
  湊不滿回報缺口、不硬塞爛圖。

### 紅隊 Stage 2 裁決（2026-08-09，Stage 1 全文見 session 紀錄）
成立並已修入本節：towns_status 對高雄失明（→縣頁 `towns:` 38 條 KH-S1 先行加入）；
腳本不擋上限（→收稿閘改「腳本跑數字＋主對話人工核線」）；模板高雄節不存在（→併入後才准發批）；
計畫未版控（→本節與模板同 commit 進 kh-towns 並推 origin）；check-search-core-sync 在 worktree
fail-open（→重建 `_workspace/taiwan-arts-db` symlink）；§8 與 worktree 矛盾（→全鏈在 worktree 跑）；
`_workspace/` 未進 .gitignore（→補一行）；主題頁撞題無檢查（→查核 A 對 typhoon/placenames/
migration；敏感頁口徑逐字比對）；查核 B 單支過載（→拆兩支各 6 頁）；裝置台帳三套不互通
（→模板 §E 指向兩份 devices txt）；handoff 漏隱性狀態（→步驟 8 清單）。
不成立（一行理由）：改 5 頁分區制／拆兩條線＝範圍是 David 拍板的產品決策（38 區、今晨明示）；
發布壓成一次＝跨 session 積壓未驗證產出違反假收斂守衛，且 CI/golden 成本在 towns: 一次加齊後
大半消失；「12 區治不了漂移」＝節奏已拍板，主對話另以「查核報告讀檔不讀全文」自律。

### 進度斷點（每 session 收官更新；**磁碟才是事實來源**，這裡只放指標）

**2026-08-09 KH-S1 全鏈收官（12/38 上線；同日兩個 session 完成，本段由後半 session 收）**

- **12/38 全鏈上線**：批一批二（前半 session）＋批三 8fafa2c（前鎮、大樹、茂林）＋批四 eba5423
  （新興、彌陀、六龜🅰）→ 查核 A/B1/B2 → 修正輪 1489ec7（fresh 複驗三輪收斂全 PASS）→
  圖鏈＋12 hero d743dfd → push main → CI 31311842685 success（32m）→ **verify_live 1349/1350
  ＋新興 03 一張 503 單獨重驗 200（CDN 暫時抖）＝全綠**。12 頁腳本口徑 5186–5200 字、
  教學 35.8–39.9%、圖 108 張全 Commons。
- 查核結果：A **零事實錯誤**（抽驗 13 條全符；那瑪夏/六龜 A 級、鹽埕 B 級紀律全達標）；
  B 高3中9低7 全裁決落地——**F13「兩張圖對看」骨架判撞**，鼓山段1（「一個洞得到名字」）
  /鹽埕段3（「瀨南街名字存續」）已重寫換錨，台帳同步＋判撞註記。
- 派工 SSOT 回填（4e3dfa7，模板＋writing-plan 兩檔同步）：前鎮「世界第一加工出口區」改兩說並陳
  （香農 1959）；茂林改「切斷型環流丘」錨點（坪林互指）；**楠梓設立年代文獻分歧（批五動工前重查）**；
  **大寮伏流水始於 1942 高雄水道第五次擴建（批八要寫成延續非創舉）**。
- 市級頁錯字 辖域→轄域（bd5ed9d）——Kitesurf 雲端瀏覽器 markdown 抽取抓到；全站簡體掃描僅此一處。
- **live 驗收新路徑（David 2026-08-09 拍板）**：公開頁頁面層驗收改走 `~/MyWork/_scripts/kitesurf.sh`
  （markdown 驗文字＋截圖驗版面含手機視口），SOP 已入 docs/DEPLOY.md（ab9adb2）；
  verify_live_images.py 圖鏈硬閘不變。
- 跨頁備忘（本 session 新增；沿用前半 session 的楠梓台積電/岡山紅線/里編組三條）：
  **中央公園在前金區**（「中央公園商圈」之名在新興）；**高雄車站本體在三民區**（新興只寫站前側）；
  扇平（林試所）在六龜側＝六龜研究中心，茂林/六龜兩頁現況查核 A 已核無誤；
  民政局表1 最新可得月三次覆查仍＝115-03；
  前鎮 images #2 為原檔 URL 形式（Chienchen_River.jpg），批量 check-images 對它穩定 429＝既知假陽性。
- devices 台帳：12 區 36 段全入冊（docs/devices-used-kaohsiung.txt，含兩段重寫版）。
- **下一 session＝KH-S2（高雄五～八，12 區）**：批五 楠梓/路竹/旗津 → 批六 苓雅/大社/永安 →
  批七 三民/美濃/茄萣 → 批八 左營/甲仙🅰/大寮，照「每個 session 的固定流程」1–8；
  **甲仙 A 級**派工單附 typhoon.md 莫拉克段＋那瑪夏、六龜兩頁當口徑對照（口徑逐批收緊）。
- 隱性狀態清單：worktree `_workspace/geo-kh-wt`@kh-towns（已 rebase main、與 origin 一致，
  kh-towns 與 main 同指 d743dfd）；arts-db symlink 在；hero-prompts.yaml 高雄 12 條已入
  （鹽埕為改版 prompt）；used-images 清單在 scratchpad 會被清、用模板 §G 重生；
  三份查核報告在主 repo `_workspace/geo-kh-reviews/`（KH-S2 派工可參考，KH-S4 收官後可刪）。

## 0-Z. 臺東 16/16 全席上線（2026-08-08 收官；驗收已完成，剩清理）

**收工前最後一刻補記：CI run 31246307074 已 success（30m25s，常態時長）；
`verify_live_images.py` 於含臺東樹（east-towns＝main 2aac797）跑出 **1230/1230 全綠**——
臺東 16 頁正式上線，全站鄉鎮頁 89/89。下一個 session 只剩下面「要做的」§3 起的清理與欠帳。**

### 已完成（全在 commit 2aac797，已推上 origin/main）
16/16 母本（9 前批＋卑南/太麻里/金峰/大武/達仁/綠島/蘭嶼 7 支 Opus 三三批完成）→
查核 A（3 高全修：縣頁池上斷層觀察點錦園→**大坡國小**、海端 4,310／鹿野 6,983 升 115-07，
16 鄉加總＝縣頁 207,747 算術鎖死；南迴通車年 1992→1991）＋查核 B（六頁減脂 6,225–6,489→≤5,200、
「逐項列舉收攏」骨架 9 撞改寫 4、六頁教學特點開場去模板化）→ 圖片鏈（fetch／Drive 上傳逐檔比對過／
source titles）→ 16 hero（10 一次過、5 一修、**綠島三修**——「像動物的岩石」prompt 會生出雕像臉，
第三版整個拿掉擬像描述改畫朝日溫泉圓池才過；已上 Drive hero/、旗標全拆）→ golden 重定基準
（16 新頁進榜、縣頁因「地震儀」修正句入 --new 白名單、既有排序零改變、test-search 23 區塊全綠）→
check-images 15/16＋鹿野 #7 批量 429 單獨重驗 200（假陽性）→ rebase → **push main（a86a34c..2aac797）**。

### 下一個 session 要做的（照序）
1. `gh run list` 看 run 31246307074（2026-08-08 07:30Z 起，收工時跑到 27 分仍 in_progress——
   **這個 repo 的部署本來就要 28–30 分鐘**，前兩次成功 run 分別 27m51s／29m45s，別誤判成卡死）。
   若失敗：先看是暫時抖還是 undici（見 memory cloud-class-5a 前例），重跑即可，內容都在 main 上。
2. CI 綠後 `.venv/bin/python3 scripts/verify_live_images.py` 全綠才算上線（預期 +16 hero＋約 150 內容圖）。
3. 清理：`git worktree remove _workspace/geo-east-wt`＋`_workspace/geo-pub`、刪 east-towns／
   east-hualien-publish 分支（本地＋origin）、`_workspace/geo-east-reviews/`（兩份花蓮＋兩份臺東查核報告、
   dup-20260808 重複寫作件——查核 A 已用畢可刪）。
4. 縣頁欠帳（等 David）：taitung.md 文風「不是A而是B」×3、定位速覽 212 字超 150——都是舊稿既有，與
   基隆縣頁同病；davices 檔已含基隆節。臺東批查核 B 確認臺東頁與基隆裝置零撞。
5. NotebookLM「認識臺灣」補花蓮 13＋臺東 16（94→123），先問 David。
6. 臺東收官後下一縣市等 David 點名。

### 本批新坑（一行版）
寫作 agent 自量字數與 towns_status 口徑差 ~20%（自報 5,200＝腳本 6,300），派工單的字數上限
要明講「以 towns_status 口徑為準」；「像動物的岩石」類 prompt 直說擬像必出雕像臉，改寫景不寫像。

## 0-0. 基隆 7/7 全席收官（2026-08-06 完成）

**一句話**：**基隆 7/7 上線**——中正、信義、仁愛、中山、安樂、暖暖、七堵一批做完
（含 7 張情境 hero 同批生成，全站鄉鎮頁 60/60）。流程照 §4 SOP：紅隊→模板補洞
（臺北收官批 12 裝置＋基隆縣頁 3 裝置入 §E、基隆分工表入 §D）→7 支 Opus 平行寫作
（心跳＋看門狗，零凍死；看門狗誤報 3 次，教訓：**盯稿檔 mtime 才是誠實訊號，
transcript symlink 與已完工 agent 的心跳都會假死**）→查核 A（Sonnet，抓 2 高：主普壇
在中正非信義、信義人口 52,339→52,299 離群）＋查核 B（Sonnet，抓 1 高：仁愛/中正/安樂
「兩張地圖」裝置骨架三撞→保留中正、改寫另兩頁）→修正輪→圖片鏈 65 圖上 Drive（新建
7 子夾直接授權 SA）→golden「純新頁進榜 4 組、既有排序零改變」重定基準。
縣頁 stats 已同批升 2026-07 基期（358,287，七區加總精確吻合）。

寫作 agent 更正派工單 §D 的錯（下一批引以為戒，錯的形狀仍是「聽起來很順」）：
獅球嶺隧道南北口都在**安樂**非仁愛；大武崙溪**背海南流入基隆河**非入海灣；五堵六堵
主體在**七堵區內**非汐止；臺鐵五堵站站址在汐止保長坑；深澳線運煤對象是瑞芳深澳電廠
非八斗子北火；仙洞巖離海主因＝築港填地、抬升說證據不足；太平青鳥 2025-10 已歇業。

### 本批新欠帳（等 David）
9. 縣頁 keelung.md 文風禁令 2 命中（「不是 A，而是 B」×1、「從來不」×1）——舊稿既有，
   要不要回修等 David（其他縣市舊縣頁可能同病）。
10. 暖暖淨水場文化景觀登錄年份 2007（台水）vs 2020（區公所）兩說並陳，待官方文資網覆核。
11. 六堵「臺灣第一個工業區」僅維基＋文化記憶庫層級，無一級文獻，正文已保守。
12. 查核 B 低嚴重度觀察未修：七頁教學特點開場句式模板化（「這一區最適合教…」）；
    中正正文 5,256 字微超 5,200 上限（施工前既有，修正輪已淨降 27 字，容忍）。

## 0-A. 斷點交接：花蓮收官、臺東 7/16 定稿（2026-08-06 午，session 收單）

**下一個 session 從這裡接。進來第一件事照舊：跑 `towns_status.py taitung` 盤點磁碟，不要信下面的數字。**

### 臺東現況（2026-08-06 12:55 收單時）
- **9 區定稿、已過寫作自檢、有 §K 回報、已 commit 到 `origin/east-towns` 分支（7ab89d2）**：
  池上、關山、海端、鹿野、延平、長濱、成功、東河、臺東市（id `taitung-taitung`，檔名 `taitung-city.md`）。
  **未查核、未跑圖片鏈、未發布。零草稿懸案。** 派工單被查出的錯已由各頁修正（三仙台非火山岩頸、
  鹿野村是臺東製糖私營移民村非官營、內本鹿 1933 遷村在先 1941 事件在後等——細節見各支 §K 回報精神已入正文）。
  東河支自報一項紀律瑕疵：批次驗 sources 時誤將 tcmb.culture.tw 兩條納入 curl（回應正常、無凍結；
  授權欄位全程只走本機索引）——TCMB 禁令仍然有效，下批照守。
- **7 區完全未派**：卑南、太麻里、金峰、大武、達仁、綠島、蘭嶼。
- **David 拍板的節奏：寫作 agent 一次最多 4 支輪替**（一次 13 支被打回），一支收稿即補位一支。

### 續做清單（照序）
1. 在 worktree `_workspace/geo-east-wt`（分支 east-towns，已 rebase 到 374f2f0 後的 main）續派剩餘各區，
   派工單樣式照本批（模板 §D 臺東列＋兩份黑名單）。黑名單已持久化：
   **裝置黑名單＝repo `docs/devices-used-east.txt`**（/tmp 那份會被清）；
   已用圖片清單用模板 §G 程式碼即時重生。
2. 全縣收齊 → 查核 A（事實）＋查核 B（文風/撞題）各一支 → 修正一支。**既知修正清單**：
   ①海端 stats 是維基層級（2026-06）→ 用民政處 RRRP03320（115-07）補正（池上/延平/臺東市支都成功下載過，
   走 taitung.gov.tw 主站；部分 agent 對民政處子網域 NXDOMAIN）；
   ②鹿野 stats 同（2026-06 內政部→115-07 民政處）；
   ③長濱「臺灣最古老」措辭之文資局公告原文（nchdb 20060501000007）未能覆核，查核輪再試。
3. 圖片鏈照 §8（fetch --only 全部 16 個 taitung-* id → upload Drive → source titles）。
   ⚠ 原檔 URL 一律轉 /thumb/1280px（花蓮批 6 張踩過，修法＝母本與 manifest 鍵一起改）。
4. hero 16 張：prompt 照花蓮批做法派 Sonnet 從各頁定位速覽起草、append 進 hero-prompts.yaml；
   gen_hero_images.py 用系統 python3、low、並發 2；逐張目檢（地標與地質狀態）。
   生圖授權：David 2026-08-06 已為「花蓮＋臺東收官」整條線授權（嚴格 low），臺東沿用、不必重問。
5. 發布走隔離 worktree 模式（本批花蓮用 `_workspace/geo-pub`，分支 east-hualien-publish）：
   發布前 git fetch 看有無其他 session 推過 main → rebase → 乾淨 build（別把未定稿母本掃進
   pages-index/sitemap，這是開 worktree 的原因）→ golden `refresh --new` 白名單 →
   `towns_status.py taitung --check-images`（批量 429＝假陽性，單獨重驗；連 `check-search-core-sync`
   需要 sibling：`_workspace/taiwan-arts-db` symlink 已建）→ commit → push <branch>:main → CI →
   `verify_live_images.py` 全綠才算完。
6. 全部收完的清理：`git worktree remove` 兩個 worktree（geo-east-wt、geo-pub）＋刪 east-towns/
   east-hualien-publish 分支；`_workspace/geo-east-reviews/` 兩份花蓮查核報告收走或刪；
   縣頁 taitung.md 的 towns: 16 條已在（花蓮批一併 commit）。
7. 結案後：NotebookLM「認識臺灣」筆記本補花蓮 13＋臺東 16（94→123 來源，檔名帶縣名慣例），先問 David。

## 0-A(舊). 花蓮 13/13 全席收官（2026-08-06，與基隆同日）＋臺東進行中

**一句話**：**花蓮 13/13 上線**（commit 374f2f0，CI 綠、verify_live_images 1061/1061 全綠），
全站鄉鎮頁 73/73。同日稍早基隆 7/7 由另一 session 收官（603c0f8）。
**臺東 16 鄉鎮進行中**（同 session、worktree `_workspace/geo-east-wt`，分支 east-towns；
發布用第二 worktree `_workspace/geo-pub`，分支 east-hualien-publish——臺東收官後兩個 worktree 都要 `git worktree remove` 清掉）。

花蓮批做完的事：紅隊關卡攻出三條（同 checkout 雙 session 互踩→改 worktree 隔離；批量一次 13 支
→David 拍板改 4 支一批輪替；光復堰塞湖敏感頁特別紀律）；查核 A（38 對 1 錯 4 未定）＋查核 B
（高 2 中 1）→修正六件落檔；13 hero 全數目檢（豐濱一修：棋盤格假石磚）；6 張原檔 URL 轉 thumb
鐵則形式並同步 manifest 鍵；golden 重定基準（11 組純新頁進榜、既有排序零改變）。

### 本批新增的坑與紀律（看門狗三代教訓，續做必讀）
- **task .output 檔是 symlink**：`stat` 不加 `-L` 量到連結本身（大小恆 124、mtime 不動）——
  mtime 與 size 兩種活性判準都會因此全面誤報。正解＝`stat -L` 追真檔。
  （原 `/tmp/geo-hb/size-watch.sh` 是當批 scratchpad 暫存檔、已隨系統清除，別再去找；
  同型腳本另存 `~/MyWork/_scripts/agent-size-watch.sh`，惟該檔未入版控、去留待 David 裁決，
  引用前先確認它還在。要用的是上面那條 `stat -L` 紀律，不是特定腳本。）
- **心跳檔判準的兩種誤報**：①復活的 agent 還沒寫新心跳、被停機前舊時間戳觸發（重掛前先 touch）；
  ②完工 agent 心跳自然停止（每次收稿後重掛看門狗換名單）。
- **長自檢段（寫完稿後的字數自檢）可 20 分鐘不打心跳**——判死前先 tail transcript 內部 timestamp。
- **查核 A 的來源要分層**：搜尋引擎 AI 摘要不可信（吉安 19 名隘勇被它誤報成 18，PDF 原文覆核 19 正確）。
- 民政處網域 DNS 對部分 agent NXDOMAIN（鹿野、海端撞過）——臺東人口統計 PDF（RRRP03320）
  池上／延平支成功下載過，走 taitung.gov.tw 主站路徑。

### 花蓮批新欠帳（等 David）
9. 縣頁 hualien.md stats 是 2026-05（311,399），13 鄉鎮頁全是 2026-07（合計 311,067）——
   照「各頁自標年月不回頭統一」未動；要不要把縣頁 stats 更到 2026-07 等 David。
10. 臺東海端頁人口是維基層級（2026-06）、鹿野頁 2026-06 內政部——臺東查核輪要用 RRRP03320
   PDF 補到 2026-07 官方層級（已記入臺東修正清單）。

## 0-B(前). 臺北 12/12 全席收官（2026-08-05 完成，dispatch 2026-08-05-003）

**一句話**：**臺北 12/12 上線**——收官批大同、中正、大安、信義 4 區
（commit df0978b，CI 綠、verify_live_images 850/850 全綠），全站鄉鎮頁 53/53。
臺北段結案；NotebookLM 歸檔已補（2026-08-05：新北 29＋臺北 12 共 41 筆上傳
「認識臺灣」筆記本，來源 53→94，讀回全齊）。

**下一個縣市：基隆市（David 2026-08-05 點名，尚未動工、別自行開跑）**。7 個行政區
（中正、七堵、暖暖、仁愛、中山、安樂、信義）——一批做得完，動工前照 §4 SOP
（紅隊關卡必經）＋§7 派工模板；注意基隆自己的縣市頁已寫過雨港/丘陵港灣論點，
只准往更細一層下錨；「信義區」「中正區」「中山區」與臺北同名，檢索 golden 與
page id 命名（keelung- 前綴）要留意撞名。

收官批做完的事：紅隊 Stage1+2（孤兒題材收：文協/二二八/白恐/鐵道部/臺北車站/華山/
五分埔/富陽）；查核 A 12 處修正全落檔（含瑠公圳誤植改霧裡薛圳第二支線、臺北高校
1926 遷古亭町、刪幣原坦無據句、兵工廠 1976 更名二〇六廠、六張犁外省籍比例改
報導者原文 58%）；查核 B 兩輪全過；hero 4 張＋內容圖 39 張上 Drive（北門碉堡式、
101 竹節各一修）；search golden 2 組新頁進榜、既有頁排序零改變。

### 本批新欠帳（等 David）
6. 民生社區計畫人口 45,000/55,000/70,000 各方不一（松山頁已並陳），需 1964 原始計畫文件。
7. 中正「幼年人口比例最高」待官方統計覆核（正文已改保守「居全市前列」）。
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

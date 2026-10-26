# 旅遊地圖（首頁第四個分頁）

2026-10-26 David 從高雄比歐緻居房內的散步地圖起頭：先把那份摺頁逐項複刻成「高雄市・第 1 區」，
其餘區域照 `travel/kaohsiung/zones.yaml` 一區一區做，一區做完就上線。

| 東西 | 位置 |
|---|---|
| 分區規劃（範圍、站號、狀態） | `travel/<city>/zones.yaml` |
| 一區的資料 | `travel/<city>/<zone>-<slug>.yaml`（欄位說明在 kh-01 檔頭） |
| 定位快取 | `travel/<city>/<zone>.geo.json`（自動產生，可 commit） |
| 產頁腳本 | `scripts/travel.py` |
| 產出 | `site/travel/<city>/*.html`、`site/data/travel-index.json`（commit 進 repo；CI 的 build.py 不碰） |
| 前端 | `site/js/travel.js`、`site/css/travel.css`；首頁分頁在 `site/index.html` 的 `#travel` |
| 捷運＋輕軌合併路線圖 | `travel/<city>/metro.yaml`（站名站號、版面座標、轉乘說明）→ build 產 `site/data/metro-<city>.js`；前端 `site/js/metro.js` |

## 做一區（例：kh-02）

```bash
python3 scripts/travel.py new kh-02          # 依 zones.yaml 產骨架
# 填資料：照 zones.yaml 的 scope 查官網／Google 商家頁，每筆要地址、時間、電話、捷運站號與出口；查不到留空
python3 scripts/travel.py geocode kh-02      # Nominatim 自動定位（每秒 1 筆），印出查無的
#   查無或位置不對：該筆加 q:（好查的名稱）或 ll: [緯度, 經度]，再跑 geocode kh-02 --retry／--recheck
python3 scripts/travel.py build
python3 scripts/travel.py status
# zones.yaml 該區 status 改 done、下一區改 next → commit＋push（CI 上線）→ kitesurf 抽驗手機版
```

在 LINE 交辦：「ddd 旅遊地圖 高雄 第 2 區」。

## 定位的誠實範圍

- 只對到路段的點會用同一條路上已知門牌內插（`interp`），地圖上畫空心虛線圈；導航以卡片上的地址連結（Google 地圖）為準。
- `judge()` 擋掉行政區對不上的結果（曾把鼓山區忠義路對到杉林區忠義路）；界路門牌離分區中心 4 km 內才收。
- 站上只放文字資料，不放摺頁圖片（摺頁是飯店的版權物，事實資料不受限）。

## 捷運＋輕軌合併路線圖（2026-10-26 加）

- 城市有 `travel/<city>/metro.yaml` 時，build 會在**城市頁與每一區頁**的標題下放「捷運＋輕軌路線圖」導航鍵，
  點開是全螢幕路線圖（全圖／本區／縮放、兩指縮放拖曳、點站看轉乘與相關分區），網址帶 `#metro` 可直接分享開圖；
  頁面往下捲後左下角有浮動「路線圖」鍵。分區頁的「捷運與輕軌」段落改放同一張圖的縮圖，分線站表收進摺疊。
- 「本區在這」的圈：取 `zones.yaml` 該區的 `stations`（第一個站號掛標籤）。新區只要寫好 `stations` 就自動有。
- 站名站號以高捷官網「各車站資訊」為準；新站開通或改名改 `metro.yaml` 一處、build，所有頁一起更新。
- 圖是依官網營運路線圖的相對位置自繪的 SVG，不嵌官方圖檔。


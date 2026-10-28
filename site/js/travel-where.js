/* 旅遊地圖：「我在哪一區」判斷（城市頁 travel-city.js、分區頁 travel.js 共用；要先載 js/geo-core.js）
   分區資料由 scripts/travel.py 寫進 window.TV_ZONES：[{ id, order, name, districts, center, status, href }]
   （href 只有已上線的區才有；center 已上線用該區 yaml、未上線用 zones.yaml 的大約值）。

   判斷規則（兩頁一致）：
   1. 用鄉鎮界線查表找出所在縣市＋行政區（GeoCore.findTown，離線）。
   2. 在本城市 → 列出 districts 含這個行政區的分區；只有一區就是它，
      一個行政區分屬兩區（鼓山區南段 kh-02／北段 kh-04、苓雅區 kh-01／kh-06、三民區 kh-04／kh-07）
      取中心最近的那區。districts 裡的括號說明（「（南段）」）判斷時拿掉。
   3. 行政區沒有對應分區（例：湖內區）或不在本城市 → zone 為 null，另給離你最近的分區。
   4. 界線查表載不到 → town 為 null，只能看距離（呼叫端自己決定怎麼說）。 */
(function () {
  'use strict';
  if (!window.GeoCore) return;

  function clean(d) { return String(d || '').replace(/[（(].*?[）)]/g, '').trim(); }

  function judge(ll, towns, zones, city) {
    var town = towns ? GeoCore.findTown(towns, ll[1], ll[0]) : null;
    var byDist = zones.filter(function (z) { return z.center; }).map(function (z) {
      return { z: z, d: GeoCore.distKm(ll, z.center) };
    }).sort(function (a, b) { return a.d - b.d; });
    var inCity = town ? town.c === city : null;
    var zone = null;
    if (inCity) {
      for (var i = 0; i < byDist.length; i++) {
        if ((byDist[i].z.districts || []).map(clean).indexOf(town.t) >= 0) { zone = byDist[i].z; break; }
      }
    }
    return { town: town, inCity: inCity, zone: zone, byDist: byDist, nearest: byDist[0] || null };
  }

  // 「第 2 區〈鹽埕・哈瑪星・駁二〉」：已上線給連結，未上線附「（尚未上線）」
  function zoneLink(z, esc) {
    var label = '第 ' + z.order + ' 區〈' + esc(z.name) + '〉';
    return z.href ? '<a href="' + esc(z.href) + '">' + label + '</a>'
                  : label + '<span class="tv-soon">（尚未上線）</span>';
  }

  function kmText(km) { return km < 100 ? km.toFixed(1) : String(Math.round(km)); }

  window.TvWhere = { clean: clean, judge: judge, zoneLink: zoneLink, kmText: kmText };
})();

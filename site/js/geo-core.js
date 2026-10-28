/* 認識臺灣 — 定位共用小工具（首頁 locate.js、旅遊地圖 travel.js／travel-city.js 共用）
   全部在瀏覽器內算，座標不送出站外、不呼叫任何反查 API。
   - loadLookup(url)：載入並解碼鄉鎮界線查表 data/taiwan-towns-lookup.json
     （scripts/build_town_lookup.py 產出，約 560 KB；呼叫端在使用者按定位鈕時才載）
   - findTown(towns, lng, lat)：點在哪個鄉鎮（奇偶規則＋海邊 3 km 容差）→ { c: 縣市, t: 鄉鎮 } 或 null
   - distKm([lat, lng], [lat, lng])：兩點直線距離（公里）
   - fmtDist(km)：「350 m」「2.3 km」「85 km」
   - errorText(err)：定位錯誤 → 給人看的一句話（依 error.code，LINE 內建瀏覽器另外提示） */
(function () {
  'use strict';

  // 簡化過的海岸線會把海邊的點切在界外；距離最近鄉鎮界線這麼近就算那個鄉鎮。
  var NEAR_KM = 3;
  var cache = {};

  function loadLookup(url) {
    if (cache[url]) return cache[url];
    var p = cache[url] = fetch(url)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        var sx = d.s[0], sy = d.s[1], ox = d.o[0], oy = d.o[1];
        return d.towns.map(function (t) {
          var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
          var rings = t.r.map(function (enc) {
            var pts = new Float64Array(enc.length);
            var qx = 0, qy = 0;
            for (var i = 0; i < enc.length; i += 2) {
              qx += enc[i]; qy += enc[i + 1];
              var x = qx * sx + ox, y = qy * sy + oy;
              pts[i] = x; pts[i + 1] = y;
              if (x < x0) x0 = x; if (x > x1) x1 = x;
              if (y < y0) y0 = y; if (y > y1) y1 = y;
            }
            return pts;
          });
          return { c: t.c, t: t.t, rings: rings, box: [x0, y0, x1, y1] };
        });
      });
    p.catch(function () { delete cache[url]; });   // 失敗下次再抓
    return p;
  }

  // 奇偶規則：所有環一起算，洞與飛地都自然處理。
  function inside(town, x, y) {
    var hit = false;
    town.rings.forEach(function (p) {
      for (var i = 0, j = p.length - 2; i < p.length; j = i, i += 2) {
        var yi = p[i + 1], yj = p[j + 1];
        if ((yi > y) !== (yj > y) &&
            x < (p[j] - p[i]) * (y - yi) / (yj - yi) + p[i]) hit = !hit;
      }
    });
    return hit;
  }

  // 點到鄉鎮界線的最短距離（公里，局部等距近似）。
  function edgeKm(town, x, y) {
    var kx = 111.32 * Math.cos(y * Math.PI / 180), ky = 110.57;
    var best = Infinity;
    town.rings.forEach(function (p) {
      for (var i = 2; i < p.length; i += 2) {
        var ax = (p[i - 2] - x) * kx, ay = (p[i - 1] - y) * ky;
        var bx = (p[i] - x) * kx, by = (p[i + 1] - y) * ky;
        var dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
        var t = L ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / L)) : 0;
        var ex = ax + t * dx, ey = ay + t * dy, d = ex * ex + ey * ey;
        if (d < best) best = d;
      }
    });
    return Math.sqrt(best);
  }

  function findTown(towns, x, y) {
    var pad = NEAR_KM / 100, near = null, nearD = Infinity;
    for (var k = 0; k < towns.length; k++) {
      var t = towns[k], b = t.box;
      if (x < b[0] - pad || x > b[2] + pad || y < b[1] - pad || y > b[3] + pad) continue;
      if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3] && inside(t, x, y)) return t;
      var d = edgeKm(t, x, y);
      if (d < nearD) { nearD = d; near = t; }
    }
    return nearD <= NEAR_KM ? near : null;
  }

  function distKm(a, b) {
    var R = 6371, r = Math.PI / 180;
    var dLat = (b[0] - a[0]) * r, dLng = (b[1] - a[1]) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function fmtDist(km) {
    if (km < 1) return (Math.max(10, Math.round(km * 100) * 10)) + ' m';
    if (km < 10) return km.toFixed(1) + ' km';
    return Math.round(km) + ' km';
  }

  // LINE 內建瀏覽器（UA 帶「Line/」）常拿不到定位
  function inLine() { return / Line\//i.test(navigator.userAgent || ''); }

  function errorText(err) {
    var code = err && err.code;
    var msg = {
      1: '沒有給定位權限（iPhone 請到 設定 › Safari › 位置 允許；Android 請點網址列左邊的鎖頭允許位置）',
      2: '訊號不足，暫時抓不到位置（到室外或靠窗再試一次）',
      3: '定位逾時，請再按一次'
    }[code] || (err && err.message === 'unsupported' ? '這個瀏覽器不能定位' : '定位失敗');
    // LINE 裡最有用的是換瀏覽器，放前面
    if (inLine()) return '拿不到位置：LINE 內建瀏覽器常拿不到定位，請按右上角「⋯」改用 Safari／Chrome 開啟。（' + msg + '）';
    return '拿不到位置：' + msg + '。';
  }

  // 瀏覽器能不能定位（http 非 localhost 的頁面也不行）
  function canLocate() { return !!navigator.geolocation && window.isSecureContext !== false; }

  window.GeoCore = {
    NEAR_KM: NEAR_KM, loadLookup: loadLookup, findTown: findTown,
    distKm: distKm, fmtDist: fmtDist, errorText: errorText, inLine: inLine, canLocate: canLocate
  };
})();

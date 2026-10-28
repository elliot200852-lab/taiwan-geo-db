/* 旅遊地圖城市頁：「📍 我在哪一區」——定位一次，判斷所在分區，畫一張小地圖，分區卡片依你的位置標出來。
   要先載 vendor/leaflet.js、js/geo-core.js、js/travel-where.js；分區資料是 scripts/travel.py 寫的 window.TV_ZONES。
   只有按下按鈕才向瀏覽器要位置權限；座標只在瀏覽器裡算（鄉鎮界線查表），不送出站外。 */
(function () {
  'use strict';
  var btn = document.getElementById('tv-where-btn');
  if (!btn || !window.GeoCore || !window.TvWhere) return;
  var G = window.GeoCore, W = window.TvWhere;
  var ZONES = window.TV_ZONES || [], CITY = window.TV_CITY || '';
  var LOOKUP = window.TV_LOOKUP || '../../data/taiwan-towns-lookup.json';
  var ACCURACY_LIMIT = 3000;   // 精度差於此（公尺）就提醒結果可能不準（桌機多半靠 IP／Wi-Fi 推位置）
  var msg = document.getElementById('tv-where-msg');
  var mapEl = document.getElementById('tv-where-map');
  var list = document.querySelector('.tv-zones');
  var cards = list ? Array.prototype.slice.call(list.querySelectorAll('.tv-zc[data-zone]')) : [];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function say(html, tone) {
    msg.innerHTML = html || '';
    msg.className = 'tv-where-msg' + (tone ? ' is-' + tone : '');
  }
  function done() { btn.disabled = false; btn.classList.remove('is-busy'); }

  // ---------- 小地圖 ----------
  var map = null, meDot = null, meRing = null, zMarks = {};
  function ensureMap() {
    mapEl.hidden = false;
    if (map) { map.invalidateSize(); return; }
    map = L.map(mapEl, { scrollWheelZoom: false });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 貢獻者'
    }).addTo(map);
    map.createPane('tvMe').style.zIndex = 650;   // 藍點畫在分區圓點之上，不被蓋住
    ZONES.forEach(function (z) {
      if (!z.center) return;
      var on = !!z.href;
      var m = L.marker(z.center, {
        title: '第 ' + z.order + ' 區 ' + z.name,
        icon: L.divIcon({ className: 'tv-zpin' + (on ? ' is-on' : ''), html: '<span>' + z.order + '</span>',
                          iconSize: [30, 30], iconAnchor: [15, 15], popupAnchor: [0, -14] })
      }).addTo(map);
      m.bindPopup('<div class="tv-pop"><strong>第 ' + z.order + ' 區・' + esc(z.name) + '</strong>' +
                  '<div>' + esc((z.districts || []).join('・')) + '</div>' +
                  '<div class="tv-pop-a">' + (on ? '<a href="' + esc(z.href) + '">打開這區的地圖 ›</a>' : '尚未上線') +
                  '</div></div>');
      zMarks[z.id] = m;
    });
  }

  function drawMe(ll, acc, r) {
    ensureMap();
    if (meDot) { map.removeLayer(meDot); map.removeLayer(meRing); }
    meRing = L.circle(ll, { pane: 'tvMe', radius: acc, color: '#1a73e8', weight: 1, opacity: .5, fillColor: '#1a73e8', fillOpacity: .12, interactive: false }).addTo(map);
    meDot = L.circleMarker(ll, { pane: 'tvMe', radius: 8, color: '#fff', weight: 3, fillColor: '#1a73e8', fillOpacity: 1 })
      .addTo(map).bindPopup('你在這裡');
    var pts = [];
    if (r.inCity || (r.nearest && r.nearest.d < 30)) {
      // 在城市裡：框你、你所在那區、離你最近的三區
      pts.push(ll);
      if (r.zone) pts.push(r.zone.center);
      r.byDist.slice(0, 3).forEach(function (w) { pts.push(w.z.center); });
      map.fitBounds(L.latLngBounds(pts).pad(0.2), { maxZoom: 14 });
    } else {
      // 人在外縣市：地圖還是看這個城市的全部分區（你的藍點在畫面外）
      r.byDist.forEach(function (w) { pts.push(w.z.center); });
      map.fitBounds(L.latLngBounds(pts).pad(0.2), { paddingTopLeft: [40, 20] });
    }
    // 圖釘要等地圖有視野才會產生 DOM，所以放在 fitBounds 之後標「你所在那區」
    Object.keys(zMarks).forEach(function (id) {
      var ic = zMarks[id].getElement && zMarks[id].getElement();
      if (ic) ic.classList.toggle('is-here', !!(r.zone && r.zone.id === id));
    });
  }

  // ---------- 分區卡片：你那區亮起並移到第一個，其他標距離 ----------
  function markCards(r) {
    cards.forEach(function (c) {
      c.classList.remove('tv-zc--here');
      c.querySelectorAll('.tv-zc-far, .tv-zc-me').forEach(function (n) { n.remove(); });
      list.appendChild(c);   // 先照原本順序排回來（重按時用）
    });
    var dist = {};
    r.byDist.forEach(function (w) { dist[w.z.id] = w.d; });
    cards.forEach(function (c) {
      var id = c.getAttribute('data-zone');
      var h = c.querySelector('.tv-zc-h');
      if (r.zone && id === r.zone.id) {
        c.classList.add('tv-zc--here');
        var me = document.createElement('span');
        me.className = 'tv-zc-me';
        me.textContent = '你在這區';
        h.insertBefore(me, h.querySelector('.tv-st-tag'));
        list.insertBefore(c, list.firstChild);
      } else if (dist[id] != null) {
        var d = c.querySelector('.tv-zc-d');
        var far = document.createElement('span');
        far.className = 'tv-zc-far';
        far.textContent = '離你約 ' + G.fmtDist(dist[id]);
        d.appendChild(far);
      }
    });
  }

  // ---------- 定位 ----------
  var towns = null;
  function onFix(pos) {
    var ll = [pos.coords.latitude, pos.coords.longitude], acc = pos.coords.accuracy || 0;
    towns.then(function (t) {
      done();
      var r = W.judge(ll, t, ZONES, CITY);
      var near = r.nearest ? '離你最近的是' + W.zoneLink(r.nearest.z, esc) + '・直線約 ' + G.fmtDist(r.nearest.d) : '';
      var html, tone = 'ok';
      if (!r.town) {
        tone = 'warn';
        html = (t ? '定位到的位置不在臺灣的鄉鎮範圍內。' : '鄉鎮界線資料沒載到，看不出你在哪個行政區。') + near;
      } else if (!r.inCity) {
        tone = 'warn';
        html = '你目前在' + esc(r.town.c + r.town.t) + '，不在' + esc(CITY) + '。' + near;
      } else if (r.zone) {
        html = '你在' + esc(r.town.c + r.town.t) + ' → ' + W.zoneLink(r.zone, esc);
      } else {
        tone = 'warn';
        html = '你在' + esc(r.town.c + r.town.t) + '，這個行政區還沒排進分區。' + near;
      }
      if (acc > ACCURACY_LIMIT) {
        html += '<br><small>定位精度只有約 ' + G.fmtDist(acc / 1000) + '，結果可能不準。</small>';
      }
      say(html, tone);
      drawMe(ll, acc, r);
      markCards(r);
    });
  }

  function onErr(err) {
    done();
    say(esc(G.errorText(err)), 'warn');
  }

  btn.addEventListener('click', function () {
    if (!G.canLocate()) { say(esc(G.errorText({ message: 'unsupported' })), 'warn'); return; }
    btn.disabled = true;
    btn.classList.add('is-busy');
    say('定位中⋯（第一次使用，瀏覽器會問你是否允許）');
    towns = G.loadLookup(LOOKUP).catch(function () { return null; });   // 與定位同時開抓界線資料
    navigator.geolocation.getCurrentPosition(onFix, onErr,
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  });
})();

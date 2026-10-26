/* 旅遊地圖分區頁：Leaflet 圖釘、類別篩選、卡片↔地圖互跳、我的位置。
   資料由 scripts/travel.py 寫進 window.TV_PINS／TV_CATS／TV_VIEW。 */
(function () {
  var el = document.getElementById('tv-map');
  if (!el || !window.L) return;
  var pins = window.TV_PINS || [], cats = window.TV_CATS || {}, view = window.TV_VIEW || {};
  var map = L.map(el, { scrollWheelZoom: false, tap: true })
    .setView(view.center || [22.625, 120.301], view.zoom || 15);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 貢獻者'
  }).addTo(map);

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  var layers = {}, byIdx = {}, all = [];
  pins.forEach(function (p) {
    var col = cats[p.cat] || '#555';
    var approx = p.prec === 'road' || p.prec === 'interp';
    var m = L.circleMarker(p.ll, {
      radius: p.cat === 'start' ? 10 : 7, color: col, weight: approx ? 2 : 1.5,
      fillColor: approx ? '#fff' : col, fillOpacity: approx ? 0.85 : 0.9, dashArray: approx ? '3 2' : null
    });
    var no = p.n ? '<b class="tv-pop-no" style="background:' + col + '">' + esc(p.n) + '</b> ' : '';
    m.bindPopup(
      '<div class="tv-pop">' + no + '<strong>' + esc(p.zh) + '</strong>' +
      '<div>' + esc(p.addr) + (approx ? '<br><small>（位置是推估，以導航為準）</small>' : '') + '</div>' +
      '<div class="tv-pop-a"><a href="' + p.g + '" target="_blank" rel="noopener">Google 地圖導航</a>' +
      ' ・ <a href="#p' + p.i + '">看資料</a></div></div>');
    (layers[p.cat] = layers[p.cat] || L.layerGroup().addTo(map)).addLayer(m);
    byIdx[p.i] = m; all.push(m);
  });

  // 類別篩選
  document.querySelectorAll('.tv-chip').forEach(function (b) {
    b.addEventListener('click', function () {
      var c = b.getAttribute('data-cat'), on = !b.classList.contains('on');
      b.classList.toggle('on', on);
      if (layers[c]) { on ? layers[c].addTo(map) : map.removeLayer(layers[c]); }
    });
  });

  // 地圖控制：散步圈／全市／我的位置
  var ctl = L.control({ position: 'topright' });
  ctl.onAdd = function () {
    var d = L.DomUtil.create('div', 'tv-ctl');
    d.innerHTML = '<button type="button" data-v="home">散步圈</button>' +
                  '<button type="button" data-v="all">全部</button>' +
                  '<button type="button" data-v="me">我在哪</button>';
    L.DomEvent.disableClickPropagation(d);
    d.addEventListener('click', function (e) {
      var v = e.target.getAttribute('data-v');
      if (v === 'home') map.setView(view.center, view.zoom || 15);
      if (v === 'all' && all.length) map.fitBounds(L.featureGroup(all).getBounds().pad(0.05));
      if (v === 'me') map.locate({ setView: true, maxZoom: 16 });
    });
    return d;
  };
  ctl.addTo(map);
  var meMark = null;
  map.on('locationfound', function (e) {
    if (meMark) map.removeLayer(meMark);
    meMark = L.circleMarker(e.latlng, { radius: 8, color: '#1a73e8', fillColor: '#1a73e8', fillOpacity: 0.9, weight: 3 })
      .addTo(map).bindPopup('你在這裡').openPopup();
  });
  map.on('locationerror', function () { alert('拿不到位置（瀏覽器沒給定位權限）'); });

  // 卡片上的「📍 地圖」→ 捲到地圖並開彈窗
  document.querySelectorAll('.tv-pin').forEach(function (b) {
    b.addEventListener('click', function () {
      var m = byIdx[b.getAttribute('data-pin')];
      if (!m) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      map.setView(m.getLatLng(), Math.max(map.getZoom(), 16));
      setTimeout(function () { m.openPopup(); }, 350);
    });
  });
})();

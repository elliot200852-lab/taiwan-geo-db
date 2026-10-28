/* 旅遊地圖分區頁：Leaflet 圖釘、類別篩選、卡片↔地圖互跳、我的位置（持續定位）。
   資料由 scripts/travel.py 寫進 window.TV_PINS／TV_CATS／TV_VIEW，分區判斷用 TV_ZONES／TV_HERE／TV_CITY；
   定位共用 js/geo-core.js、js/travel-where.js（要先載）。 */
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

  // 地圖控制（右上）：散步圈／全部。定位鍵在右下，見下方「我的位置」。
  var ctl = L.control({ position: 'topright' });
  ctl.onAdd = function () {
    var d = L.DomUtil.create('div', 'tv-ctl');
    d.innerHTML = '<button type="button" data-v="home">散步圈</button>' +
                  '<button type="button" data-v="all">全部</button>';
    L.DomEvent.disableClickPropagation(d);
    d.addEventListener('click', function (e) {
      var v = e.target.getAttribute('data-v');
      if (v) unfollow();
      if (v === 'home') map.setView(view.center, view.zoom || 15);
      if (v === 'all' && all.length) map.fitBounds(L.featureGroup(all).getBounds().pad(0.05));
    });
    return d;
  };
  ctl.addTo(map);

  // ---------- 我的位置：持續定位、藍點＋精度圈、跟隨、不在本區提示、店卡距離 ----------
  // 按鍵三態：off（沒在定位）→ 按 → follow（追蹤＋地圖跟著你，鍵亮藍底）
  //   follow 時自己拖地圖（或按散步圈／全部／卡片的「📍 地圖」）→ track（照樣追蹤、藍點會動，地圖不動；鍵是藍色圖示）
  //   track 時按 → 回到 follow 並把地圖移回你；follow 時再按 → 關閉定位（藍點、距離小標、提示條都收掉）。
  // 第一次定到位：在本區 → 地圖移到你（縮放至少 16）；不在本區但離本區中心 30 km 內 → 縮放到同時看得到你和本區；
  //   更遠（例如人在臺北先看高雄）→ 地圖留在本區、改成 track，提示條說你在哪，想看自己再按一次鍵。
  // 只有按下定位鍵才向瀏覽器要位置權限；座標只在瀏覽器裡算，不送出站外。
  var ZONES = window.TV_ZONES || [], HERE = window.TV_HERE, CITY = window.TV_CITY || '';
  var LOOKUP = window.TV_LOOKUP || '../../data/taiwan-towns-lookup.json';
  var hereZone = ZONES.filter(function (z) { return z.id === HERE; })[0] || { center: view.center, districts: [] };
  var FAR_KM = 30;          // 超過這個距離，第一次定位不把地圖拉走
  var RECALC_M = 20;        // 位置移動超過這麼多公尺才重算店卡距離與所在分區（節流）
  var me = { mode: 'off', watch: null, ll: null, acc: 0, dot: null, ring: null, first: true, last: null, towns: null };
  var G = window.GeoCore, W = window.TvWhere;

  var CROSS = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="6.5"/>' +
              '<path d="M12 2.5v3.5M12 18v3.5M2.5 12H6M18 12h3.5"/><circle class="tv-loc-dot" cx="12" cy="12" r="2.6"/></svg>';
  var locBtn;
  var loc = L.control({ position: 'bottomright' });
  loc.onAdd = function () {
    var d = L.DomUtil.create('div', 'tv-loc-wrap');
    d.innerHTML = '<button type="button" class="tv-loc" aria-label="顯示我的位置" title="顯示我的位置">' + CROSS + '</button>';
    L.DomEvent.disableClickPropagation(d);
    locBtn = d.firstChild;
    locBtn.addEventListener('click', onLocClick);
    return d;
  };
  loc.addTo(map);

  // 地圖框頂端的提示條（不在本區、定位錯誤）
  var box = map.getContainer();
  var bar = L.DomUtil.create('div', 'tv-geo-bar', box);
  bar.setAttribute('role', 'status');
  bar.hidden = true;
  bar.innerHTML = '<p class="tv-geo-msg"></p><button type="button" class="tv-geo-x" aria-label="關閉提示">×</button>';
  L.DomEvent.disableClickPropagation(bar);
  L.DomEvent.disableScrollPropagation(bar);
  var barMsg = bar.firstChild, barKey = null, barTimer = null;
  bar.lastChild.addEventListener('click', function () { hideBar(); });
  function showBar(html, tone, key, autoHideMs) {
    if (key && key === barKey && bar.hidden) return;   // 同一則已被使用者關掉，不再跳
    barKey = key || null;
    barMsg.innerHTML = html;
    bar.className = 'tv-geo-bar' + (tone ? ' is-' + tone : '');
    bar.hidden = false;
    box.classList.add('tv-bar-on');
    box.style.setProperty('--tv-bar-h', bar.offsetHeight + 'px');   // 右上控制鍵讓位到提示條下方
    clearTimeout(barTimer);
    if (autoHideMs) barTimer = setTimeout(hideBar, autoHideMs);
  }
  function hideBar() {
    bar.hidden = true;
    box.classList.remove('tv-bar-on');
    clearTimeout(barTimer);
  }

  function setMode(m) {
    me.mode = m;
    locBtn.classList.toggle('is-follow', m === 'follow');
    locBtn.classList.toggle('is-track', m === 'track');
    locBtn.setAttribute('aria-pressed', m === 'off' ? 'false' : 'true');
    var t = { off: '顯示我的位置', follow: '跟隨中・再按一次關閉定位', track: '回到我的位置並跟隨' }[m];
    locBtn.title = t; locBtn.setAttribute('aria-label', t);
  }
  function unfollow() { if (me.mode === 'follow') setMode('track'); }
  map.on('dragstart', unfollow);   // 只有使用者拖動才會觸發；程式移動地圖不算

  function onLocClick() {
    if (me.mode === 'off') return start();
    if (me.mode === 'track') {
      setMode('follow');
      if (me.ll) map.setView(me.ll, Math.max(map.getZoom(), 16));
      return;
    }
    stop();
    hideBar();
  }

  function start() {
    if (!G || !G.canLocate()) { showBar(esc(G ? G.errorText({ message: 'unsupported' }) : '這個瀏覽器不能定位'), 'warn'); return; }
    hideBar(); barKey = null;
    me.first = true; me.last = null;
    setMode('follow');
    locBtn.classList.add('is-wait');
    me.towns = G.loadLookup(LOOKUP).catch(function () { return null; });   // 與定位同時開抓界線資料
    me.watch = navigator.geolocation.watchPosition(onPos, onErr,
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
  }

  function stop() {
    if (me.watch != null) navigator.geolocation.clearWatch(me.watch);
    me.watch = null; me.ll = null;
    if (me.dot) { map.removeLayer(me.dot); map.removeLayer(me.ring); me.dot = me.ring = null; }
    document.querySelectorAll('.tv-dist').forEach(function (n) { n.remove(); });
    locBtn.classList.remove('is-wait');
    setMode('off');
  }

  function onErr(err) {
    // 已經有位置時，偶發的訊號不足／逾時不打斷追蹤；權限被拒或一開始就拿不到才停。
    if (me.ll && err && err.code !== 1) return;
    stop();
    showBar(esc(G.errorText(err)), 'warn');
  }

  function onPos(pos) {
    var ll = [pos.coords.latitude, pos.coords.longitude], acc = pos.coords.accuracy || 0;
    me.ll = ll; me.acc = acc;
    locBtn.classList.remove('is-wait');
    if (!me.dot) {
      if (!map.getPane('tvMe')) map.createPane('tvMe').style.zIndex = 650;   // 藍點畫在圖釘之上
      me.ring = L.circle(ll, { pane: 'tvMe', radius: acc, color: '#1a73e8', weight: 1, opacity: .5, fillColor: '#1a73e8', fillOpacity: .12, interactive: false }).addTo(map);
      me.dot = L.circleMarker(ll, { pane: 'tvMe', radius: 8, color: '#fff', weight: 3, fillColor: '#1a73e8', fillOpacity: 1 })
        .addTo(map).bindPopup('你在這裡');
    } else {
      me.ring.setLatLng(ll).setRadius(acc);
      me.dot.setLatLng(ll);
    }
    if (!me.first && me.mode === 'follow') map.panTo(ll);
    if (me.last && G.distKm(me.last, ll) * 1000 <= RECALC_M) return;
    me.last = ll;
    updateCards(ll);
    me.towns.then(function (towns) {
      if (!me.ll) return;            // 期間已關閉定位
      var inZone = updateWhere(ll, towns);
      if (me.first) { me.first = false; firstView(ll, inZone); }
    });
  }

  function firstView(ll, inZone) {
    if (me.mode !== 'follow') return;   // 定到位之前使用者已經自己拖地圖了
    var d = G.distKm(ll, hereZone.center || view.center);
    if (inZone) map.setView(ll, Math.max(map.getZoom(), 16));
    else if (d <= FAR_KM) map.fitBounds(L.latLngBounds([ll, hereZone.center || view.center]).pad(0.25), { maxZoom: 16 });
    else setMode('track');
  }

  // 店卡「離你直線 350 m」：有圖釘的卡才有
  function updateCards(ll) {
    pins.forEach(function (p) {
      var card = document.getElementById('p' + p.i);
      var tags = card && card.querySelector('.tv-tags');
      if (!tags) return;
      var tag = tags.querySelector('.tv-dist');
      if (!tag) {
        tag = document.createElement('span');
        tag.className = 'tv-dist';
        tag.title = '直線距離，不是步行或開車的路程';
        tags.insertBefore(tag, tags.firstChild);
      }
      tag.textContent = '離你直線 ' + G.fmtDist(G.distKm(ll, p.ll));
    });
  }

  // 判斷在不在本區（規則見 js/travel-where.js：所在行政區 → 分區，同一行政區分屬兩區取中心最近），回傳 true／false
  function updateWhere(ll, towns) {
    var r = W.judge(ll, towns, ZONES, CITY);
    var dHere = G.distKm(ll, hereZone.center || view.center);
    var accNote = me.acc > 500 ? '（定位精度約 ' + G.fmtDist(me.acc / 1000) + '，距離僅供參考）' : '';
    var inZone = r.town ? !!(r.zone && r.zone.id === HERE) : dHere <= 2;   // 沒有界線資料：離中心 2 km 內才算
    if (inZone) {
      showBar('你在本區' + (r.town ? '（' + esc(r.town.t) + '）' : '') + '・店卡已標出離你多遠' + accNote, 'ok', 'in', 5000);
      return true;
    }
    var where = r.town ? (r.inCity ? esc(r.town.t) : esc(r.town.c + r.town.t)) : '';
    var html = (where ? '你目前在' + where + '，不在這一區' : '你不在這一區') +
               '・離本區中心約 ' + W.kmText(dHere) + ' 公里';
    if (r.zone) html += ' → ' + W.zoneLink(r.zone, esc);
    else if (r.inCity && r.nearest) html += '・離你最近的是' + W.zoneLink(r.nearest.z, esc);
    else if (!r.town && towns === null) html += '（界線資料沒載到，看不出你在哪個行政區）';
    showBar(html + accNote, 'info', 'out:' + (r.zone ? r.zone.id : '') + ':' + where);
    return false;
  }

  // 頁面右下的浮動導覽鈕（geo-fab）是固定在視窗的；地圖捲到視窗底部時定位鍵往上讓，不疊在一起。
  var fabEl = document.querySelector('#geo-fab .geo-fab-toggle'), dodgeQ = false;
  function dodgeFab() {
    dodgeQ = false;
    if (!fabEl || !locBtn) return;
    var wrap = locBtn.parentNode;
    wrap.style.marginBottom = '';
    var a = locBtn.getBoundingClientRect(), b = fabEl.getBoundingClientRect(), m = box.getBoundingClientRect();
    var overlap = a.right > b.left - 8 && a.left < b.right + 8 && a.bottom > b.top - 8 && a.top < b.bottom + 8;
    if (!overlap) return;
    var lift = a.bottom - (b.top - 8);
    if (a.top - lift < m.top + 60) return;   // 地圖露出太少就不硬擠
    wrap.style.marginBottom = (10 + lift) + 'px';
  }
  function queueDodge() { if (!dodgeQ) { dodgeQ = true; requestAnimationFrame(dodgeFab); } }
  window.addEventListener('scroll', queueDodge, { passive: true });
  window.addEventListener('resize', function () {
    queueDodge();
    if (!bar.hidden) box.style.setProperty('--tv-bar-h', bar.offsetHeight + 'px');
  });
  queueDodge();

  // 卡片上的「📍 地圖」→ 捲到地圖並開彈窗
  document.querySelectorAll('.tv-pin').forEach(function (b) {
    b.addEventListener('click', function () {
      var m = byIdx[b.getAttribute('data-pin')];
      if (!m) return;
      unfollow();
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      map.setView(m.getLatLng(), Math.max(map.getZoom(), 16));
      setTimeout(function () { m.openPopup(); }, 350);
    });
  });
})();

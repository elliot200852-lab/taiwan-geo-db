/* 旅遊地圖・捷運＋輕軌合併路線圖（同城市每一頁共用）
   資料：window.METRO（site/data/metro-<city>.js，由 scripts/travel.py build 產生）
   頁面約定：
     [data-metro-open]          點了打開全螢幕路線圖（頂部導航鍵、頁內預覽圖）
     .mt-preview                 頁內放一張不可操作的縮圖，點了打開
     body[data-metro-here]       本頁這一區的站號（逗號分隔），圖上圈起來；body[data-metro-label] 圈旁的字
   網址帶 #metro 直接打開（可分享）；手機返回鍵關閉。 */
(function () {
  var M = window.METRO;
  if (!M) return;
  var here = (document.body.getAttribute('data-metro-here') || '').split(',').filter(function (c) { return M.st[c]; });
  var hereLabel = document.body.getAttribute('data-metro-label') || '本區';
  var NS = 'http://www.w3.org/2000/svg';

  function markHere(svg) {
    var layer = svg.querySelector('.mt-here-layer');
    if (!layer) return;
    here.forEach(function (c, i) {
      var xy = M.st[c].xy;
      var ring = document.createElementNS(NS, 'circle');
      ring.setAttribute('cx', xy[0]); ring.setAttribute('cy', xy[1]); ring.setAttribute('r', 20);
      ring.setAttribute('class', 'mt-here-ring');
      layer.appendChild(ring);
      if (i === 0) {
        var t = document.createElementNS(NS, 'text');
        t.setAttribute('x', xy[0] + 32); t.setAttribute('y', xy[1] - 22);
        t.setAttribute('class', 'mt-here-tag');
        t.textContent = '◀ ' + hereLabel + '在這';
        layer.appendChild(t);
      }
    });
  }

  // 頁內預覽縮圖
  Array.prototype.forEach.call(document.querySelectorAll('.mt-preview'), function (el) {
    el.insertAdjacentHTML('afterbegin', M.svg);
    markHere(el.querySelector('svg'));
    el.setAttribute('tabindex', '0');
    // iOS Safari 對非按鈕元素只靠 document 委派收不到 click，直接掛
    el.addEventListener('click', function () { open(); });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });

  // 全螢幕
  var ov = document.createElement('div');
  ov.className = 'mt-ov';
  ov.hidden = true;
  ov.setAttribute('role', 'dialog');
  ov.setAttribute('aria-label', M.title);
  ov.innerHTML =
    '<div class="mt-bar"><strong class="mt-title">' + M.title + '</strong>' +
    '<button type="button" data-act="fit">全圖</button>' +
    (here.length ? '<button type="button" data-act="here">本區</button>' : '') +
    '<button type="button" data-act="in" aria-label="放大">＋</button>' +
    '<button type="button" data-act="out" aria-label="縮小">－</button>' +
    '<button type="button" data-act="close" class="mt-x" aria-label="關閉">✕</button></div>' +
    '<div class="mt-stage">' + M.svg + '</div>' +
    '<div class="mt-info" hidden></div>' +
    '<p class="mt-hint">兩指縮放・拖曳移動・點車站看轉乘</p>';
  document.body.appendChild(ov);
  var stage = ov.querySelector('.mt-stage');
  var svg = stage.querySelector('svg');
  var info = ov.querySelector('.mt-info');
  markHere(svg);

  var full = M.view.slice();
  var vb = full.slice();
  function apply() { svg.setAttribute('viewBox', vb.join(' ')); }
  function toSvg(cx, cy) {
    var p = svg.createSVGPoint(); p.x = cx; p.y = cy;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
  function zoomAt(cx, cy, f) {
    var p = toSvg(cx, cy);
    var nw = Math.max(full[2] / 14, Math.min(full[2] * 1.3, vb[2] / f));
    var k = nw / vb[2];
    vb = [p.x - (p.x - vb[0]) * k, p.y - (p.y - vb[1]) * k, nw, vb[3] * k];
    apply();
  }
  function zoomCenter(f) {
    var r = svg.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, f);
  }
  function fit() { vb = full.slice(); apply(); }
  function focus(code, w) {
    var xy = M.st[code].xy;
    var r = svg.getBoundingClientRect();
    var ww = w || full[2] / 3;
    var hh = ww * (r.height / Math.max(r.width, 1));
    vb = [xy[0] - ww / 2, xy[1] - hh / 2, ww, hh];
    apply();
  }

  function showInfo(code) {
    var s = M.st[code];
    if (!s) return;
    var col = M.colors[s.l];
    var html = '<button type="button" class="mt-info-x" aria-label="關閉">✕</button>' +
      '<div class="mt-info-h"><b class="mt-code" style="--lc:' + col + '">' + code + '</b>' +
      '<span class="mt-info-zh">' + s.zh + '</span><small>' + M.names[s.l] + '</small></div>';
    if (s.note) html += '<p>' + s.note + '</p>';
    if (s.zones) {
      html += '<p class="mt-info-z">旅遊地圖：' + s.zones.map(function (z) {
        var t = '第 ' + z.order + ' 區 ' + z.name;
        return z.href ? '<a href="' + z.href + '">' + t + '</a>' : '<span>' + t + '（規劃中）</span>';
      }).join('、') + '</p>';
    }
    info.innerHTML = html;
    info.hidden = false;
    Array.prototype.forEach.call(svg.querySelectorAll('.mst.sel'), function (g) { g.classList.remove('sel'); });
    var g = svg.querySelector('.mst[data-c="' + code + '"]');
    if (g) g.classList.add('sel');
  }
  info.addEventListener('click', function (e) {
    if (e.target.closest('.mt-info-x')) info.hidden = true;
  });

  // 手勢：單指拖曳、兩指縮放、輕點選站
  var pts = {}, last = null, down = null;
  function list() { return Object.keys(pts).map(function (k) { return pts[k]; }); }
  function gesture() {
    var a = list();
    if (a.length >= 2) {
      var dx = a[0].x - a[1].x, dy = a[0].y - a[1].y;
      return { x: (a[0].x + a[1].x) / 2, y: (a[0].y + a[1].y) / 2, d: Math.hypot(dx, dy), n: 2 };
    }
    return a.length ? { x: a[0].x, y: a[0].y, d: 0, n: 1 } : null;
  }
  stage.addEventListener('pointerdown', function (e) {
    try { stage.setPointerCapture(e.pointerId); } catch (_) {}
    pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    last = gesture();
    if (last.n === 1) down = { x: e.clientX, y: e.clientY, t: Date.now() };
    else down = null;
  });
  stage.addEventListener('pointermove', function (e) {
    if (!pts[e.pointerId]) return;
    if (e.pointerType === 'mouse' && !e.buttons) { delete pts[e.pointerId]; last = gesture(); return; }
    pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    var g = gesture();
    if (!g || !last || g.n !== last.n) { last = g; return; }
    var p0 = toSvg(last.x, last.y), p1 = toSvg(g.x, g.y);
    vb[0] += p0.x - p1.x; vb[1] += p0.y - p1.y;
    apply();
    if (g.n === 2 && last.d > 0) zoomAt(g.x, g.y, g.d / last.d);
    last = g;
    e.preventDefault();
  });
  function up(e) {
    if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 8 && Date.now() - down.t < 600) {
      var el = document.elementFromPoint(e.clientX, e.clientY);
      var g = el && el.closest ? el.closest('[data-c]') : null;
      if (g) showInfo(g.getAttribute('data-c'));
    }
    delete pts[e.pointerId];
    last = gesture();
    down = null;
  }
  stage.addEventListener('pointerup', up);
  stage.addEventListener('pointercancel', function (e) { delete pts[e.pointerId]; last = gesture(); down = null; });
  stage.addEventListener('wheel', function (e) {
    e.preventDefault();
    zoomAt(e.clientX, e.clientY, e.deltaY < 0 ? 1.2 : 1 / 1.2);
  }, { passive: false });
  stage.addEventListener('dblclick', function (e) { zoomAt(e.clientX, e.clientY, 2); });

  ov.querySelector('.mt-bar').addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b) return;
    var act = b.getAttribute('data-act');
    if (act === 'fit') fit();
    else if (act === 'here') { focus(here[0]); showInfo(here[0]); }
    else if (act === 'in') zoomCenter(1.5);
    else if (act === 'out') zoomCenter(1 / 1.5);
    else if (act === 'close') close();
  });

  function show() {
    if (!ov.hidden) return;
    ov.hidden = false;
    document.documentElement.classList.add('mt-lock');
    fit();
  }
  function hide() {
    ov.hidden = true;
    info.hidden = true;
    document.documentElement.classList.remove('mt-lock');
  }
  function open() {
    if (location.hash !== '#metro') history.pushState({ metro: 1 }, '', '#metro');
    show();
  }
  function close() {
    if (history.state && history.state.metro) history.back();
    else {
      history.replaceState(null, '', location.pathname + location.search);
      hide();
    }
  }
  window.addEventListener('popstate', function () {
    if (location.hash === '#metro') show(); else hide();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !ov.hidden) close(); });
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-metro-open]');
    if (t) { e.preventDefault(); open(); }
  });

  // 頂部導航鍵捲出畫面後，右下角補一顆浮動鍵
  var top = document.querySelector('.mt-open');
  var fab = document.createElement('button');
  fab.type = 'button';
  fab.className = 'mt-fab';
  fab.setAttribute('data-metro-open', '');
  fab.innerHTML = '<span class="mt-ico" aria-hidden="true"><i></i><i></i><i></i></span>路線圖';
  document.body.appendChild(fab);
  if (top && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (es) {
      fab.classList.toggle('on', !es[0].isIntersecting);
    }).observe(top);
  } else {
    fab.classList.add('on');
  }

  if (location.hash === '#metro') show();
})();

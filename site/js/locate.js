/* 認識臺灣 — 首頁「我在哪裡」：定位跳鄉鎮頁＋縣市／鄉鎮選單（只在首頁掛載）
   定位：navigator.geolocation 取座標，在瀏覽器內用鄉鎮界線查表判斷落在哪個鄉鎮，
   座標不送出站外。有鄉鎮頁就跳鄉鎮頁，沒有就跳縣市頁。
   界線查表＝data/taiwan-towns-lookup.json（scripts/build_town_lookup.py 產出，
   約 560 KB），按下定位鈕才載入；解碼與判斷在 js/geo-core.js（要先載）。選單只列 pages-index.json 裡已上線的頁面。 */
(function () {
  'use strict';

  var COUNTIES = [
    '臺北市', '新北市', '基隆市', '桃園市', '新竹市', '新竹縣', '苗栗縣',
    '臺中市', '彰化縣', '南投縣', '雲林縣', '嘉義市', '嘉義縣', '臺南市',
    '高雄市', '屏東縣', '宜蘭縣', '花蓮縣', '臺東縣', '澎湖縣', '金門縣', '連江縣'
  ];
  // 定位精度差於此（公尺）就不自動跳頁，只把推測結果填進選單讓使用者確認
  //（桌機多半靠 IP／Wi-Fi 推位置，常差好幾公里）。
  var ACCURACY_LIMIT = 3000;

  var root = document.getElementById('geo-locate');
  if (!root || !window.GeoCore) return;
  var btn = document.getElementById('geo-locate-btn');
  var selCounty = document.getElementById('geo-pick-county');
  var selTown = document.getElementById('geo-pick-town');
  var goBtn = document.getElementById('geo-pick-go');
  var status = document.getElementById('geo-locate-status');

  var norm = function (s) { return String(s || '').replace(/台/g, '臺'); };
  var byCounty = {};   // 縣市 → { page: 縣市頁 id, towns: [{ id, name }] }
  var townPage = {};   // '縣市|鄉鎮' → 鄉鎮頁 id

  function say(msg, tone) {
    status.textContent = msg || '';
    status.className = 'geo-locate-status' + (tone ? ' is-' + tone : '');
  }
  function pageUrl(id) { return 'pages/' + id + '.html'; }

  // ---------- 選單 ----------
  var collator = window.Intl && Intl.Collator ? new Intl.Collator('zh-Hant-TW') : null;

  function fillTowns(county, pickId) {
    var info = byCounty[county];
    selTown.innerHTML = '';
    if (!info) {
      selTown.appendChild(new Option('選鄉鎮市區', ''));
      selTown.disabled = true;
      goBtn.disabled = true;
      return;
    }
    selTown.appendChild(new Option(county + '概論', info.page));
    info.towns.forEach(function (t) { selTown.appendChild(new Option(t.name, t.id)); });
    selTown.disabled = false;
    selTown.value = pickId || info.page;
    goBtn.disabled = false;
  }

  var ready = fetch('data/pages-index.json')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var pages = (data && data.pages) || [];
      pages.forEach(function (p) {
        var c = norm(p.county);
        if (COUNTIES.indexOf(c) < 0) return;
        var info = byCounty[c] = byCounty[c] || { page: null, towns: [] };
        if (norm(p.name) === c) info.page = p.id;
        else {
          info.towns.push({ id: p.id, name: p.name });
          townPage[c + '|' + norm(p.name)] = p.id;
        }
      });
      COUNTIES.forEach(function (c) {
        var info = byCounty[c];
        if (!info || !info.page) { delete byCounty[c]; return; }
        if (collator) info.towns.sort(function (a, b) { return collator.compare(a.name, b.name); });
        selCounty.appendChild(new Option(c, c));
      });
      selCounty.disabled = false;
    })
    .catch(function () { say('縣市清單載入失敗，請重新整理頁面。', 'warn'); });

  selCounty.addEventListener('change', function () {
    var info = byCounty[selCounty.value];
    fillTowns(selCounty.value);
    say(info && !info.towns.length ? '這個縣市的鄉鎮頁還在撰寫，先看縣市概論。' : '');
  });
  goBtn.addEventListener('click', function () {
    if (selTown.value) location.href = pageUrl(selTown.value);
  });

  // ---------- 鄉鎮界線查表（解碼與點在多邊形判斷在 js/geo-core.js，旅遊地圖共用） ----------
  function loadLookup() { return GeoCore.loadLookup('data/taiwan-towns-lookup.json'); }
  var findTown = GeoCore.findTown;

  // ---------- 定位 ----------
  function resetBtn() { btn.disabled = false; btn.classList.remove('is-busy'); }

  function onFix(pos) {
    var x = pos.coords.longitude, y = pos.coords.latitude, acc = pos.coords.accuracy || 0;
    Promise.all([loadLookup(), ready]).then(function (res) {
      resetBtn();
      var hit = findTown(res[0], x, y);
      if (!hit) {
        say('定位到的位置不在臺灣的鄉鎮範圍內，請改用選單挑一個地方。', 'warn');
        return;
      }
      var county = hit.c, town = hit.t;
      if (!byCounty[county]) {
        say('定位到' + county + town + '，但這個縣市的頁面還沒上線。', 'warn');
        return;
      }
      var id = townPage[county + '|' + town];
      selCounty.value = county;
      fillTowns(county, id);
      if (acc > ACCURACY_LIMIT) {
        say('定位精度只有約 ' + Math.round(acc / 1000) + ' 公里，推測你在' + county + town +
            '，已幫你選好，確認後按「前往」。', 'warn');
        return;
      }
      say(id ? '你在' + county + town + '，前往' + town + '⋯'
             : '你在' + county + town + '（鄉鎮頁還在撰寫），先前往' + county + '⋯', 'ok');
      setTimeout(function () { location.href = pageUrl(id || byCounty[county].page); }, 700);
    }).catch(function () {
      resetBtn();
      say('鄉鎮界線資料載入失敗，請檢查網路後再試一次。', 'warn');
    });
  }

  function onError(err) {
    resetBtn();
    var msg = {
      1: '沒有取得定位權限。可以在瀏覽器設定允許本站使用位置，或直接用選單挑地方。',
      2: '暫時抓不到位置訊號，請稍後再試，或用選單挑地方。',
      3: '定位逾時，請再試一次，或用選單挑地方。'
    }[err && err.code];
    say(msg || '定位失敗，請用選單挑地方。', 'warn');
  }

  btn.addEventListener('click', function () {
    if (!navigator.geolocation || window.isSecureContext === false) {
      say('這個瀏覽器不能定位，請用選單挑地方。', 'warn');
      return;
    }
    btn.disabled = true;
    btn.classList.add('is-busy');
    say('定位中⋯（第一次使用，瀏覽器會問你是否允許）');
    loadLookup();   // 與定位同時開抓界線資料
    navigator.geolocation.getCurrentPosition(onFix, onError,
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 });
  });

  // 從鄉鎮頁按「上一頁」回來時（bfcache 還原），把按鈕與提示復原。
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) { resetBtn(); say(''); }
  });
})();

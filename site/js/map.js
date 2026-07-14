/* 認識臺灣 — 首頁互動地圖
   臺灣 → 縣市 → 鄉鎮 的導航概念。離線自包含，不掛 raster 底圖。
   註：dkaoster/taiwan-atlas 的縣市名用「台」不用「臺」（如「台北市」）。 */

// 全 22 縣市已上線。縣市名須與 taiwan-counties.geojson 的 COUNTYNAME 完全一致。
const DRILL_COUNTIES = { '宜蘭縣': true };            // 點了 → 鑽進鄉鎮層
const COUNTY_PAGES = {                                 // 點了 → 直接進縣市內容頁
  '台北市': 'taipei',
  '新北市': 'new-taipei',
  '基隆市': 'keelung',
  '桃園市': 'taoyuan',
  '新竹市': 'hsinchu-city',
  '新竹縣': 'hsinchu-county',
  '苗栗縣': 'miaoli',
  '台中市': 'taichung',
  '彰化縣': 'changhua',
  '南投縣': 'nantou',
  '雲林縣': 'yunlin',
  '嘉義市': 'chiayi-city',
  '嘉義縣': 'chiayi-county',
  '台南市': 'tainan',
  '高雄市': 'kaohsiung',
  '屏東縣': 'pingtung',
  '台東縣': 'taitung',
  '花蓮縣': 'hualien',
  '澎湖縣': 'penghu',
  '金門縣': 'kinmen',
  '連江縣': 'lienchiang'
};
// 宜蘭 12 鄉鎮市 中文名 → 內容頁 id（須與母本 frontmatter 的 id 一致）
const TOWN_IDS = {
  '宜蘭市': 'yilan-yilan',   '頭城鎮': 'yilan-toucheng', '礁溪鄉': 'yilan-jiaoxi',
  '壯圍鄉': 'yilan-zhuangwei','員山鄉': 'yilan-yuanshan', '羅東鎮': 'yilan-luodong',
  '五結鄉': 'yilan-wujie',   '冬山鄉': 'yilan-dongshan', '蘇澳鎮': 'yilan-suao',
  '三星鄉': 'yilan-sanxing', '大同鄉': 'yilan-datong',   '南澳鄉': 'yilan-nanao'
};

// 22 縣市各自定色（圖資縣市名用「台」）。宜蘭/北北基沿用第一期原色，其餘 18 縣市新配色，
// 各自散開在色相環上避開既有 4 色，維持鄰近縣市可辨識。
const COUNTY_COLORS = {
  '宜蘭縣': '#4e8a4e',   // 綠（維持原色，鄉鎮下鑽）
  '台北市': '#c0504d',   // 磚紅（維持原色）
  '新北市': '#4472a8',   // 藍（維持原色）
  '基隆市': '#d09a3c',   // 琥珀（維持原色）
  '南投縣': '#ab5f3f',
  '台中市': '#aba73f',
  '台南市': '#95ab3f',
  '台東縣': '#7cab3f',
  '嘉義市': '#63ab3f',
  '嘉義縣': '#3fab6a',
  '屏東縣': '#3fab83',
  '彰化縣': '#3fab99',
  '新竹市': '#3fa4ab',
  '新竹縣': '#3f8aab',
  '桃園市': '#3f3fab',
  '澎湖縣': '#583fab',
  '花蓮縣': '#713fab',
  '苗栗縣': '#873fab',
  '連江縣': '#a03fab',
  '金門縣': '#ab3f9c',
  '雲林縣': '#ab3f83',
  '高雄市': '#ab3f6a'
};

const COLORS = {
  ready:    '#6d7a4f',   // 已有內容頁的鄉鎮（hover 用）
  building: '#d9c9a6',   // 內容建置中的鄉鎮
  inactive: '#ddd6c6',   // 灰化不可點（其餘縣市）
  line:     '#8f8266'
};

// 鄉鎮政區配色：每區一色（柔和大地調，鄰區可辨），已完成＝實色、建置中＝同色轉淡
const TOWN_COLORS = {
  '宜蘭市': '#c25b4e', '頭城鎮': '#4e7fa3', '礁溪鄉': '#c78f3d',
  '壯圍鄉': '#8a9a5b', '員山鄉': '#7b6aa8', '羅東鎮': '#b5566d',
  '五結鄉': '#4f9484', '冬山鄉': '#996a3d', '蘇澳鎮': '#5b7ab5',
  '三星鄉': '#6f9a4e', '大同鄉': '#a3703f', '南澳鄉': '#5e8a6e'
};

const PAGE = (id) => `pages/${id}.html`;

const map = L.map('map', {
  zoomControl: false,          // 定著地圖：拿掉縮放控制鈕
  dragging: false,             // 關拖曳平移
  touchZoom: false,            // 關 pinch 縮放
  doubleClickZoom: false,      // 關雙擊縮放
  scrollWheelZoom: false,      // 關滾輪縮放
  boxZoom: false,              // 關 shift+拖曳框選縮放
  keyboard: false,             // 關鍵盤方向鍵平移/縮放
  attributionControl: false,
  minZoom: 6,
  maxZoom: 12
});

// 臺灣本島取景框：只框本島（不含金門/馬祖/澎湖），讓本島置中放大。
// 若用 countyLayer.getBounds() 會把金門(lng≈118.15)、馬祖(lat≈26.38)全包進來，
// 導致本島被壓小又偏移（手機直式尤其明顯）。離島仍會被畫出、只是可能被裁掉部分。
const TAIWAN_MAIN_BOUNDS = L.latLngBounds([[21.8, 119.9], [25.4, 122.1]]);
function fitTaiwan() { map.fitBounds(TAIWAN_MAIN_BOUNDS, { padding: [8, 8] }); }

let availablePages = {};   // { id: true } 由 build.py 產生的 pages-index.json
let countyLayer, townLayer;
const crumbs = document.getElementById('crumbs');

function setCrumbs(html) { if (crumbs) crumbs.innerHTML = html; }

// ---- 縣市層 ----
// 縣市內容頁是否已 build 出來（避免點了 404）
const countyPageReady = (name) => COUNTY_PAGES[name] && availablePages[COUNTY_PAGES[name]];
const inScopeCounty = (name) => DRILL_COUNTIES[name] || COUNTY_PAGES[name];
const clickableCounty = (name) => DRILL_COUNTIES[name] || countyPageReady(name);

function countyStyle(feature) {
  const name = feature.properties.COUNTYNAME;
  const inScope = inScopeCounty(name);
  const clickable = clickableCounty(name);
  if (inScope) {
    return {
      color: '#fffdf6',          // active 縣市加粗白邊，提高可辨識（基隆市多邊形太小）
      weight: 2,
      fillColor: COUNTY_COLORS[name] || COLORS.building,
      fillOpacity: clickable ? 0.85 : 0.55,
      opacity: 1
    };
  }
  // 其餘縣市：灰米色、降低存在感
  return {
    color: COLORS.line,
    weight: 0.6,
    fillColor: COLORS.inactive,
    fillOpacity: 0.3,
    opacity: 0.5
  };
}

function onCountyFeature(feature, layer) {
  const name = feature.properties.COUNTYNAME;
  if (!inScopeCounty(name)) return;
  const clickable = clickableCounty(name);
  layer.bindTooltip(clickable ? name : `${name}（內容建置中）`, { className: 'geo-tip', sticky: true });
  if (!clickable) {
    layer.on('mouseover', (e) => e.target.setStyle({ fillOpacity: 0.75 }));
    layer.on('mouseout',  (e) => countyLayer.resetStyle(e.target));
    return;
  }
  layer.on({
    // hover：提高飽和/透明度、白邊再加粗
    mouseover: (e) => e.target.setStyle({ fillOpacity: 1, weight: 3 }),
    mouseout:  (e) => countyLayer.resetStyle(e.target),
    click: () => goToCounty(name)
  });
}

// 縣市進入行為（地圖多邊形點擊 與 快速導覽 chips 共用）
function goToCounty(name) {
  if (DRILL_COUNTIES[name]) { drillToTowns(name); return; }
  if (countyPageReady(name)) { window.location.href = PAGE(COUNTY_PAGES[name]); }
}

// ---- 鄉鎮層（宜蘭）----
function townStyle(feature) {
  const name = feature.properties.TOWNNAME;
  const id = TOWN_IDS[name];
  const ready = id && availablePages[id];
  return {
    color: '#fffdf6',
    weight: 1.4,
    fillColor: TOWN_COLORS[name] || COLORS.building,
    fillOpacity: ready ? 0.88 : 0.32,
    opacity: 1
  };
}

function onTownFeature(feature, layer) {
  const name = feature.properties.TOWNNAME;
  const id = TOWN_IDS[name];
  const ready = id && availablePages[id];
  const label = ready ? name : `${name}（內容建置中）`;
  layer.bindTooltip(label, {
    className: 'geo-tip', sticky: true,
    permanent: false
  });
  if (ready) {
    layer.on({
      mouseover: (e) => e.target.setStyle({ fillOpacity: 1, weight: 2 }),
      mouseout:  (e) => townLayer.resetStyle(e.target),
      click: () => { window.location.href = PAGE(id); }
    });
  } else {
    layer.on('mouseover', (e) => e.target.setStyle({ fillOpacity: 0.5 }));
    layer.on('mouseout',  (e) => townLayer.resetStyle(e.target));
  }
}

function drillToTowns(countyName) {
  if (countyLayer) map.removeLayer(countyLayer);
  fetch('data/yilan-towns.geojson')
    .then((r) => r.json())
    .then((geo) => {
      townLayer = L.geoJSON(geo, { style: townStyle, onEachFeature: onTownFeature }).addTo(map);
      map.fitBounds(townLayer.getBounds(), { padding: [20, 20] });
      setCrumbs(`<a id="back-tw">臺灣</a> &rsaquo; <strong>${countyName}</strong>`);
      const back = document.getElementById('back-tw');
      if (back) back.addEventListener('click', showTaiwan);
    });
}

function showTaiwan() {
  if (townLayer) { map.removeLayer(townLayer); townLayer = null; }
  if (countyLayer) countyLayer.addTo(map);
  fitTaiwan();
  setCrumbs('<strong>臺灣</strong>');
}

// 快速導覽 chips → 與點多邊形完全一致
function wireChips() {
  document.querySelectorAll('.nav-chip[data-county]').forEach((btn) => {
    btn.addEventListener('click', () => goToCounty(btn.getAttribute('data-county')));
  });
}

// ---- 初始化 ----
Promise.all([
  fetch('data/taiwan-counties.geojson').then((r) => r.json()),
  fetch('data/pages-index.json').then((r) => r.json()).catch(() => ({ pages: [] }))
]).then(([counties, index]) => {
  (index.pages || []).forEach((p) => { availablePages[p.id] = true; });
  countyLayer = L.geoJSON(counties, { style: countyStyle, onEachFeature: onCountyFeature }).addTo(map);
  fitTaiwan();
  setCrumbs('<strong>臺灣</strong>');
  wireChips();

  // ?county=宜蘭縣 → 載入後自動下鑽宜蘭（給內容頁「回到宜蘭縣」用）
  const wanted = new URLSearchParams(window.location.search).get('county');
  if (wanted && DRILL_COUNTIES[wanted]) { drillToTowns(wanted); }
  else if (wanted && COUNTY_PAGES[wanted] && countyPageReady(wanted)) {
    window.location.href = PAGE(COUNTY_PAGES[wanted]);
  }
});

// 視窗尺寸變動（旋轉螢幕、桌機縮放視窗）後重新取景，維持置中。
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    map.invalidateSize();
    if (townLayer && map.hasLayer(townLayer)) {
      map.fitBounds(townLayer.getBounds(), { padding: [20, 20] });
    } else {
      fitTaiwan();
    }
  }, 200);
});

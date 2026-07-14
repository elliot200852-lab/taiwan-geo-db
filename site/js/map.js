/* 認識臺灣 — 首頁互動地圖
   臺灣 → 縣市 → 鄉鎮 的導航概念。離線自包含，不掛 raster 底圖。
   註：dkaoster/taiwan-atlas 的縣市名用「台」不用「臺」（如「台北市」）。 */

// 第一期範圍。縣市名須與 taiwan-counties.geojson 的 COUNTYNAME 完全一致。
const DRILL_COUNTIES = { '宜蘭縣': true };            // 點了 → 鑽進鄉鎮層
const COUNTY_PAGES = {                                 // 點了 → 直接進縣市內容頁
  '台北市': 'taipei',
  '新北市': 'new-taipei',
  '基隆市': 'keelung'
};
// 宜蘭 12 鄉鎮市 中文名 → 內容頁 id（須與母本 frontmatter 的 id 一致）
const TOWN_IDS = {
  '宜蘭市': 'yilan-yilan',   '頭城鎮': 'yilan-toucheng', '礁溪鄉': 'yilan-jiaoxi',
  '壯圍鄉': 'yilan-zhuangwei','員山鄉': 'yilan-yuanshan', '羅東鎮': 'yilan-luodong',
  '五結鄉': 'yilan-wujie',   '冬山鄉': 'yilan-dongshan', '蘇澳鎮': 'yilan-suao',
  '三星鄉': 'yilan-sanxing', '大同鄉': 'yilan-datong',   '南澳鄉': 'yilan-nanao'
};

const COLORS = {
  active:   '#b56a3c',   // 可點縣市
  ready:    '#6d7a4f',   // 已有內容頁的鄉鎮（hover 用）
  building: '#d9c9a6',   // 內容建置中的鄉鎮
  inactive: '#ddd6c6',   // 灰化不可點
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
  zoomControl: true,
  attributionControl: false,
  minZoom: 6,
  maxZoom: 12,
  scrollWheelZoom: false
});

let availablePages = {};   // { id: true } 由 build.py 產生的 pages-index.json
let countyLayer, townLayer;
const crumbs = document.getElementById('crumbs');

function setCrumbs(html) { if (crumbs) crumbs.innerHTML = html; }

// ---- 縣市層 ----
// 縣市內容頁是否已 build 出來（避免點了 404）
const countyPageReady = (name) => COUNTY_PAGES[name] && availablePages[COUNTY_PAGES[name]];

function countyStyle(feature) {
  const name = feature.properties.COUNTYNAME;
  const inScope = DRILL_COUNTIES[name] || COUNTY_PAGES[name];
  const clickable = DRILL_COUNTIES[name] || countyPageReady(name);
  return {
    color: COLORS.line,
    weight: inScope ? 1.1 : 0.6,
    fillColor: clickable ? COLORS.active : (inScope ? COLORS.building : COLORS.inactive),
    fillOpacity: inScope ? 0.85 : 0.45,
    opacity: inScope ? 0.9 : 0.5
  };
}

function onCountyFeature(feature, layer) {
  const name = feature.properties.COUNTYNAME;
  if (!(DRILL_COUNTIES[name] || COUNTY_PAGES[name])) return;
  const clickable = DRILL_COUNTIES[name] || countyPageReady(name);
  layer.bindTooltip(clickable ? name : `${name}（內容建置中）`, { className: 'geo-tip', sticky: true });
  if (!clickable) {
    layer.on('mouseover', (e) => e.target.setStyle({ fillOpacity: 0.7 }));
    layer.on('mouseout',  (e) => countyLayer.resetStyle(e.target));
    return;
  }
  layer.on({
    mouseover: (e) => e.target.setStyle({ fillColor: COLORS.ready, fillOpacity: 0.95 }),
    mouseout:  (e) => countyLayer.resetStyle(e.target),
    click: () => {
      if (DRILL_COUNTIES[name]) drillToTowns(name);
      else window.location.href = PAGE(COUNTY_PAGES[name]);
    }
  });
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
  map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });
  setCrumbs('<strong>臺灣</strong>');
}

// ---- 初始化 ----
Promise.all([
  fetch('data/taiwan-counties.geojson').then((r) => r.json()),
  fetch('data/pages-index.json').then((r) => r.json()).catch(() => ({ pages: [] }))
]).then(([counties, index]) => {
  (index.pages || []).forEach((p) => { availablePages[p.id] = true; });
  countyLayer = L.geoJSON(counties, { style: countyStyle, onEachFeature: onCountyFeature }).addTo(map);
  map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });
  setCrumbs('<strong>臺灣</strong>');
});

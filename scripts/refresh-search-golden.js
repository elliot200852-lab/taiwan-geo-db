#!/usr/bin/env node
/**
 * 更新 scripts/search-golden.json —— 但先確認這次的差異真的只是「新內容進榜」。
 *
 * 為什麼不直接重產：golden test 的用途是擋**計分／排序邏輯**的回歸
 * （docs/DEPLOY.md「search-core 雙 repo 同步規則」）。新增頁面必然會改變 top-10，
 * 這時候如果直接把 golden 重產一份蓋上去，等於每次都把基準線對齊現況——
 * 真的排序 bug 混在裡面也會一起被「更新」掉，測試從此再也擋不住任何東西。
 *
 * 所以這支的順序是：先分類，再決定給不給更新。
 *   ① 把「這次新增的頁」從實得結果裡拿掉
 *   ② 比對剩下的既有頁順序與 golden 是否一致
 *   ③ 一致 → 純內容擴充，允許更新
 *      不一致 → 排序邏輯真的變了，**拒絕更新並非零離開**，回去查 search-core
 *
 * 用法（--new＝這一批「允許移動」的頁：新增的、或內容被改動過的）：
 *   node scripts/refresh-search-golden.js --new <id> [<id>...]      # 檢查，不寫入
 *   node scripts/refresh-search-golden.js --new <id> [...] --write  # 通過才寫入
 *
 * --new 要列出這一批新增的 page id。列不全會讓某些新頁被當成「既有頁」，
 * 於是看起來像排序改變 → 這支會擋下來要你查清楚，寧可誤擋不要放行。
 */
const path = require("path");
const fs = require("fs");

const REPO = path.join(__dirname, "..");
const { geoSearchMatch } = require(path.join(REPO, "site/js/search.js"));

const argv = process.argv.slice(2);
const write = argv.includes("--write");
const ni = argv.indexOf("--new");
if (ni < 0) {
  console.error("要用 --new 列出這一批新增的 page id，例如：\n" +
    "  node scripts/refresh-search-golden.js --new yilan new-taipei-tamsui");
  process.exit(2);
}
const NEW = new Set(argv.slice(ni + 1).filter((a) => !a.startsWith("--")));
if (!NEW.size) {
  console.error("--new 後面至少要接一個 page id。");
  process.exit(2);
}

const indexPath = path.join(REPO, "site/data/search-index.json");
const goldenPath = path.join(REPO, "scripts/search-golden.json");
const records = JSON.parse(fs.readFileSync(indexPath, "utf8")).records;
const golden = JSON.parse(fs.readFileSync(goldenPath, "utf8"));

const known = new Set(records.map((r) => r.id));
const bogus = [...NEW].filter((id) => !known.has(id));
if (bogus.length) {
  console.error(`--new 裡有不存在於 search-index 的 id：${bogus.join(", ")}（build 跑了嗎？）`);
  process.exit(2);
}

let same = 0, benign = 0;
const regressions = [];
const next = {};

for (const q of Object.keys(golden)) {
  const got = geoSearchMatch(q, records).slice(0, 10).map((r) => r.record.id);
  const want = golden[q];
  next[q] = got;
  if (JSON.stringify(got) === JSON.stringify(want)) { same++; continue; }

  // 「允許移動」的頁要從**兩邊**都剔除再比。
  // 第一版只從實得結果剔除，假設 golden 是「這批頁還不存在」的基準——
  // 但同一批內第二次 refresh 時 golden 裡早就有它們了，那個假設就破了，
  // 於是純粹改個錯字也會被誤判成排序回歸。剔除兩邊之後，這支比的
  // 一律是「我沒碰過的頁，彼此的相對順序有沒有變」，跟 refresh 過幾次無關。
  const gotOld = got.filter((id) => !NEW.has(id));
  const wantOld = want.filter((id) => !NEW.has(id));
  const inserted = got.filter((id) => NEW.has(id));
  // 移動的頁擠進擠出會改變 top-10 的尾巴，所以只比對兩邊都有的長度
  const n = Math.min(gotOld.length, wantOld.length);
  if (JSON.stringify(gotOld.slice(0, n)) === JSON.stringify(wantOld.slice(0, n))) {
    benign++;
    console.log(`  ○ 「${q}」既有頁順序不變，新頁進榜：${inserted.join("、")}`);
  } else {
    regressions.push({ q, gotOld, wantOld });
    console.log(`  ✗ 「${q}」既有頁順序改變`);
    console.log(`      實得(去掉可移動頁) ${JSON.stringify(gotOld.slice(0, n))}`);
    console.log(`      golden           ${JSON.stringify(wantOld.slice(0, n))}`);
  }
}

console.log(`\n完全相同 ${same}｜只是新頁進榜 ${benign}｜既有頁排序改變 ${regressions.length}`);

if (regressions.length) {
  console.error("\n拒絕更新 golden：既有頁的相對順序變了，這是排序邏輯的回歸，不是內容擴充。");
  console.error("回去查 site/js/search-core.js 與 site/js/search.js 的 GEO_CONFIG；");
  console.error("確定是刻意改動再手動處理 golden，不要用這支繞過。");
  process.exit(1);
}

if (!write) {
  console.log("\n檢查通過（純內容擴充）。要真的寫入請加 --write。");
  process.exit(0);
}

fs.writeFileSync(goldenPath, JSON.stringify(next, null, 2) + "\n", "utf8");
console.log(`\n已更新 ${path.relative(REPO, goldenPath)}（${Object.keys(next).length} 組）。`);
console.log("接著跑 node scripts/test-search.js 應該全綠。");

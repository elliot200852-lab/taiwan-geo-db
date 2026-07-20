#!/usr/bin/env node
// 站內檢索純函式斷言測試（A-list #1：tie-break 排序修復；2026-07-20：
// search-core.js 雙 repo 收斂案，加 golden test）。
// 用法：node scripts/test-search.js
//
// site/js/search.js（geo-db adapter，計分核心已抽到 site/js/search-core.js，
// 兩 repo 同步檔）的 geoSearchMatch(query, records) 是可 require 的純函式，
// 這支跑三類斷言：
//   0. search-core.js 雙 repo 同步檢查（呼叫 check-search-core-sync.sh）。
//   1. 合成資料單元測試——直接驗證 tie-break 邏輯本身（不依賴真實內容，日後內容改版不會誤報）。
//   2. golden test（scripts/search-golden.json）——2026-07-20 收斂重構前，用舊實作對
//      20 組查詢記錄的 top-10 結果清單；重構後逐組比對完全一致，證明「geo 行為零變化」。
"use strict";

const assert = require("assert");
const path = require("path");
const fs = require("fs");
const { spawnSync } = require("child_process");

const { geoSearchMatch } = require(path.join(__dirname, "..", "site", "js", "search.js"));

let passed = 0;
function check(name, fn) {
  fn();
  passed += 1;
  console.log(`  ok - ${name}`);
}

console.log("== 0. search-core.js 雙 repo 同步檢查 ==");
const syncCheck = spawnSync(
  "bash",
  [path.join(__dirname, "check-search-core-sync.sh")],
  { encoding: "utf-8" }
);
if (syncCheck.stdout) process.stdout.write(syncCheck.stdout.replace(/^/gm, "  "));
if (syncCheck.stderr) process.stderr.write(syncCheck.stderr);
assert.strictEqual(syncCheck.status, 0, "search-core.js 雙 repo 同步檢查失敗，中止測試");
passed += 1;

console.log("== 1. 合成資料單元測試（tie-break 邏輯本身）==");

// 兩筆同分（都只靠 body 命中且都頂到 +5 分上限），但原始命中次數不同：
// rec-low 命中 5 次（未封頂前也是 5），rec-high 命中 30 次（封頂後一樣是 +5）。
// 修復前：兩者同分 5，維持原陣列序（rec-low 在前）；修復後：rec-high（命中次數多）應排前。
const synth = [
  { id: "rec-low", url: "pages/rec-low.html", title: "無關標題A", sub: "", kw: [], body: "關鍵字 ".repeat(5) },
  { id: "rec-high", url: "pages/rec-high.html", title: "無關標題B", sub: "", kw: [], body: "關鍵字 ".repeat(30) },
];
check("同分時 body 命中次數多者排前（tie-break 生效）", () => {
  const results = geoSearchMatch("關鍵字", synth);
  assert.strictEqual(results.length, 2, "應回傳兩筆合成結果");
  assert.strictEqual(results[0].score, results[1].score, "兩筆合成資料分數應相同（都頂到上限）");
  assert.strictEqual(results[0].record.id, "rec-high", "命中次數較多的 rec-high 應排第一");
  assert.strictEqual(results[1].record.id, "rec-low");
});

check("title 命中分數仍高於 body tie-break（既有排序邏輯不變）", () => {
  const withTitle = [
    { id: "rec-title", url: "pages/rec-title.html", title: "關鍵字專頁", sub: "", kw: [], body: "" },
    { id: "rec-high", url: "pages/rec-high.html", title: "無關標題", sub: "", kw: [], body: "關鍵字 ".repeat(30) },
  ];
  const results = geoSearchMatch("關鍵字", withTitle);
  assert.strictEqual(results[0].record.id, "rec-title", "title 命中（+100）應仍排在純 body 命中之前");
});

console.log("== 2. golden test（重構前 20 組查詢 top-10，比對零回歸）==");

const indexPath = path.join(__dirname, "..", "site", "data", "search-index.json");
const indexData = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
const records = indexData.records;
assert.ok(Array.isArray(records) && records.length > 0, "search-index.json 應含非空 records 陣列");

const goldenPath = path.join(__dirname, "search-golden.json");
const golden = JSON.parse(fs.readFileSync(goldenPath, "utf-8"));
const goldenQueries = Object.keys(golden);
assert.ok(goldenQueries.length >= 15, `golden 查詢組應至少 15 組，實得 ${goldenQueries.length}`);

for (const q of goldenQueries) {
  check(`golden：「${q}」top-10 與收斂重構前完全一致`, () => {
    const got = geoSearchMatch(q, records).slice(0, 10).map((r) => r.record.id);
    const want = golden[q];
    assert.deepStrictEqual(
      got,
      want,
      `「${q}」top-10 不符：\n  實得 ${JSON.stringify(got)}\n  應為 ${JSON.stringify(want)}`
    );
  });
}

console.log(`\n全部通過（${passed} 項斷言區塊，含 golden ${goldenQueries.length} 組）。`);

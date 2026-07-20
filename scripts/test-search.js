#!/usr/bin/env node
// 站內檢索純函式斷言測試（A-list #1：tie-break 排序修復）。
// 用法：node scripts/test-search.js
//
// site/js/search.js 的核心比對邏輯 geoSearchMatch(query, records) 是可 require 的純函式，
// 這支跑兩類斷言：
//   1. 合成資料單元測試——直接驗證 tie-break 邏輯本身（不依賴真實內容，日後內容改版不會誤報）。
//   2. 真實資料回歸測試——對 site/data/search-index.json 跑實際查詢，驗證已知錯排修好、
//      且既有查詢（龜山島→頭城鎮）沒有回歸。
"use strict";

const assert = require("assert");
const path = require("path");
const fs = require("fs");

const { geoSearchMatch } = require(path.join(__dirname, "..", "site", "js", "search.js"));

let passed = 0;
function check(name, fn) {
  fn();
  passed += 1;
  console.log(`  ok - ${name}`);
}

console.log("== 合成資料單元測試（tie-break 邏輯本身）==");

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

console.log("== 真實資料回歸測試（site/data/search-index.json）==");

const indexPath = path.join(__dirname, "..", "site", "data", "search-index.json");
const indexData = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
const records = indexData.records;
assert.ok(Array.isArray(records) && records.length > 0, "search-index.json 應含非空 records 陣列");

check("搜尋「媽祖」：theme-temples 主題頁排第一（已證實的錯排修復）", () => {
  const results = geoSearchMatch("媽祖", records);
  assert.ok(results.length > 0, "「媽祖」應有搜尋結果");
  assert.strictEqual(
    results[0].record.id,
    "theme-temples",
    `第一名應為 theme-temples，實得 ${results[0].record.id}`
  );
});

check("搜尋「龜山島」：頭城鎮排第一（既有查詢組不回歸）", () => {
  const results = geoSearchMatch("龜山島", records);
  assert.ok(results.length > 0, "「龜山島」應有搜尋結果");
  assert.strictEqual(
    results[0].record.id,
    "yilan-toucheng",
    `第一名應為 yilan-toucheng（頭城鎮），實得 ${results[0].record.id}`
  );
});

console.log(`\n全部通過（${passed} 項斷言區塊）。`);

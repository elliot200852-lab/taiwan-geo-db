/* 認識臺灣 — 首頁站內檢索（client-side 全文檢索，只在首頁掛載）
   計分／排序核心已抽到 search-core.js（taiwan-geo-db／taiwan-arts-db 雙 repo
   同步檔，2026-07-20 收斂案；規則見該檔檔頭）。本檔是 geo-db 專屬 adapter：
   只處理「kw 是陣列」這個資料形狀差異（join 成字串再交給 core，理由見
   geoSearchMatch 內註解），UI 行為（lazy-load 索引、輸入、結果面板、鍵盤、
   IME）維持原樣不動。
   Node 環境可直接 require('./search.js') 取得 { geoSearchMatch, normalize, splitQuery } 驗收，
   不會因為沒有 document/window 而噴錯（UI 掛載段落遇非瀏覽器環境會提前 return）。
   瀏覽器需先載入 js/search-core.js（見 site/index.html 的 <script> 順序，
   search-core.js 排在 search.js 之前，兩者皆 defer，執行序不受影響）。
   索引來源：data/search-index.json（scripts/build.py 產生，53 筆 { id, url, title, sub, kw, body }）。 */
(function (root) {
  'use strict';

  // ---------------------------------------------------------------------
  // geo-db adapter：呼叫共用核心 + 處理 kw 陣列形狀
  // ---------------------------------------------------------------------

  var SearchCore = (typeof module === 'object' && module.exports)
    ? require('./search-core.js')
    : root.SearchCore;

  var normalize = SearchCore.normalize;
  var splitQuery = SearchCore.splitQuery;
  var findAllIndexes = SearchCore.findAllIndexes;

  // geo-db 計分權重與收斂前完全一致（title+100/前綴+50、kw+40、sub+20、
  // body 每現+1 上限+5），不啟用 typeBoosts（該欄位只有 arts-db 用）。
  var GEO_CONFIG = {
    weights: { title: 100, titlePrefix: 50, kw: 40, sub: 20, bodyHit: 1, bodyCap: 5 }
  };

  // 單一 query 對 records 做比對計分，回傳前 20 名（依分數高到低）。
  // 每個 result：{ record, score, snippetPos, rawBodyHits }。snippetPos = body 內最早命中位置（無則 -1）。
  // 計分／多詞 AND／排序（含 tie-break：同分比未封頂 body 命中總數）規則全部在
  // search-core.js，此處不重覆説明。本函式只做一件事：geo 的 kw 是陣列
  // （例：["媽祖","廟會"]），core 期待的是單一字串——join(' ') 後再呼叫
  // rankRecords。用空白分隔可安全 join：查詢詞（splitQuery 產物）本身絕不含
  // 空白，故 join 造成的邊界不會被單一詞跨陣列元素誤匹配到，join 前後的
  // 「任一 kw 元素含 term」語意完全等價。回傳的 record 是保留原欄位
  // （id/url/title/sub/body）的淺拷貝物件，只有 kw 從陣列換成字串，UI 端
  // 存取的欄位不受影響。
  function geoSearchMatch(query, records) {
    if (!records || !records.length) return [];
    var canon = new Array(records.length);
    for (var i = 0; i < records.length; i++) {
      var rec = records[i];
      canon[i] = {
        id: rec.id,
        url: rec.url,
        title: rec.title,
        sub: rec.sub,
        body: rec.body,
        kw: (rec.kw || []).join(' ')
      };
    }
    return SearchCore.rankRecords(canon, query, GEO_CONFIG, 20);
  }

  // Node（require）與瀏覽器（<script>）皆可用；純函式段落到此為止。
  if (typeof module === 'object' && module.exports) {
    module.exports = { geoSearchMatch: geoSearchMatch, normalize: normalize, splitQuery: splitQuery };
  }
  if (root) {
    root.geoSearchMatch = geoSearchMatch;
  }

  // 非瀏覽器環境（Node 直跑/require）到此結束，不掛載下面的 DOM 行為。
  if (typeof document === 'undefined') return;

  // ---------------------------------------------------------------------
  // 前端行為（僅首頁）：lazy-load 索引、輸入、結果面板、鍵盤、IME
  // ---------------------------------------------------------------------

  var input = document.getElementById('geo-search-input');
  var hint = document.getElementById('geo-search-hint');
  var resultsEl = document.getElementById('geo-search-results');
  if (!input || !resultsEl) return;   // 子頁沒有這些節點，安靜跳過

  var INDEX_URL = 'data/search-index.json';
  var records = null;      // null = 尚未載入；載入後為陣列（可能為空陣列）
  var loading = false;
  var composing = false;   // 中文組字（IME）中：compositionstart~compositionend 之間不觸發比對
  var debounceTimer = null;
  var activeIndex = -1;

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      switch (c) {
        case '&': return '&amp;';
        case '<': return '&lt;';
        case '>': return '&gt;';
        case '"': return '&quot;';
        default: return '&#39;';
      }
    });
  }

  function setHint(text) {
    if (hint) hint.textContent = text || '';
  }

  // 在原字串（未正規化，用於畫面顯示）上標出 terms 命中的區段。
  // 命中位置以「正規化後字串」計算——本站語料以中文為主，NFKC＋小寫幾乎不改變長度，
  // 位置可直接套回原字串；若未來混入大量全形／合字內容需重新檢視此假設（見收工回報取捨）。
  function highlightTerms(original, terms) {
    var text = original == null ? '' : String(original);
    if (!terms || !terms.length || !text) return escapeHtml(text);
    var norm = normalize(text);
    var ranges = [];
    for (var i = 0; i < terms.length; i++) {
      var term = terms[i];
      if (!term) continue;
      var idxs = findAllIndexes(norm, term);
      for (var j = 0; j < idxs.length; j++) ranges.push([idxs[j], idxs[j] + term.length]);
    }
    if (!ranges.length) return escapeHtml(text);
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    for (var r = 0; r < ranges.length; r++) {
      var cur = ranges[r];
      var last = merged[merged.length - 1];
      if (last && cur[0] <= last[1]) {
        if (cur[1] > last[1]) last[1] = cur[1];
      } else {
        merged.push([cur[0], cur[1]]);
      }
    }
    var out = '';
    var pos = 0;
    for (var m = 0; m < merged.length; m++) {
      var s = Math.max(merged[m][0], pos);
      var e = Math.max(merged[m][1], s);
      if (s >= text.length) break;
      var eClamped = Math.min(e, text.length);
      out += escapeHtml(text.slice(pos, s));
      out += '<mark>' + escapeHtml(text.slice(s, eClamped)) + '</mark>';
      pos = eClamped;
    }
    out += escapeHtml(text.slice(pos));
    return out;
  }

  // body 命中處前後約 30 字的 snippet；查無 body 命中（只靠 title/kw/sub 命中）就取開頭。
  function buildSnippet(body, terms, hitPos) {
    var text = body == null ? '' : String(body);
    if (!text) return '';
    var radius = 30;
    if (hitPos == null || hitPos < 0) {
      var lead = text.slice(0, 60);
      return highlightTerms(lead, terms) + (text.length > 60 ? '…' : '');
    }
    var start = Math.max(0, hitPos - radius);
    var end = Math.min(text.length, hitPos + radius + 10);
    var prefix = start > 0 ? '…' : '';
    var suffix = end < text.length ? '…' : '';
    return prefix + highlightTerms(text.slice(start, end), terms) + suffix;
  }

  function loadIndexIfNeeded(cb) {
    if (records !== null || loading) { if (cb) cb(); return; }
    loading = true;
    setHint('索引載入中…');
    fetch(INDEX_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        records = (data && data.records) || [];
        loading = false;
        setHint('');
        if (cb) cb();
      })
      .catch(function () {
        loading = false;
        records = [];
        setHint('檢索索引載入失敗，請稍後再試');
        if (cb) cb();
      });
  }

  function clearResults() {
    resultsEl.innerHTML = '';
    resultsEl.hidden = true;
    activeIndex = -1;
  }

  function renderResults(query) {
    var terms = splitQuery(query);
    var matches = geoSearchMatch(query, records || []);
    activeIndex = -1;

    if (!matches.length) {
      resultsEl.innerHTML = '<p class="geo-search-empty">找不到符合的頁面</p>';
      resultsEl.hidden = false;
      setHint('找不到符合的頁面');
      return;
    }

    var html = '';
    for (var i = 0; i < matches.length; i++) {
      var rec = matches[i].record;
      var titleHtml = highlightTerms(rec.title, terms);
      var subHtml = rec.sub ? '<span class="gsi-sub">' + escapeHtml(rec.sub) + '</span>' : '';
      var snippetHtml = buildSnippet(rec.body, terms, matches[i].snippetPos);
      html += '<a class="geo-search-item" href="' + escapeHtml(rec.url) + '" role="option" data-idx="' + i + '">' +
        '<span class="gsi-title">' + titleHtml + '</span>' +
        subHtml +
        (snippetHtml ? '<span class="gsi-snippet">' + snippetHtml + '</span>' : '') +
        '</a>';
    }
    resultsEl.innerHTML = html;
    resultsEl.hidden = false;
    setHint(matches.length + ' 筆結果');
  }

  function runSearch() {
    var q = input.value;
    if (!q || !q.trim()) { clearResults(); setHint(''); return; }
    loadIndexIfNeeded(function () {
      if (!input.value.trim()) { clearResults(); return; }
      renderResults(input.value);
    });
  }

  function debouncedSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      if (!composing) runSearch();
    }, 120);
  }

  input.addEventListener('focus', function () { loadIndexIfNeeded(function () {}); });

  input.addEventListener('compositionstart', function () { composing = true; });
  input.addEventListener('compositionend', function () {
    composing = false;
    debouncedSearch();
  });

  input.addEventListener('input', function () {
    if (composing) return;   // 組字中不觸發比對，等 compositionend
    debouncedSearch();
  });

  function setActive(idx) {
    var items = resultsEl.querySelectorAll('.geo-search-item');
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle('active', i === idx);
    }
    activeIndex = idx;
    if (items[idx] && items[idx].scrollIntoView) items[idx].scrollIntoView({ block: 'nearest' });
  }

  input.addEventListener('keydown', function (e) {
    if (composing) return;
    var items = resultsEl.querySelectorAll('.geo-search-item');
    if (e.key === 'ArrowDown') {
      if (!items.length) return;
      e.preventDefault();
      setActive(activeIndex < items.length - 1 ? activeIndex + 1 : 0);
    } else if (e.key === 'ArrowUp') {
      if (!items.length) return;
      e.preventDefault();
      setActive(activeIndex > 0 ? activeIndex - 1 : items.length - 1);
    } else if (e.key === 'Enter') {
      var target = items[activeIndex >= 0 ? activeIndex : 0];
      if (target) {
        e.preventDefault();
        window.location.href = target.getAttribute('href');
      }
    } else if (e.key === 'Escape') {
      input.value = '';
      clearResults();
      setHint('');
      input.blur();
    }
  });
})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));

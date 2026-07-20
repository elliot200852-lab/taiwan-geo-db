/* 認識臺灣 — 首頁站內檢索（client-side 全文檢索，只在首頁掛載）
   核心比對邏輯 geoSearchMatch(query, records) 是純函式，掛在本模組頂層；
   Node 環境可直接 require('./search.js') 取得 { geoSearchMatch, normalize, splitQuery } 驗收，
   不會因為沒有 document/window 而噴錯（UI 掛載段落遇非瀏覽器環境會提前 return）。
   索引來源：data/search-index.json（scripts/build.py 產生，53 筆 { id, url, title, sub, kw, body }）。 */
(function (root) {
  'use strict';

  // ---------------------------------------------------------------------
  // 核心比對邏輯（純函式段落）
  // ---------------------------------------------------------------------

  // NFKC 正規化 + 小寫 + 空白正規化。中文不分詞，之後一律做子字串比對。
  function normalize(s) {
    if (s === null || s === undefined) return '';
    var t = String(s);
    if (typeof t.normalize === 'function') t = t.normalize('NFKC');
    t = t.toLowerCase();
    t = t.replace(/\s+/g, ' ').trim();
    return t;
  }

  // 查詢字串以空白切成多詞（正規化後切），空字串過濾掉。
  function splitQuery(query) {
    var n = normalize(query);
    if (!n) return [];
    var parts = n.split(' ');
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      if (parts[i]) out.push(parts[i]);
    }
    return out;
  }

  // haystack 中 needle 的所有出現起始位置（子字串，不重疊往前找）。
  function findAllIndexes(haystack, needle) {
    var idxs = [];
    if (!needle) return idxs;
    var start = 0;
    while (true) {
      var i = haystack.indexOf(needle, start);
      if (i === -1) break;
      idxs.push(i);
      start = i + needle.length;
    }
    return idxs;
  }

  // 單一 query 對 records 做比對計分，回傳前 20 名（依分數高到低）。
  // 每個 result：{ record, score, snippetPos }。snippetPos = body 內最早命中位置（無則 -1）。
  // 計分：title 命中 +100（前綴再 +50）、kw +40、sub +20、body 每次出現 +1（每詞上限 +5，計分不變）；
  // 多詞取 AND——任一詞在 title/kw/sub/body 都沒命中就整筆排除；命中詞分數加總。
  // 排序：主鍵＝score（不變）。次鍵（tie-break，2026-07-20 加）＝body 未封頂的原始命中總數，
  // 高者排前——解決「同分（都只靠 body 命中且都頂到 +5 上限）時，命中次數其實差很多的兩頁
  // 排序卻看不出差別」的錯排（例：搜「媽祖」時縣市頁排到真正的媽祖主題頁 theme-temples 前面）。
  // 兩鍵都相同才維持現行穩定序（Array#sort 為 stable sort，原陣列序＝records 傳入序）。
  function geoSearchMatch(query, records) {
    var terms = splitQuery(query);
    if (!terms.length || !records || !records.length) return [];

    var results = [];
    for (var ri = 0; ri < records.length; ri++) {
      var rec = records[ri];
      var titleN = normalize(rec.title);
      var subN = normalize(rec.sub);
      var kwList = rec.kw || [];
      var kwN = [];
      for (var ki = 0; ki < kwList.length; ki++) kwN.push(normalize(kwList[ki]));
      var bodyN = normalize(rec.body);

      var totalScore = 0;
      var matchedAll = true;
      var bodyFirstPositions = [];
      var rawBodyHits = 0;   // tie-break 用：body 命中次數加總，不封頂、不計分

      for (var ti = 0; ti < terms.length; ti++) {
        var term = terms[ti];
        var termScore = 0;
        var termHit = false;

        var titleIdx = titleN.indexOf(term);
        if (titleIdx !== -1) {
          termScore += 100;
          if (titleIdx === 0) termScore += 50;
          termHit = true;
        }

        var kwHit = false;
        for (var kj = 0; kj < kwN.length; kj++) {
          if (kwN[kj].indexOf(term) !== -1) { kwHit = true; break; }
        }
        if (kwHit) { termScore += 40; termHit = true; }

        if (subN.indexOf(term) !== -1) { termScore += 20; termHit = true; }

        var bodyIdxs = findAllIndexes(bodyN, term);
        if (bodyIdxs.length) {
          termScore += Math.min(bodyIdxs.length, 5);
          termHit = true;
          bodyFirstPositions.push(bodyIdxs[0]);
          rawBodyHits += bodyIdxs.length;
        }

        if (!termHit) { matchedAll = false; break; }
        totalScore += termScore;
      }

      if (!matchedAll) continue;

      var snippetPos = -1;
      if (bodyFirstPositions.length) {
        snippetPos = bodyFirstPositions[0];
        for (var pi = 1; pi < bodyFirstPositions.length; pi++) {
          if (bodyFirstPositions[pi] < snippetPos) snippetPos = bodyFirstPositions[pi];
        }
      }

      results.push({ record: rec, score: totalScore, snippetPos: snippetPos, rawBodyHits: rawBodyHits });
    }

    results.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return b.rawBodyHits - a.rawBodyHits;
    });
    return results.slice(0, 20);
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

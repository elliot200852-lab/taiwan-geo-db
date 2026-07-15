/* 認識臺灣 — 浮動導覽小浮標行為（所有頁面共用）
   收合／展開、分享網址（navigator.share 或複製 fallback）、回上一頁。
   回首頁／上一層是純連結，無需 JS。
   markup 由 build.py（子頁）與 index.html（首頁）注入；本檔只管行為。 */
(function () {
  var fab = document.getElementById('geo-fab');
  var toast = document.getElementById('copy-toast');

  function showToast(msg) {
    if (!toast) return;
    if (msg) toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { toast.classList.remove('show'); }, 1600);
  }

  function fallbackCopy(text) {
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showToast('網址已複製');
    } catch (e) {
      showToast('複製失敗，請手動複製');
    }
  }

  function copyUrl() {
    var url = window.location.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        showToast('網址已複製');
      }).catch(function () { fallbackCopy(url); });
    } else {
      fallbackCopy(url);
    }
  }

  if (!fab) return;

  var toggle = fab.querySelector('.geo-fab-toggle');
  function setOpen(open) {
    fab.classList.toggle('open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  if (toggle) {
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      setOpen(!fab.classList.contains('open'));
    });
  }

  fab.addEventListener('click', function (e) {
    var b = e.target.closest('[data-fab]');
    if (!b) return;
    var act = b.getAttribute('data-fab');
    if (act === 'back') {
      history.back();
    } else if (act === 'share') {
      // navigator.share 可用 → 開系統分享面板；否則複製網址 + toast。
      var url = window.location.href;
      if (navigator.share) {
        navigator.share({ title: document.title, url: url }).catch(function () {});
      } else {
        copyUrl();
      }
    }
  });

  // 點浮標以外 / 按 Esc → 收起
  document.addEventListener('click', function (e) {
    if (fab.classList.contains('open') && !fab.contains(e.target)) setOpen(false);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setOpen(false);
  });
})();

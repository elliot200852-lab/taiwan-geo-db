#!/usr/bin/env bash
# scripts/check-duplicate-titles.sh — 五年級即用小標逐字重複檢查。
#
# 背景：2026-09-01 砍掉 collision_check.py（356 行 n-gram 相似度撞題器）。紅隊拿
# 高雄 39 頁真實語料實跑證明它數學上是逐字匹配器——五年級小標中位長度只有 10 字，
# 短句要湊出「像」的分數，實質等於一字不差；換一個字（「臺灣的信史起點」→「臺灣
# 信史的起點」）就放行。它的抽取器本身在同一批語料上還有 9%（449 條中 40 條）被
# 抽成「埤」「拆」「汕」這種 1–5 字碎片，而且是靜默碎掉。改走誠實的一步：只抓
# 「一字不差」的重複——這是機器該做、也做得準的事；說法相近但不同字的撞題，
# 交給人眼看 `dispatch_slices.py --titles` 印出來的整句清單去判斷，不假裝有一支
# 腳本能幫你判斷語意相似度。
#
# ⚠ 2026-09-01 實測校準：預設 shell locale（zh_TW.UTF-8）下 sort/uniq 走 locale
# collation 比對，會把標點位置不同的兩條「不同」字串判成重複——親測案例：
# 「用臺北盆地講『盆地』地形」與「用臺北盆地講『盆地地形』」（分屬 taipei.md／
# new-taipei.md，內容並不相同）在 zh_TW.UTF-8 下被 `uniq -d` 誤判為同一條，換
# LC_ALL=C 逐位元組比對就消失。本腳本全程鎖 LC_ALL=C，不能拿掉，否則會生出假警報。
#
# 只查「五年級即用」的粗體小標（**...**）。探究題整句較長，逐字重複機率低，
# 而且探究題撞題的重點本來就是「換句話問同一件事」這種近似撞題，逐字比對抓不到，
# 也不該假裝抓得到。
set -euo pipefail
export LC_ALL=C

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SELF_DIR"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

grep -h '【五年級' content/*/*.md \
  | sed 's/.*\*\*\(.*\)\*\*.*/\1/' \
  | sort > "$TMP"

# 歷史豁免：docs/title-dup-baseline.txt（格式「<容許次數> <小標>」，只准縮不准長）。
# 用「次數」而不是「名單」豁免：新頁再撞同一條會讓全站次數超過容許值，照樣被抓。
BASE="docs/title-dup-baseline.txt"
DUPES="$(uniq -c "$TMP" | awk -v base="$BASE" '
  BEGIN { while ((getline line < base) > 0) { if (line ~ /^#/ || line == "") continue; n = index(line, " "); allow[substr(line, n+1)] = substr(line, 1, n-1) + 0 } }
  { cnt = $1; $1 = ""; sub(/^ /, ""); lbl = $0; if (cnt > 1 && cnt > allow[lbl] + 0) print lbl }')"

if [[ -z "$DUPES" ]]; then
  echo "✓ 五年級即用小標無逐字重複。"
  exit 0
fi

echo "✗ 發現逐字重複的五年級小標：" >&2
while IFS= read -r label; do
  [[ -z "$label" ]] && continue
  echo "  ▪ ${label}" >&2
  grep -rFn -- "$label" content/*/*.md | sed 's/^/      /' >&2
done <<< "$DUPES"
exit 1

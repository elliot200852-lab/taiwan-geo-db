#!/usr/bin/env python3
"""
taiwan-geo-db 視覺改版 v1 — 54 張情境 hero 圖批次生成腳本（gpt-image-2）

規格 SSOT：../docs/DESIGN-SPEC.md 第 6 節。
API 呼叫方式與 OPENAI_API_KEY 讀取順序抄自全域技能 ~/.claude/skills/draw/draw.py
（cwd .env → ~/.openai.env → shell 環境變數）。

用法：
  python3 gen_hero_images.py                                  # 全部 54 張（已存在的 webp 自動跳過）
  python3 gen_hero_images.py --only site-hero,hualien,theme-mountains
  python3 gen_hero_images.py --force                          # 已存在也重生
  python3 gen_hero_images.py --quality medium --concurrency 2

流程（單張）：
  1. 讀 hero-prompts.yaml 取得該 page-id 的主體描述
  2. 風格前綴（DESIGN-SPEC §6）＋ 主體描述 → gpt-image-2、1536x1024、output_format=jpeg
  3. jpg 中繼檔存 scratchpad/geo-hero-jpg/{page-id}.jpg
  4. cwebp 轉最長邊 1200 的 webp → site/img/hero/{page-id}.webp（該路徑在 .gitignore 內）

並發 2；撞 429/限流退避 35 秒重試（最多 5 次）；單張失敗不中斷整批，
最後統一列出失敗清單並以非零 exit code 結束。
"""

import argparse
import base64
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

MODEL = "gpt-image-2"
SIZE = "1536x1024"
DEFAULT_QUALITY = "low"  # 沿用 draw skill 預設判級：99% 情境用 low，不自作主張升級
MAX_RETRIES = 5
BACKOFF_SECONDS = 35
DEFAULT_CONCURRENCY = 2
WEBP_MAX_EDGE = 1200

# DESIGN-SPEC.md §6「prompt 風格前綴（批次腳本統一使用）」原文，逐字照抄，不得在
# hero-prompts.yaml 各條目裡重複這些風格詞。
STYLE_PREFIX = (
    "Traditional pen-and-wash illustration (鋼筆淡彩), fine ink linework with light "
    "watercolor washes, muted earthy palette of terracotta, moss green, slate blue and "
    "cream map-paper tones, wide panoramic landscape composition, aged paper texture, "
    "no text, no lettering, no recognizable human faces (distant silhouettes only), "
    "style of vintage geographic field sketches"
)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PROMPTS_PATH = SCRIPT_DIR / "hero-prompts.yaml"
JPG_SCRATCH_DIR = Path(
    "/private/tmp/claude-501/-Users-Dave-MyWork/e935127e-b58b-4598-874f-1daaa1d551cf"
    "/scratchpad/geo-hero-jpg"
)
WEBP_OUT_DIR = REPO_ROOT / "site" / "img" / "hero"


def load_env_from_file(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_env():
    load_env_from_file(Path.cwd() / ".env")
    load_env_from_file(Path.home() / ".openai.env")


def load_prompts() -> dict:
    with open(PROMPTS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or not data:
        print(f"錯誤：{PROMPTS_PATH} 讀不到任何 prompt", file=sys.stderr)
        sys.exit(1)
    return data


def build_prompt(subject: str) -> str:
    return f"{STYLE_PREFIX}. {subject}."


def is_rate_limited(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "rate_limit" in msg


def generate_one(client, page_id: str, subject: str, quality: str, force: bool):
    """回傳 (status, page_id, attempts, elapsed_seconds, error_or_None)。
    status ∈ {"ok", "skip", "fail"}。"""
    webp_path = WEBP_OUT_DIR / f"{page_id}.webp"
    if webp_path.exists() and not force:
        return ("skip", page_id, 0, 0.0, None)

    JPG_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    WEBP_OUT_DIR.mkdir(parents=True, exist_ok=True)
    jpg_path = JPG_SCRATCH_DIR / f"{page_id}.jpg"

    prompt = build_prompt(subject)
    started = time.time()
    print(f"  [START] {page_id}", file=sys.stderr)

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = client.images.generate(
                model=MODEL,
                prompt=prompt,
                size=SIZE,
                quality=quality,
                n=1,
                output_format="jpeg",
            )
            b64 = result.data[0].b64_json
            jpg_path.write_bytes(base64.b64decode(b64))
            break  # 成功，跳出重試迴圈
        except Exception as e:
            last_err = e
            if is_rate_limited(e) and attempt < MAX_RETRIES:
                print(
                    f"  [{page_id}] 撞 429/限流，第 {attempt} 次嘗試失敗，"
                    f"等待 {BACKOFF_SECONDS}s 後重試...",
                    file=sys.stderr,
                )
                time.sleep(BACKOFF_SECONDS)
                continue
            elapsed = time.time() - started
            return ("fail", page_id, attempt, elapsed, str(e))
    else:
        # 理論上不會走到這裡（迴圈內每個失敗分支都會 return），保留以防萬一
        elapsed = time.time() - started
        return ("fail", page_id, MAX_RETRIES, elapsed, str(last_err))

    # jpg -> webp（最長邊 1200，與現有史料照同規）
    cwebp_cmd = [
        "cwebp", "-quiet", "-q", "82",
        "-resize", str(WEBP_MAX_EDGE), "0",
        str(jpg_path), "-o", str(webp_path),
    ]
    proc = subprocess.run(cwebp_cmd, capture_output=True, text=True)
    elapsed = time.time() - started
    if proc.returncode != 0:
        return ("fail", page_id, attempt, elapsed, f"cwebp 失敗：{proc.stderr.strip()}")

    return ("ok", page_id, attempt, elapsed, None)


def main():
    load_env()
    parser = argparse.ArgumentParser(description="taiwan-geo-db 情境 hero 圖批次生成（gpt-image-2）")
    parser.add_argument("--only", default=None, help="逗號分隔的 page-id 清單，只生這幾張")
    parser.add_argument("--quality", default=DEFAULT_QUALITY,
                         choices=["low", "medium", "high", "auto"])
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--force", action="store_true",
                         help="已存在的 webp 也重生（預設跳過既有檔，方便補跑）")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("錯誤：找不到 OPENAI_API_KEY（找過 cwd/.env、~/.openai.env、shell 環境變數）",
              file=sys.stderr)
        sys.exit(1)

    from openai import OpenAI
    client = OpenAI()

    prompts = load_prompts()

    if args.only:
        ids = [x.strip() for x in args.only.split(",") if x.strip()]
        missing = [i for i in ids if i not in prompts]
        if missing:
            print(f"錯誤：--only 指定的 id 不在 hero-prompts.yaml：{missing}", file=sys.stderr)
            sys.exit(1)
        selected = [(i, prompts[i]) for i in ids]
    else:
        selected = sorted(prompts.items())

    total = len(selected)
    print(
        f"共 {total} 張 -> {WEBP_OUT_DIR}（並發 {args.concurrency}、quality={args.quality}、"
        f"force={args.force}）",
        file=sys.stderr,
    )

    results = []
    done_count = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {
            ex.submit(generate_one, client, pid, subject, args.quality, args.force): pid
            for pid, subject in selected
        }
        for fut in as_completed(futures):
            pid = futures[fut]
            res = fut.result()
            results.append(res)
            done_count += 1
            status, _, attempts, elapsed, err = res
            if status == "ok":
                print(f"  [OK]   ({done_count}/{total}) {pid} — {elapsed:.1f}s，重試 {attempts - 1} 次")
            elif status == "skip":
                print(f"  [SKIP] ({done_count}/{total}) {pid} — 已存在，跳過")
            else:
                print(
                    f"  [FAIL] ({done_count}/{total}) {pid} — 嘗試 {attempts} 次後失敗：{err}",
                    file=sys.stderr,
                )

    oks = [r for r in results if r[0] == "ok"]
    skips = [r for r in results if r[0] == "skip"]
    fails = [r for r in results if r[0] == "fail"]

    print(f"\n完成：成功 {len(oks)}、跳過 {len(skips)}、失敗 {len(fails)}（共 {total}）")

    if fails:
        print("\n失敗清單：", file=sys.stderr)
        for r in fails:
            print(f"  - {r[1]}: {r[4]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

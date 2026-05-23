"""
FER2013 데이터셋 다운로드 (실제 얼굴 표정 48x48).

사용법:
  python scripts/download_fer2013.py

자동: Hugging Face 공개 미러 (약 200MB, 1~10분)
수동: Kaggle FER2013 → data/fer2013/fer2013.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "fer2013"
OUT_CSV = OUT_DIR / "fer2013.csv"

HF_TRAIN_URL = (
    "https://huggingface.co/datasets/abhilash88/fer2013-enhanced/resolve/main/train.csv"
)


def _download_file(url: str, dest: Path) -> bool:
    try:
        import urllib.request

        print(f"다운로드: {url}")
        print(f"  → {dest.name} (Wi-Fi 유지, 수 분 걸릴 수 있음)")

        def progress(block_num, block_size, total_size):
            if total_size > 0 and block_num % 80 == 0:
                pct = min(100, block_num * block_size * 100 // total_size)
                print(f"\r  진행: {pct}%", end="", flush=True)

        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print()
        return dest.exists() and dest.stat().st_size > 100_000
    except Exception as exc:
        print(f"  실패: {exc}")
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def _convert_hf_csv(src: Path, dest: Path) -> int:
    written = 0
    with src.open(encoding="utf-8", newline="") as fin, dest.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=["emotion", "pixels", "Usage"])
        writer.writeheader()
        for row in reader:
            emo = row.get("emotion")
            pixels = row.get("pixels")
            usage = (row.get("Usage") or row.get(" usage") or "Training").strip()
            if emo is None or not pixels:
                continue
            writer.writerow({"emotion": emo, "pixels": pixels, "Usage": usage})
            written += 1
    return written


def _merge_hf_to_fer2013() -> bool:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT_DIR / "_hf_train.csv"

    try:
        if not _download_file(HF_TRAIN_URL, tmp):
            return False

        print("fer2013.csv로 변환 중...")
        written = _convert_hf_csv(tmp, OUT_CSV)
        ok = OUT_CSV.exists() and OUT_CSV.stat().st_size > 1_000_000 and written > 10_000
        if ok:
            mb = OUT_CSV.stat().st_size // 1024 // 1024
            print(f"저장 완료: {OUT_CSV} ({mb} MB, {written:,}행)")
        return ok
    finally:
        tmp.unlink(missing_ok=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_CSV.exists() and OUT_CSV.stat().st_size > 1_000_000:
        print(f"이미 존재합니다: {OUT_CSV}")
        return

    print("Hugging Face에서 FER2013 다운로드를 시작합니다.\n")
    if _merge_hf_to_fer2013():
        return

    print(
        "\n자동 다운로드에 실패했습니다.\n"
        "수동 방법:\n"
        "  1. https://www.kaggle.com/datasets/msambare/fer2013\n"
        "  2. fer2013.csv를 다음 경로에 저장:\n"
        f"     {OUT_CSV}\n"
        "  3. python scripts/train_emotion_classifier.py\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

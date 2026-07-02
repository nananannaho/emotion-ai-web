"""
기존 emotion_clf.joblib 을 트리 수만 줄여 용량을 낮춥니다 (재학습·다운로드 불필요).

  python scripts/shrink_emotion_model.py
  python scripts/shrink_emotion_model.py --trees 50
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import EMOTION_LABELS, WEIGHTS_DIR  # noqa: E402
from models.emotion_ml import ThinRandomForest  # noqa: E402

IN_PATH = WEIGHTS_DIR / "emotion_clf.joblib"
OUT_PATH = WEIGHTS_DIR / "emotion_clf.joblib"
BACKUP = WEIGHTS_DIR / "emotion_clf.joblib.bak"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trees", type=int, default=60, help="유지할 결정 트리 수 (기본 60)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not IN_PATH.exists():
        print(f"파일 없음: {IN_PATH}")
        sys.exit(1)

    data = joblib.load(IN_PATH)
    old = data["model"]
    n_total = len(getattr(old, "estimators_", []) or [])
    n_keep = max(10, min(args.trees, n_total))

    if n_keep >= n_total:
        print(f"이미 {n_total}트리 — 축소 불필요. compress=9만 적용합니다.")
        thin = old
    else:
        print(f"{n_total} → {n_keep} 트리로 축소")
        thin = ThinRandomForest.from_random_forest(old, n_keep)

    payload = {
        "model": thin,
        "labels": list(data.get("labels", EMOTION_LABELS)),
        "source": str(data.get("source", "")) + f"+shrunk{n_keep}",
        "n_samples": data.get("n_samples"),
    }

    if args.dry_run:
        tmp = WEIGHTS_DIR / "_shrink_preview.joblib"
        joblib.dump(payload, tmp, compress=9)
        mb = tmp.stat().st_size / (1024 * 1024)
        tmp.unlink()
        print(f"예상 크기: {mb:.1f} MB")
        return

    if IN_PATH.exists() and not BACKUP.exists():
        IN_PATH.replace(BACKUP)
        print(f"백업: {BACKUP.name}")

    joblib.dump(payload, OUT_PATH, compress=9)
    mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"저장: {OUT_PATH} ({mb:.1f} MB)")
    if mb > 95:
        print("경고: 95MB 초과 — GitHub push 거부될 수 있음")
        sys.exit(1)


if __name__ == "__main__":
    main()

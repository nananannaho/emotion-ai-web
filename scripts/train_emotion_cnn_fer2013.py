"""
로컬 전용: FER2013으로 TensorFlow CNN 학습 (가장 정확, PC + GPU 권장).

  pip install tensorflow
  python scripts/download_fer2013.py
  python scripts/train_emotion_cnn_fer2013.py

결과: weights/emotion_cnn.keras
Render 무료 서버에서는 TensorFlow 미사용 → 로컬에서 run.bat 실행 시 CNN 사용.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import EMOTION_LABELS, WEIGHTS_DIR  # noqa: E402
from models.emotion_cnn import WEIGHTS_PATH, _build_emotion_model  # noqa: E402

FER_CSV = ROOT / "data" / "fer2013" / "fer2013.csv"


def load_fer_arrays(max_per_class: int = 4000):
    xs, ys = [], []
    counts = {i: 0 for i in range(7)}
    with FER_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            use = (row.get("Usage") or "").strip()
            if use and use != "Training":
                continue
            e = int(row["emotion"])
            if counts[e] >= max_per_class:
                continue
            pix = np.asarray(row["pixels"].split(), dtype=np.float32).reshape(48, 48, 1) / 255.0
            xs.append(pix)
            ys.append(e)
            counts[e] += 1
    return np.array(xs), np.array(ys)


def main():
    if not FER_CSV.exists():
        print("먼저: python scripts/download_fer2013.py")
        sys.exit(1)

    import tensorflow as tf

    print("FER2013 CNN 학습 시작 (시간이 꽤 걸립니다)...")
    X, y = load_fer_arrays()
    y_cat = tf.keras.utils.to_categorical(y, len(EMOTION_LABELS))

    model = _build_emotion_model()
    model.fit(
        X,
        y_cat,
        epochs=12,
        batch_size=64,
        validation_split=0.1,
        verbose=1,
    )
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    model.save(WEIGHTS_PATH)
    print(f"저장: {WEIGHTS_PATH}")
    print("로컬 실행: run.bat (USE_LIGHT_ML 끄면 CNN 사용)")


if __name__ == "__main__":
    main()

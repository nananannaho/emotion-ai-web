"""
7가지 표정 분류기 학습 (scikit-learn) — Render 경량 배포용.

로컬에서 1회 실행:
  python scripts/train_emotion_classifier.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import EMOTION_LABELS, WEIGHTS_DIR  # noqa: E402
from models.emotion_features import extract_face_features  # noqa: E402

OUT_PATH = WEIGHTS_DIR / "emotion_clf.joblib"


def _draw_base(rng: np.random.Generator) -> np.ndarray:
    img = np.full((48, 48), rng.integers(70, 130), dtype=np.uint8)
    cv2.ellipse(img, (24, 26), (16, 20), 0, 0, 360, int(rng.integers(140, 200)), -1)
    cv2.circle(img, (16, 20), 3, 40, -1)
    cv2.circle(img, (32, 20), 3, 40, -1)
    return img


def _synthesize(emotion: str, rng: np.random.Generator) -> np.ndarray:
    img = _draw_base(rng)
    noise = rng.normal(0, 6, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if emotion == "happy":
        cv2.ellipse(img, (24, 32), (10, 5), 0, 0, 180, 220, 2)
        img = cv2.add(img, 25)
    elif emotion == "sad":
        cv2.ellipse(img, (24, 34), (8, 4), 0, 0, 180, 60, 2)
        img = cv2.subtract(img, 20)
    elif emotion == "angry":
        cv2.line(img, (14, 17), (18, 19), 30, 2)
        cv2.line(img, (34, 17), (30, 19), 30, 2)
        img = cv2.convertScaleAbs(img, alpha=1.2, beta=-15)
    elif emotion == "surprise":
        cv2.circle(img, (24, 30), 5, 200, 2)
        cv2.circle(img, (16, 18), 4, 180, -1)
        cv2.circle(img, (32, 18), 4, 180, -1)
    elif emotion == "fear":
        img = cv2.subtract(img, 15)
        cv2.ellipse(img, (24, 32), (8, 4), 0, 0, 180, 100, 2)
    elif emotion == "disgust":
        cv2.line(img, (20, 30), (28, 32), 80, 2)
        img[:, :24] = cv2.subtract(img[:, :24], 10)
    # neutral: base only

    blur = rng.integers(0, 2)
    if blur:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def build_dataset(samples_per_class: int = 400) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    xs, ys = [], []
    for label_idx, emo in enumerate(EMOTION_LABELS):
        for _ in range(samples_per_class):
            face = _synthesize(emo, rng)
            xs.append(extract_face_features(face))
            ys.append(label_idx)
    return np.vstack(xs), np.array(ys, dtype=np.int32)


def main():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    import joblib

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    print("데이터 생성 중...")
    X, y = build_dataset()
    print(f"샘플: {len(y)}, 특징 차원: {X.shape[1]}")

    clf = RandomForestClassifier(
        n_estimators=120,
        max_depth=18,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    scores = cross_val_score(clf, X, y, cv=5)
    print(f"교차 검증 정확도: {scores.mean():.3f} (+/- {scores.std():.3f})")

    clf.fit(X, y)
    joblib.dump({"model": clf, "labels": EMOTION_LABELS}, OUT_PATH)
    print(f"저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()

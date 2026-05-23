"""
7가지 표정 분류기 학습 — FER2013 실제 얼굴 + (선택) 직접 촬영 사진.

1) FER2013 받기:  python scripts/download_fer2013.py
2) 학습 실행:    python scripts/train_emotion_classifier.py
3) 배포:         git push 후 Render Manual Deploy
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import EMOTION_LABELS, WEIGHTS_DIR  # noqa: E402
from models.emotion_features import extract_face_features  # noqa: E402

FER_CSV = ROOT / "data" / "fer2013" / "fer2013.csv"
CUSTOM_DIR = ROOT / "data" / "emotions"
OUT_PATH = WEIGHTS_DIR / "emotion_clf.joblib"

# FER2013 emotion id → 우리 라벨 (동일 순서)
FER_ID_TO_LABEL = list(EMOTION_LABELS)


def _augment(face: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    img = face.copy()
    if rng.random() < 0.5:
        img = cv2.flip(img, 1)
    alpha = rng.uniform(0.85, 1.15)
    beta = rng.integers(-15, 16)
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    if rng.random() < 0.3:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    return img


def _load_fer2013(
    max_per_class: int = 4000,
    usage: str = "Training",
) -> tuple[list[np.ndarray], list[int]]:
    if not FER_CSV.exists():
        return [], []

    xs: list[np.ndarray] = []
    ys: list[int] = []
    counts = {i: 0 for i in range(7)}

    print(f"FER2013 로드: {FER_CSV}")
    with FER_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            use = (row.get("Usage") or row.get(" usage") or "").strip()
            if use and use != usage:
                continue
            emo_id = int(row["emotion"])
            if emo_id < 0 or emo_id > 6 or counts[emo_id] >= max_per_class:
                continue
            pixels = np.asarray(row["pixels"].split(), dtype=np.uint8)
            if pixels.size != 48 * 48:
                continue
            face = pixels.reshape(48, 48)
            xs.append(face)
            ys.append(emo_id)
            counts[emo_id] += 1

    print(f"  FER2013 샘플: {len(ys)} (클래스별 {counts})")
    return xs, ys


def _load_custom_folders() -> tuple[list[np.ndarray], list[int]]:
    if not CUSTOM_DIR.exists():
        return [], []

    faces: list[np.ndarray] = []
    labels: list[int] = []
    label_map = {name: i for i, name in enumerate(EMOTION_LABELS)}

    for emo_name, idx in label_map.items():
        folder = CUSTOM_DIR / emo_name
        if not folder.is_dir():
            continue
        for path in list(folder.glob("*.jpg")) + list(folder.glob("*.png")) + list(folder.glob("*.jpeg")):
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            face = cv2.resize(img, (48, 48))
            faces.append(face)
            labels.append(idx)

    if faces:
        print(f"  직접 촬영 사진: {len(faces)}장 ({CUSTOM_DIR})")
    return faces, labels


def _build_feature_matrix(
    faces: list[np.ndarray],
    labels: list[int],
    augment_times: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    feats, ys = [], []

    for face, label in zip(faces, labels):
        feats.append(extract_face_features(face))
        ys.append(label)
        for _ in range(augment_times):
            aug = _augment(face, rng)
            feats.append(extract_face_features(aug))
            ys.append(label)

    return np.vstack(feats), np.array(ys, dtype=np.int32)


def main():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split
    import joblib

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    fer_faces, fer_labels = _load_fer2013()
    custom_faces, custom_labels = _load_custom_folders()

    if not fer_faces and not custom_faces:
        print("\n학습용 이미지가 없습니다.")
        print("  python scripts/download_fer2013.py")
        print("  또는 data/emotions/ 폴더에 사진 추가")
        sys.exit(1)

    all_faces = fer_faces + custom_faces
    all_labels = fer_labels + custom_labels
    print(f"\n총 얼굴 이미지: {len(all_labels)}장 → 특징 추출 중...")
    X, y = _build_feature_matrix(all_faces, all_labels, augment_times=1)
    print(f"학습 벡터: {X.shape[0]}개, 차원: {X.shape[1]}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )

    # GitHub 파일 100MB 제한 — 트리 수·깊이를 제한해 joblib 크기 유지
    clf = RandomForestClassifier(
        n_estimators=120,
        max_depth=18,
        max_features="sqrt",
        min_samples_leaf=3,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    print("\n검증 결과 (FER2013 기반):")
    print(
        classification_report(
            y_test,
            y_pred,
            target_names=EMOTION_LABELS,
            zero_division=0,
        )
    )

    clf.fit(X, y)
    joblib.dump(
        {
            "model": clf,
            "labels": EMOTION_LABELS,
            "source": "fer2013+custom",
            "n_samples": int(len(y)),
        },
        OUT_PATH,
        compress=3,
    )
    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"\n저장 완료: {OUT_PATH} ({size_mb:.1f} MB)")
    if size_mb > 95:
        print("경고: 파일이 95MB를 넘습니다. GitHub push가 거부될 수 있습니다.")
        sys.exit(1)
    print("다음: git add weights/emotion_clf.joblib && git push → Render 배포")


if __name__ == "__main__":
    main()

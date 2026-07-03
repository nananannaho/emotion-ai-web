"""얼굴 영상(48x48)에서 감정 분류용 특징 추출."""

from __future__ import annotations

import cv2
import numpy as np


def extract_face_features(face_gray: np.ndarray) -> np.ndarray:
    """정규화된 특징 벡터 (RandomForest / MLP 입력)."""
    if face_gray.shape != (48, 48):
        face_gray = cv2.resize(face_gray, (48, 48))

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    face = clahe.apply(face_gray.astype(np.uint8))
    face_f = face.astype(np.float32) / 255.0

    parts: list[np.ndarray] = []
    grid = 4
    ch, cw = 12, 12
    for r in range(grid):
        for c in range(grid):
            cell = face_f[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw]
            parts.append(cell.flatten())

    h = face.shape[0]
    eye = face_f[: h // 3, :]
    mouth = face_f[h * 2 // 3 :, :]
    cheek = face_f[h // 3 : h * 2 // 3, :]

    edges = cv2.Canny(face, 40, 120).astype(np.float32) / 255.0

    stats = np.array(
        [
            np.mean(face_f),
            np.std(face_f),
            np.mean(eye),
            np.mean(mouth),
            np.mean(mouth) - np.mean(eye),
            np.std(mouth),
            np.mean(cheek),
            np.sum(edges) / edges.size,
            float(np.percentile(face_f, 25)),
            float(np.percentile(face_f, 75)),
        ],
        dtype=np.float32,
    )

    vec = np.concatenate(parts + [stats]).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 1e-6 else vec

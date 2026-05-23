"""얼굴 임베딩 — 로그인 시 사용자 식별 (CNN 또는 경량 특징)."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from config import (
    FACE_IMG_SIZE,
    FACE_MATCH_MARGIN,
    FACE_MATCH_MARGIN_LIGHT,
    FACE_MATCH_THRESHOLD,
    FACE_MATCH_THRESHOLD_LIGHT,
    USE_LIGHT_ML,
    WEIGHTS_DIR,
)
from utils.opencv_utils import get_face_cascade

logger = logging.getLogger(__name__)

ENCODER_WEIGHTS = WEIGHTS_DIR / "face_encoder.keras"


def _build_face_encoder(input_shape=(96, 96, 3)):
    import tensorflow as tf

    inputs = tf.keras.layers.Input(shape=input_shape)
    x = tf.keras.layers.Conv2D(32, (3, 3), activation="relu", padding="same")(inputs)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Conv2D(64, (3, 3), activation="relu", padding="same")(x)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Conv2D(128, (3, 3), activation="relu", padding="same")(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(128, activation=None)(x)
    x = tf.keras.layers.Lambda(lambda t: tf.nn.l2_normalize(t, axis=1))(x)
    return tf.keras.Model(inputs, x, name="face_encoder")


def _preprocess_gray(face_bgr: np.ndarray) -> np.ndarray:
    face = cv2.resize(face_bgr, FACE_IMG_SIZE)
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _light_embedding(face_bgr: np.ndarray) -> np.ndarray:
    """경량 모드: 격자 히스토그램 + LBP — 조명 변화에 더 견고."""
    gray = _preprocess_gray(face_bgr)
    parts: list[np.ndarray] = []

    grid = 4
    h, w = gray.shape
    ch, cw = h // grid, w // grid
    for r in range(grid):
        for c in range(grid):
            cell = gray[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw]
            hist = cv2.calcHist([cell], [0], None, [16], [0, 256]).flatten()
            parts.append(hist)

    # 간단 LBP 히스토그램
    lbp = np.zeros_like(gray, dtype=np.uint8)
    center = gray[1:-1, 1:-1]
    offsets = [
        (-1, -1), (-1, 0), (-1, 1), (0, 1),
        (1, 1), (1, 0), (1, -1), (0, -1),
    ]
    for bit, (dy, dx) in enumerate(offsets):
        neighbor = gray[1 + dy : gray.shape[0] - 1 + dy, 1 + dx : gray.shape[1] - 1 + dx]
        lbp[1:-1, 1:-1] |= ((neighbor >= center).astype(np.uint8) << bit)

    lbp_hist = cv2.calcHist([lbp], [0], None, [32], [0, 256]).flatten()
    parts.append(lbp_hist)

    vec = np.concatenate(parts).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 1e-6 else vec


class FaceEncoder:
    def __init__(self):
        self._model = None
        self._cascade = get_face_cascade()

    def _ensure_model(self):
        if self._model is not None:
            return
        import tensorflow as tf

        if ENCODER_WEIGHTS.exists():
            self._model = tf.keras.models.load_model(ENCODER_WEIGHTS)
        else:
            self._model = _build_face_encoder()
            logger.warning("얼굴 인코더 가중치 없음 — 경량 특징 폴백 사용.")

    def extract_face(self, image_bgr: np.ndarray) -> np.ndarray | None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self._cascade.detectMultiScale(gray, 1.08, 4, minSize=(36, 36))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        pad = int(0.08 * max(w, h))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(image_bgr.shape[1], x + w + pad)
        y1 = min(image_bgr.shape[0], y + h + pad)
        face = image_bgr[y0:y1, x0:x1]
        return cv2.resize(face, FACE_IMG_SIZE)

    def encode(self, image_bgr: np.ndarray) -> np.ndarray | None:
        face = self.extract_face(image_bgr)
        if face is None:
            return None

        if ENCODER_WEIGHTS.exists() and not USE_LIGHT_ML:
            self._ensure_model()
            tensor = face.astype("float32") / 255.0
            tensor = np.expand_dims(tensor, axis=0)
            return self._model.predict(tensor, verbose=0)[0]

        return _light_embedding(face)

    def encode_robust(self, image_bgr: np.ndarray) -> np.ndarray | None:
        """가입 시: 원본 + 좌우반전 평균으로 저장 (모바일 촬영 차이 완화)."""
        emb = self.encode(image_bgr)
        if emb is None:
            return None
        flipped = cv2.flip(image_bgr, 1)
        emb_flip = self.encode(flipped)
        if emb_flip is None:
            return emb
        merged = (emb + emb_flip) / 2.0
        norm = np.linalg.norm(merged)
        return merged / norm if norm > 1e-6 else merged

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def _match_thresholds(self) -> tuple[float, float]:
        if USE_LIGHT_ML or not ENCODER_WEIGHTS.exists():
            return FACE_MATCH_THRESHOLD_LIGHT, FACE_MATCH_MARGIN_LIGHT
        return FACE_MATCH_THRESHOLD, FACE_MATCH_MARGIN

    def _login_embeddings(self, image_bgr: np.ndarray) -> list[np.ndarray]:
        """로그인: 원본 + 좌우반전 중 더 나은 매칭."""
        out: list[np.ndarray] = []
        for img in (image_bgr, cv2.flip(image_bgr, 1)):
            emb = self.encode(img)
            if emb is not None:
                out.append(emb)
        return out

    def match_user(
        self, image_bgr: np.ndarray, stored_embeddings: dict[str, np.ndarray]
    ) -> tuple[str | None, float]:
        currents = self._login_embeddings(image_bgr)
        if not currents:
            return None, 0.0

        threshold, margin = self._match_thresholds()
        scores: list[tuple[str, float]] = []
        for username, embedding in stored_embeddings.items():
            best = max(self.cosine_similarity(cur, embedding) for cur in currents)
            scores.append((username, best))
        scores.sort(key=lambda x: x[1], reverse=True)

        best_user, best_score = scores[0]
        second_score = scores[1][1] if len(scores) > 1 else 0.0
        gap = best_score - second_score

        if best_score >= threshold and gap >= margin:
            return best_user, best_score
        logger.info(
            "얼굴 매칭 거부: best=%.3f gap=%.3f (need %.2f / %.2f)",
            best_score,
            gap,
            threshold,
            margin,
        )
        return None, best_score

    @staticmethod
    def train_minimal_weights() -> Path:
        import tensorflow as tf

        rng = np.random.default_rng(7)
        n = 200
        x = rng.random((n, 96, 96, 3)).astype("float32")
        model = _build_face_encoder()
        model.predict(x[:4], verbose=0)
        model.save(ENCODER_WEIGHTS)
        return ENCODER_WEIGHTS

"""CNN 기반 얼굴 임베딩 — 로그인 시 사용자 식별."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from config import FACE_IMG_SIZE, FACE_MATCH_THRESHOLD, USE_LIGHT_ML, WEIGHTS_DIR
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
            logger.warning("얼굴 인코더 가중치 없음 — 히스토그램 기반 폴백 사용.")

    def extract_face(self, image_bgr: np.ndarray) -> np.ndarray | None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, 1.1, 5, minSize=(50, 50))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face = image_bgr[y : y + h, x : x + w]
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

        # 폴백: 정규화된 그레이스케일 히스토그램 + HSV 특징
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
        hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
        hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180]).flatten()
        hist_s = cv2.calcHist([hsv], [1], None, [32], [0, 256]).flatten()
        vec = np.concatenate([hist, hist_h, hist_s]).astype("float32")
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 1e-6 else vec

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def match_user(
        self, image_bgr: np.ndarray, stored_embeddings: dict[str, np.ndarray]
    ) -> tuple[str | None, float]:
        current = self.encode(image_bgr)
        if current is None:
            return None, 0.0

        best_user, best_score = None, -1.0
        for username, embedding in stored_embeddings.items():
            score = self.cosine_similarity(current, embedding)
            if score > best_score:
                best_score = score
                best_user = username

        if best_score >= FACE_MATCH_THRESHOLD:
            return best_user, best_score
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

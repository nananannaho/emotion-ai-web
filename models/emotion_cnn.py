"""합성곱 신경망(CNN) 기반 얼굴 감정 분류."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from config import EMOTION_IMG_SIZE, EMOTION_LABELS, USE_LIGHT_ML, WEIGHTS_DIR
from utils.opencv_utils import get_face_cascade

logger = logging.getLogger(__name__)

WEIGHTS_PATH = WEIGHTS_DIR / "emotion_cnn.keras"


def _build_emotion_model(input_shape=(48, 48, 1), num_classes: int = 7):
    import tensorflow as tf

    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=input_shape),
            tf.keras.layers.Conv2D(32, (3, 3), padding="same", activation="relu"),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Conv2D(64, (3, 3), padding="same", activation="relu"),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(0.25),
            tf.keras.layers.Conv2D(128, (3, 3), padding="same", activation="relu"),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(256, activation="relu"),
            tf.keras.layers.Dropout(0.4),
            tf.keras.layers.Dense(num_classes, activation="softmax"),
        ],
        name="emotion_cnn",
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


class EmotionCNN:
    """얼굴 영역에서 7가지 감정을 CNN으로 분류."""

    def __init__(self):
        self._model = None
        self._cascade = get_face_cascade()

    def _ensure_model(self):
        if self._model is not None:
            return
        import tensorflow as tf

        if WEIGHTS_PATH.exists():
            self._model = tf.keras.models.load_model(WEIGHTS_PATH)
            logger.info("감정 CNN 가중치 로드: %s", WEIGHTS_PATH)
        else:
            self._model = _build_emotion_model()
            logger.warning(
                "감정 CNN 가중치 없음 — python init_models.py 실행 권장. 휴리스틱 폴백 사용."
            )

    def detect_face(self, image_bgr: np.ndarray) -> tuple | None:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return int(x), int(y), int(w), int(h)

    def preprocess_face(self, image_bgr: np.ndarray, box: tuple | None = None) -> np.ndarray | None:
        if box is None:
            box = self.detect_face(image_bgr)
        if box is None:
            return None
        x, y, w, h = box
        face = image_bgr[y : y + h, x : x + w]
        face_gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        face_resized = cv2.resize(face_gray, EMOTION_IMG_SIZE)
        face_norm = face_resized.astype("float32") / 255.0
        return face_norm.reshape(1, *EMOTION_IMG_SIZE, 1)

    def _heuristic_emotion(self, face_gray: np.ndarray) -> dict[str, float]:
        """가중치 없을 때 사용하는 간단한 밝기·대비 기반 추정."""
        mean = float(np.mean(face_gray))
        std = float(np.std(face_gray))
        scores = {
            "happy": max(0.0, (mean - 110) / 80),
            "sad": max(0.0, (130 - mean) / 80),
            "angry": max(0.0, (std - 35) / 40),
            "surprise": max(0.0, (std - 45) / 35),
            "fear": max(0.0, (120 - mean) / 60) * 0.5,
            "disgust": 0.15,
            "neutral": 0.4,
        }
        total = sum(scores.values()) or 1.0
        return {k: v / total for k, v in scores.items()}

    def predict(self, image_bgr: np.ndarray) -> dict:
        box = self.detect_face(image_bgr)
        if box is None:
            return {
                "success": False,
                "error": "얼굴을 찾을 수 없습니다. 카메라를 정면으로 바라봐 주세요.",
            }

        x, y, w, h = box
        face = image_bgr[y : y + h, x : x + w]
        face_gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        face_resized = cv2.resize(face_gray, EMOTION_IMG_SIZE)

        if WEIGHTS_PATH.exists() and not USE_LIGHT_ML:
            self._ensure_model()
            tensor = face_resized.astype("float32") / 255.0
            tensor = tensor.reshape(1, *EMOTION_IMG_SIZE, 1)
            probs = self._model.predict(tensor, verbose=0)[0]
            distribution = {EMOTION_LABELS[i]: float(probs[i]) for i in range(len(EMOTION_LABELS))}
        else:
            distribution = self._heuristic_emotion(face_resized)

        dominant = max(distribution, key=distribution.get)
        return {
            "success": True,
            "emotion": dominant,
            "confidence": float(distribution[dominant]),
            "distribution": distribution,
            "face_box": {"x": x, "y": y, "w": w, "h": h},
        }

    @staticmethod
    def train_minimal_weights(epochs: int = 3) -> Path:
        """데모용 합성 데이터로 CNN 가중치 생성."""
        import tensorflow as tf

        rng = np.random.default_rng(42)
        n = 400
        x = rng.random((n, 48, 48, 1)).astype("float32")
        y = tf.keras.utils.to_categorical(rng.integers(0, 7, n), 7)

        model = _build_emotion_model()
        model.fit(x, y, epochs=epochs, batch_size=32, validation_split=0.1, verbose=1)
        model.save(WEIGHTS_PATH)
        return WEIGHTS_PATH

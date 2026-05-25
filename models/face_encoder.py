"""얼굴 임베딩 — 로그인 시 사용자 식별 (CNN 또는 경량 특징)."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from config import (
    FACE_DUPLICATE_THRESHOLD,
    FACE_DUPLICATE_THRESHOLD_LIGHT,
    FACE_IMG_SIZE,
    FACE_MATCH_MARGIN,
    FACE_MATCH_MARGIN_LIGHT,
    FACE_MATCH_THRESHOLD,
    FACE_MATCH_THRESHOLD_LIGHT,
    FACE_VERIFY_AVG_THRESHOLD,
    FACE_VERIFY_AVG_THRESHOLD_LIGHT,
    FACE_VERIFY_THRESHOLD,
    FACE_VERIFY_THRESHOLD_LIGHT,
    USE_LIGHT_ML,
    WEIGHTS_DIR,
)
from utils.opencv_utils import get_face_cascade

logger = logging.getLogger(__name__)

ENCODER_WEIGHTS = WEIGHTS_DIR / "face_encoder.keras"
LIGHT_EMBEDDING_DIM = 16 * 16 + 32  # 격자 히스토그램 + LBP
CNN_EMBEDDING_DIM = 128


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
    if not np.isfinite(vec).all():
        raise ValueError("invalid light embedding values")
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

    @staticmethod
    def expected_embedding_dim() -> int:
        if USE_LIGHT_ML or not ENCODER_WEIGHTS.exists():
            return LIGHT_EMBEDDING_DIM
        return CNN_EMBEDDING_DIM

    @staticmethod
    def normalize_embedding(embedding: np.ndarray) -> np.ndarray | None:
        if embedding is None:
            return None
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vec.size == 0 or not np.isfinite(vec).all():
            return None
        norm = np.linalg.norm(vec)
        if norm < 1e-6:
            return None
        return vec / norm

    def _crop_largest_face(self, image_bgr: np.ndarray, faces) -> np.ndarray:
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        pad = int(0.12 * max(w, h))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(image_bgr.shape[1], x + w + pad)
        y1 = min(image_bgr.shape[0], y + h + pad)
        face = image_bgr[y0:y1, x0:x1]
        return cv2.resize(face, FACE_IMG_SIZE)

    def _detect_faces(self, gray: np.ndarray):
        attempts = (
            (1.08, 4, 36),
            (1.05, 3, 28),
            (1.12, 5, 40),
            (1.2, 6, 32),
        )
        for scale, neighbors, min_sz in attempts:
            faces = self._cascade.detectMultiScale(
                gray, scale, neighbors, minSize=(min_sz, min_sz)
            )
            if len(faces) > 0:
                return faces
        return []

    def extract_face(self, image_bgr: np.ndarray, *, allow_center_fallback: bool = False) -> np.ndarray | None:
        if image_bgr is None or image_bgr.size == 0:
            return None

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        variants = (
            cv2.equalizeHist(gray),
            cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray),
            gray,
        )
        for variant in variants:
            faces = self._detect_faces(variant)
            if len(faces) > 0:
                return self._crop_largest_face(image_bgr, faces)

        if allow_center_fallback:
            h, w = image_bgr.shape[:2]
            side = int(min(h, w) * 0.72)
            if side >= 48:
                x0 = (w - side) // 2
                y0 = (h - side) // 2
                crop = image_bgr[y0 : y0 + side, x0 : x0 + side]
                return cv2.resize(crop, FACE_IMG_SIZE)

        return None

    def encode(self, image_bgr: np.ndarray, *, allow_center_fallback: bool = False) -> np.ndarray | None:
        face = self.extract_face(image_bgr, allow_center_fallback=allow_center_fallback)
        if face is None:
            return None

        if ENCODER_WEIGHTS.exists() and not USE_LIGHT_ML:
            self._ensure_model()
            tensor = face.astype("float32") / 255.0
            tensor = np.expand_dims(tensor, axis=0)
            vec = self._model.predict(tensor, verbose=0)[0]
            return self.normalize_embedding(vec)

        try:
            return self.normalize_embedding(_light_embedding(face))
        except Exception as exc:
            logger.warning("경량 얼굴 특징 추출 실패, 단순 히스토그램 폴백: %s", exc)
            gray = _preprocess_gray(face)
            hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten().astype(np.float32)
            return self.normalize_embedding(hist)

    def is_compatible_embedding(self, embedding: np.ndarray) -> bool:
        vec = self.normalize_embedding(embedding)
        if vec is None:
            return False
        return vec.size == self.expected_embedding_dim()

    def encode_robust(self, image_bgr: np.ndarray) -> np.ndarray | None:
        """가입 시: 원본 + 좌우반전 평균으로 저장 (모바일 촬영 차이 완화)."""
        emb = self.encode(image_bgr, allow_center_fallback=True)
        if emb is None:
            return None
        flipped = cv2.flip(image_bgr, 1)
        emb_flip = self.encode(flipped, allow_center_fallback=True)
        if emb_flip is None:
            return emb
        merged = (emb + emb_flip) / 2.0
        return self.normalize_embedding(merged)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        va = FaceEncoder.normalize_embedding(a)
        vb = FaceEncoder.normalize_embedding(b)
        if va is None or vb is None or va.shape != vb.shape:
            return -1.0
        return float(np.dot(va, vb))

    def _match_thresholds(self) -> tuple[float, float]:
        if USE_LIGHT_ML or not ENCODER_WEIGHTS.exists():
            return FACE_MATCH_THRESHOLD_LIGHT, FACE_MATCH_MARGIN_LIGHT
        return FACE_MATCH_THRESHOLD, FACE_MATCH_MARGIN

    def verify_thresholds(self) -> tuple[float, float]:
        if USE_LIGHT_ML or not ENCODER_WEIGHTS.exists():
            return FACE_VERIFY_THRESHOLD_LIGHT, FACE_VERIFY_AVG_THRESHOLD_LIGHT
        return FACE_VERIFY_THRESHOLD, FACE_VERIFY_AVG_THRESHOLD

    def duplicate_threshold(self) -> float:
        if USE_LIGHT_ML or not ENCODER_WEIGHTS.exists():
            return FACE_DUPLICATE_THRESHOLD_LIGHT
        return FACE_DUPLICATE_THRESHOLD

    def _login_embeddings(self, image_bgr: np.ndarray) -> list[np.ndarray]:
        """로그인: 원본 + 좌우반전 중 더 나은 매칭."""
        out: list[np.ndarray] = []
        for img in (image_bgr, cv2.flip(image_bgr, 1)):
            emb = self.encode(img, allow_center_fallback=True)
            if emb is not None:
                out.append(emb)
        return out

    def verify_user(
        self, image_bgr: np.ndarray, stored_embedding: np.ndarray
    ) -> tuple[bool, float]:
        currents = self._login_embeddings(image_bgr)
        if not currents:
            return False, 0.0

        stored = self.normalize_embedding(stored_embedding)
        expected = self.expected_embedding_dim()
        if stored is None or stored.size != expected:
            raise ValueError("stored_embeddings_incompatible")

        scores = [
            self.cosine_similarity(cur, stored)
            for cur in currents
        ]
        scores = [score for score in scores if score >= 0]
        if not scores:
            return False, 0.0

        best_score = max(scores)
        avg_score = float(sum(scores) / len(scores))
        best_threshold, avg_threshold = self.verify_thresholds()
        if best_score >= best_threshold and (len(scores) == 1 or avg_score >= avg_threshold):
            return True, best_score

        logger.info(
            "얼굴 1:1 검증 거부: best=%.3f avg=%.3f (need %.2f / %.2f)",
            best_score,
            avg_score,
            best_threshold,
            avg_threshold,
        )
        return False, best_score

    def match_user(
        self, image_bgr: np.ndarray, stored_embeddings: dict[str, np.ndarray]
    ) -> tuple[str | None, float]:
        currents = self._login_embeddings(image_bgr)
        if not currents:
            return None, 0.0

        expected = self.expected_embedding_dim()
        threshold, margin = self._match_thresholds()
        scores: list[tuple[str, float]] = []
        skipped = 0
        for username, embedding in stored_embeddings.items():
            stored = self.normalize_embedding(embedding)
            if stored is None or stored.size != expected:
                skipped += 1
                logger.warning(
                    "얼굴 DB 형식 불일치 (%s): dim=%s expected=%s",
                    username,
                    getattr(stored, "size", None),
                    expected,
                )
                continue
            best = max(self.cosine_similarity(cur, stored) for cur in currents)
            if best < 0:
                continue
            scores.append((username, best))

        if skipped and not scores:
            raise ValueError("stored_embeddings_incompatible")

        if not scores:
            return None, 0.0

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

"""웹캠 표정 추론 보정 — FER2013 학습 모델 + 실시간 카메라 도메인 차이 완화."""

from __future__ import annotations

import cv2
import numpy as np

from config import EMOTION_LABELS, EMOTION_IMG_SIZE

NEGATIVE_EMOTIONS = frozenset({"angry", "sad", "disgust", "fear"})


def prepare_face_gray(face_gray: np.ndarray) -> np.ndarray:
    """FER2013과 비슷하게 48x48 그레이 + 히스토그램 평활화."""
    if face_gray.shape != EMOTION_IMG_SIZE:
        face_gray = cv2.resize(face_gray, EMOTION_IMG_SIZE)
    gray = face_gray.astype(np.uint8)
    return cv2.equalizeHist(gray)


def sharpen_distribution(dist: dict[str, float], temperature: float = 0.62) -> dict[str, float]:
    """확률을 날카롭게 — 평온/기쁨으로만 뭉개지는 현상 완화."""
    if not dist:
        return dist
    powered = {k: float(v) ** (1.0 / temperature) for k, v in dist.items()}
    total = sum(powered.values()) or 1.0
    return {k: v / total for k, v in powered.items()}


def pick_dominant_emotion(dist: dict[str, float]) -> tuple[str, float]:
    """상위 감정 선택. 기쁨·평온만 과하게 나올 때 분노·슬픔 후보 반영."""
    if not dist:
        return "neutral", 0.0

    ranked = sorted(dist.items(), key=lambda x: -x[1])
    top, top_p = ranked[0]
    if top not in ("happy", "neutral") or top_p >= 0.58:
        return top, top_p

    neg_best = max((dist.get(e, 0.0) for e in NEGATIVE_EMOTIONS), default=0.0)
    neg_label = max(NEGATIVE_EMOTIONS, key=lambda e: dist.get(e, 0.0))

    # ML이 부정 감정에 어느 정도 확신이면 기쁨/평온 대신 채택
    if neg_best >= 0.16 and neg_best >= top_p * 0.72:
        return neg_label, neg_best

    if top == "neutral" and dist.get("happy", 0) > 0.12:
        happy_p = dist["happy"]
        if happy_p > top_p * 0.9 and top_p < 0.45:
            return "happy", happy_p

    return top, top_p

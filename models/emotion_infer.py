"""웹캠 표정 추론 보정 — FER2013 학습 모델 + 실시간 카메라 도메인 차이 완화."""

from __future__ import annotations

import cv2
import numpy as np

from config import EMOTION_IMG_SIZE

CORE_EMOTIONS = ("happy", "neutral", "sad", "angry")


def prepare_face_gray(face_gray: np.ndarray) -> np.ndarray:
    """FER2013과 비슷하게 48x48 그레이 + 히스토그램 평활화."""
    if face_gray.shape != EMOTION_IMG_SIZE:
        face_gray = cv2.resize(face_gray, EMOTION_IMG_SIZE)
    gray = face_gray.astype(np.uint8)
    return cv2.equalizeHist(gray)


def angry_cue_strength(face_gray: np.ndarray) -> float:
    """분노 기하 힌트 0~1 — 확실할 때만 분노 보정에 사용."""
    face = prepare_face_gray(face_gray)
    h, w = face.shape
    eye = face[: h // 3, :]
    brow = face[h // 5 : h // 3, :]
    upper = face[: h // 2, :]
    mouth = face[int(h * 0.58) :, :]

    brow_tension = max(0.0, (float(np.mean(eye)) - float(np.mean(brow))) / 28.0)
    upper_contrast = max(0.0, (float(np.std(upper)) - 22.0) / 24.0)

    mouth_mid = mouth[:, w // 4 : 3 * w // 4]
    mouth_corner = np.concatenate([mouth[:, : w // 5], mouth[:, -w // 5 :]], axis=1)
    frown = 0.0
    if mouth_mid.size and mouth_corner.size:
        frown = max(0.0, (float(np.mean(mouth_corner)) - float(np.mean(mouth_mid))) / 20.0)

    raw = 0.4 * brow_tension + 0.35 * upper_contrast + 0.25 * frown
    return float(np.clip(raw, 0.0, 1.0))


def soften_angry_bias(dist: dict[str, float], face_gray: np.ndarray | None) -> dict[str, float]:
    """분노만 과하게 나올 때 완화 — 눈썹 신호가 약하면 기쁨·평온·슬픔 쪽으로."""
    if not dist or face_gray is None:
        return dist

    angry_p = dist.get("angry", 0.0)
    cue = angry_cue_strength(face_gray)
    if angry_p < 0.28 or cue >= 0.48:
        return dist

    out = dict(dist)
    factor = 0.55 + 0.45 * cue
    out["angry"] = angry_p * factor
    bonus = (angry_p - out["angry"]) / 3.0
    for key in ("happy", "neutral", "sad"):
        out[key] = out.get(key, 0.0) + bonus

    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def sharpen_distribution(dist: dict[str, float], temperature: float = 0.78) -> dict[str, float]:
    """확률을 약하게 날카롭게 — 한 감정으로만 쏠리지 않게."""
    if not dist:
        return dist
    powered = {k: float(v) ** (1.0 / temperature) for k, v in dist.items()}
    total = sum(powered.values()) or 1.0
    return {k: v / total for k, v in powered.items()}


def pick_dominant_emotion(
    dist: dict[str, float],
    face_gray: np.ndarray | None = None,
) -> tuple[str, float]:
    """ML 분포를 기본으로, 분노 과다·기쁨/평온 과다만 가볍게 조정."""
    if not dist:
        return "neutral", 0.0

    dist = soften_angry_bias(dist, face_gray)
    ranked = sorted(dist.items(), key=lambda x: -x[1])
    top, top_p = ranked[0]
    second_p = ranked[1][1] if len(ranked) > 1 else 0.0

    if top == "angry" and face_gray is not None:
        cue = angry_cue_strength(face_gray)
        if cue < 0.38 and top_p < 0.45:
            for alt in ("neutral", "happy", "sad"):
                if dist.get(alt, 0) >= top_p * 0.88:
                    return alt, dist[alt]

    if top in ("happy", "neutral") and top_p < 0.42 and (top_p - second_p) < 0.08:
        for alt in CORE_EMOTIONS:
            if alt != top and dist.get(alt, 0) >= second_p:
                return alt, dist[alt]

    return top, top_p

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


def angry_cue_strength(face_gray: np.ndarray) -> float:
    """
    분노 표정 기하 힌트: 눈썹·이마 대비, 상안면 대비, 입꼬 내림.
    웹캠 밝기와 무관하게 0~1 점수.
    """
    face = prepare_face_gray(face_gray)
    h, w = face.shape
    eye = face[: h // 3, :]
    brow = face[h // 5 : h // 3, :]
    upper = face[: h // 2, :]
    mouth = face[int(h * 0.58) :, :]

    eye_m = float(np.mean(eye))
    brow_m = float(np.mean(brow))
    brow_tension = max(0.0, (eye_m - brow_m) / 28.0)
    upper_contrast = max(0.0, (float(np.std(upper)) - 20.0) / 22.0)

    mouth_mid = mouth[:, w // 4 : 3 * w // 4]
    mouth_corner = np.concatenate([mouth[:, : w // 5], mouth[:, -w // 5 :]], axis=1)
    frown = 0.0
    if mouth_mid.size and mouth_corner.size:
        frown = max(0.0, (float(np.mean(mouth_corner)) - float(np.mean(mouth_mid))) / 18.0)

    edges = cv2.Canny(face, 45, 110)
    edge_upper = float(np.sum(edges[: h // 2])) / max(1, edges[: h // 2].size)
    edge_score = min(1.0, edge_upper * 5.0)

    raw = 0.32 * brow_tension + 0.28 * upper_contrast + 0.22 * frown + 0.18 * edge_score
    return float(np.clip(raw, 0.0, 1.0))


def apply_angry_boost(dist: dict[str, float], face_gray: np.ndarray) -> dict[str, float]:
    """ML이 분노를 낮게 줄 때 기하 힌트로 angry 확률 상향."""
    if not dist:
        return dist
    strength = angry_cue_strength(face_gray)
    if strength < 0.22:
        return dist

    out = dict(dist)
    angry = out.get("angry", 0.0)
    add = (0.06 + 0.28 * strength) * (1.0 - angry)
    out["angry"] = angry + add
    damp = 0.12 + 0.2 * strength
    for key in ("happy", "neutral"):
        if key in out:
            out[key] *= max(0.0, 1.0 - damp)

    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def sharpen_distribution(dist: dict[str, float], temperature: float = 0.62) -> dict[str, float]:
    """확률을 날카롭게 — 평온/기쁨으로만 뭉개지는 현상 완화."""
    if not dist:
        return dist
    powered = {k: float(v) ** (1.0 / temperature) for k, v in dist.items()}
    total = sum(powered.values()) or 1.0
    return {k: v / total for k, v in powered.items()}


def pick_dominant_emotion(
    dist: dict[str, float],
    face_gray: np.ndarray | None = None,
) -> tuple[str, float]:
    """상위 감정 선택. 기쁨·평온 편향 시 분노·슬픔 후보 반영."""
    if not dist:
        return "neutral", 0.0

    if face_gray is not None:
        dist = apply_angry_boost(dist, face_gray)

    ranked = sorted(dist.items(), key=lambda x: -x[1])
    top, top_p = ranked[0]
    angry_p = dist.get("angry", 0.0)
    cue = angry_cue_strength(face_gray) if face_gray is not None else 0.0

    # 분노: ML 2위여도 눈썹·찌푸림 신호가 강하면 우선
    if face_gray is not None and cue >= 0.30:
        if angry_p >= 0.10 and top in ("happy", "neutral"):
            if angry_p >= top_p * 0.50 or (len(ranked) > 1 and ranked[1][0] == "angry"):
                return "angry", angry_p
        if top == "angry":
            return top, top_p

    if top not in ("happy", "neutral") or top_p >= 0.58:
        return top, top_p

    neg_best = max((dist.get(e, 0.0) for e in NEGATIVE_EMOTIONS), default=0.0)
    neg_label = max(NEGATIVE_EMOTIONS, key=lambda e: dist.get(e, 0.0))

    angry_min = 0.11 if cue >= 0.28 else 0.16
    if neg_label == "angry" and angry_p >= angry_min and angry_p >= top_p * 0.62:
        return "angry", angry_p

    if neg_best >= 0.16 and neg_best >= top_p * 0.72:
        return neg_label, neg_best

    if top == "neutral" and dist.get("happy", 0) > 0.12:
        happy_p = dist["happy"]
        if happy_p > top_p * 0.9 and top_p < 0.45:
            return "happy", happy_p

    return top, top_p

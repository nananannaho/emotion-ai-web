"""감정 분석 + 멀티모달 융합 오케스트레이션."""

from __future__ import annotations

import base64
import logging
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

from config import EMOTION_LABELS_KO
from models.emotion_cnn import EmotionCNN
from models.fusion import FusionInput, MultiModalFusion
from services.auth_service import AuthService

logger = logging.getLogger(__name__)


class EmotionService:
    def __init__(self):
        self.cnn = EmotionCNN()
        self.fusion = MultiModalFusion()
        self.auth = AuthService()

    @staticmethod
    def decode_image(data_url_or_b64: str) -> np.ndarray | None:
        try:
            if "," in data_url_or_b64:
                data_url_or_b64 = data_url_or_b64.split(",", 1)[1]
            raw = base64.b64decode(data_url_or_b64)
            img = Image.open(BytesIO(raw)).convert("RGB")
            arr = np.array(img)
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            logger.exception("이미지 디코딩 실패: %s", exc)
            return None

    def analyze_frame(self, image_bgr, username: str | None = None, message: str = "") -> dict:
        emotion_result = self.cnn.predict(image_bgr)
        if not emotion_result.get("success"):
            return emotion_result

        profile = None
        if username:
            profile = self.auth.get_profile(username)

        fusion_input = FusionInput(
            visual_emotion=emotion_result["emotion"],
            visual_confidence=emotion_result["confidence"],
            visual_distribution=emotion_result["distribution"],
            text_message=message,
            user_mood_history=profile.get("mood_history", []) if profile else [],
            user_preferences=profile.get("preferences", {}) if profile else {},
        )
        fused = self.fusion.fuse(fusion_input)

        if username:
            self.auth.update_mood_history(username, fused["fused_emotion"])

        return {
            "success": True,
            "visual": {
                "emotion": emotion_result["emotion"],
                "emotion_ko": EMOTION_LABELS_KO.get(emotion_result["emotion"], ""),
                "confidence": emotion_result["confidence"],
                "distribution": emotion_result["distribution"],
                "face_box": emotion_result.get("face_box"),
            },
            "fusion": fused,
        }

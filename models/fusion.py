"""멀티모달 결합: 시각(얼굴 감정) + 텍스트 + 사용자 프로필 → 상황 판단."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import EMOTION_LABELS_KO


@dataclass
class FusionInput:
    visual_emotion: str
    visual_confidence: float
    visual_distribution: dict[str, float]
    text_message: str = ""
    text_sentiment: str = "neutral"
    user_mood_history: list[str] = field(default_factory=list)
    user_preferences: dict = field(default_factory=dict)
    session_context: str = ""


class MultiModalFusion:
    """
    가중 융합 알고리즘
    - 시각 모달 (CNN 감정): 0.45
    - 텍스트 모달 (키워드 감성): 0.30
    - 사용자 이력·선호: 0.25
    """

    WEIGHTS = {"visual": 0.45, "text": 0.30, "profile": 0.25}

    TEXT_POSITIVE = ("좋", "행복", "기쁘", "감사", "최고", "사랑", "웃", "즐거", "희망")
    TEXT_NEGATIVE = ("슬프", "우울", "힘들", "짜증", "화", "무서", "불안", "싫", "외로", "지쳐")
    TEXT_ANXIOUS = ("걱정", "불안", "무서", "두려", "긴장")

    SITUATION_MAP = {
        ("happy", "positive"): "celebration",
        ("happy", "neutral"): "casual_positive",
        ("sad", "negative"): "comfort_needed",
        ("sad", "neutral"): "gentle_support",
        ("angry", "negative"): "de_escalation",
        ("fear", "anxious"): "reassurance",
        ("neutral", "neutral"): "neutral_chat",
        ("surprise", "positive"): "excited_chat",
    }

    def analyze_text(self, message: str) -> tuple[str, dict[str, float]]:
        if not message.strip():
            return "neutral", {"neutral": 1.0}

        msg = message.lower()
        scores = {
            "happy": sum(1 for w in self.TEXT_POSITIVE if w in msg),
            "sad": sum(1 for w in self.TEXT_NEGATIVE if w in msg),
            "fear": sum(1 for w in self.TEXT_ANXIOUS if w in msg),
            "angry": 1 if any(w in msg for w in ("화", "짜증", "열받")) else 0,
            "neutral": 0.5,
        }
        total = sum(scores.values()) or 1
        dist = {k: v / total for k, v in scores.items()}
        dominant = max(dist, key=dist.get)
        if scores["fear"] > 0:
            return "anxious", dist
        return dominant, dist

    def _profile_emotion_bias(self, history: list[str], preferences: dict) -> dict[str, float]:
        bias = {e: 0.0 for e in ("angry", "disgust", "fear", "happy", "sad", "surprise", "neutral")}
        for mood in history[-5:]:
            if mood in bias:
                bias[mood] += 0.2
        preferred = preferences.get("preferred_tone", "neutral")
        if preferred in bias:
            bias[preferred] += 0.3
        total = sum(bias.values()) or 1
        return {k: v / total for k, v in bias.items()}

    def fuse(self, data: FusionInput) -> dict:
        text_emotion, text_dist = self.analyze_text(data.text_message)
        profile_dist = self._profile_emotion_bias(
            data.user_mood_history, data.user_preferences
        )

        visual_dist = data.visual_distribution or {data.visual_emotion: data.visual_confidence}
        all_emotions = set(visual_dist) | set(text_dist) | set(profile_dist)

        fused = {}
        for emo in all_emotions:
            fused[emo] = (
                self.WEIGHTS["visual"] * visual_dist.get(emo, 0)
                + self.WEIGHTS["text"] * text_dist.get(emo, 0)
                + self.WEIGHTS["profile"] * profile_dist.get(emo, 0)
            )

        total = sum(fused.values()) or 1
        fused = {k: v / total for k, v in fused.items()}
        final_emotion = max(fused, key=fused.get)
        confidence = fused[final_emotion]

        situation_key = (data.visual_emotion, text_emotion)
        situation = self.SITUATION_MAP.get(
            situation_key,
            self.SITUATION_MAP.get((final_emotion, "neutral"), "general_support"),
        )

        return {
            "fused_emotion": final_emotion,
            "fused_emotion_ko": EMOTION_LABELS_KO.get(final_emotion, final_emotion),
            "confidence": round(confidence, 4),
            "distribution": {k: round(v, 4) for k, v in fused.items()},
            "modal_breakdown": {
                "visual": data.visual_emotion,
                "text": text_emotion,
                "visual_confidence": data.visual_confidence,
            },
            "situation": situation,
            "session_context": data.session_context or situation,
        }

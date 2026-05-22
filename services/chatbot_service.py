"""감정·상황 맞춤형 챗봇 — API 없는 자체 엔진."""

from __future__ import annotations

from config import EMOTION_LABELS_KO
from services.local_chatbot import LocalChatEngine


class ChatbotService:
    def __init__(self):
        self._engine = LocalChatEngine()

    def generate(
        self,
        user_message: str,
        fused_emotion: str,
        situation: str,
        display_name: str = "친구",
        chat_history: list[dict] | None = None,
    ) -> dict:
        emotion_ko = EMOTION_LABELS_KO.get(fused_emotion, fused_emotion)
        return self._engine.generate(
            user_message=user_message,
            fused_emotion=fused_emotion,
            situation=situation,
            emotion_ko=emotion_ko,
            display_name=display_name,
            chat_history=chat_history,
        )

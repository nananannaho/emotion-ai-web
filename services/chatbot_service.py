"""감정·상황 맞춤형 챗봇 — Gemini(키 설정 시) 또는 자체 로컬 엔진."""

from __future__ import annotations

from config import CHATBOT_AVATAR, EMOTION_EMOJI, EMOTION_LABELS_KO, GEMINI_API_KEY
from services.gemini_chatbot import GeminiChatEngine
from services.local_chatbot import LocalChatEngine


class ChatbotService:
    def __init__(self):
        self._local = LocalChatEngine()
        self._gemini = GeminiChatEngine() if GEMINI_API_KEY else None

    def generate(
        self,
        user_message: str,
        fused_emotion: str,
        situation: str,
        display_name: str = "친구",
        chat_history: list[dict] | None = None,
    ) -> dict:
        emotion_ko = EMOTION_LABELS_KO.get(fused_emotion, fused_emotion)

        if self._gemini is not None:
            gemini_result = self._gemini.generate(
                user_message=user_message,
                fused_emotion=fused_emotion,
                situation=situation,
                emotion_ko=emotion_ko,
                display_name=display_name,
                chat_history=chat_history,
            )
            if gemini_result:
                gemini_result.setdefault("emotion_emoji", EMOTION_EMOJI.get(fused_emotion, "💬"))
                gemini_result.setdefault("bot_avatar", CHATBOT_AVATAR)
                return gemini_result

        result = self._local.generate(
            user_message=user_message,
            fused_emotion=fused_emotion,
            situation=situation,
            emotion_ko=emotion_ko,
            display_name=display_name,
            chat_history=chat_history,
        )
        result.setdefault("emotion_emoji", EMOTION_EMOJI.get(fused_emotion, "💬"))
        result.setdefault("bot_avatar", CHATBOT_AVATAR)
        return result

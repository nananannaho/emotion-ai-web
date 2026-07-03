"""Google Gemini API 기반 챗봇 (키 없거나 오류 시 상위에서 로컬 엔진으로 fallback)."""

from __future__ import annotations

from config import (
    CHATBOT_AVATAR,
    EMOTION_EMOJI,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SECONDS,
)

SITUATION_HINTS_KO: dict[str, str] = {
    "celebration": "기쁜 일을 함께 나누는 분위기",
    "casual_positive": "가볍고 밝은 대화",
    "comfort_needed": "위로와 공감이 필요한 상황",
    "gentle_support": "부드럽게 돕는 상황",
    "de_escalation": "화나거나 답답한 감정을 가라앉히는 상황",
    "reassurance": "불안과 걱정을 덜어주는 상황",
    "neutral_chat": "차분한 일상 대화",
    "excited_chat": "설레거나 신나는 대화",
    "general_support": "일반적인 정서 지원",
}


class GeminiChatEngine:
    MAX_HISTORY_TURNS = 10

    def __init__(self) -> None:
        self.available = bool(GEMINI_API_KEY)

    def _system_instruction(
        self,
        *,
        fused_emotion: str,
        emotion_ko: str,
        situation: str,
        display_name: str,
    ) -> str:
        situation_hint = SITUATION_HINTS_KO.get(situation, situation)
        emoji = EMOTION_EMOJI.get(fused_emotion, "💬")
        return f"""당신은 Felunai의 감정 맞춤 대화 도우미입니다.

역할:
- 사용자의 표정·텍스트로 추정된 현재 감정({emotion_ko}, 코드: {fused_emotion})과 상황({situation_hint})을 반영해 한국어로 답합니다.
- 상담사처럼 차분하고 성숙한 톤을 유지하되, 따뜻하고 구체적으로 말합니다.
- 의학·법률·위기 상담이 아닌 일상 정서 지원 범위에서 답합니다. 자해·타해 위험이 보이면 전문 기관(1393, 119 등) 안내를 짧게 권합니다.

스타일:
- 2~5문장, 불필요한 목록·장문 금지.
- 답변 맨 앞에 감정 이모티콘 {emoji} 하나만 자연스럽게 붙일 수 있습니다.
- 사용자를 "{display_name}님"으로 부를 수 있습니다.
- 표정 분석 결과를 억지로 반복하지 말고, 대화 맥락에 맞게 한 번 정도만 언급합니다.
- 질문이 있으면 마지막에 부드럽게 한 가지만 되물어도 됩니다."""

    def _format_history(self, chat_history: list[dict] | None) -> list[dict]:
        if not chat_history:
            return []
        rows = chat_history[-(self.MAX_HISTORY_TURNS * 2) :]
        formatted: list[dict] = []
        for item in rows:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                formatted.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                formatted.append({"role": "model", "parts": [content]})
        return formatted

    def generate(
        self,
        user_message: str,
        fused_emotion: str,
        situation: str,
        emotion_ko: str,
        display_name: str = "친구",
        chat_history: list[dict] | None = None,
    ) -> dict | None:
        if not self.available:
            return None

        message = (user_message or "").strip()
        if not message:
            message = "지금 말하기 어려운데, 옆에서 같이 있어 줘."

        try:
            import google.generativeai as genai
        except ImportError:
            return None

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                system_instruction=self._system_instruction(
                    fused_emotion=fused_emotion,
                    emotion_ko=emotion_ko,
                    situation=situation,
                    display_name=display_name,
                ),
                generation_config={
                    "temperature": 0.75,
                    "max_output_tokens": 512,
                },
            )
            request_options = {"timeout": GEMINI_TIMEOUT_SECONDS}
            history = self._format_history(chat_history)

            if history:
                chat = model.start_chat(history=history)
                response = chat.send_message(message, request_options=request_options)
            else:
                response = model.generate_content(
                    message,
                    request_options=request_options,
                )

            reply = (getattr(response, "text", None) or "").strip()
            if not reply:
                return None

            return {
                "reply": reply,
                "emotion": fused_emotion,
                "emotion_ko": emotion_ko,
                "emotion_emoji": EMOTION_EMOJI.get(fused_emotion, "💬"),
                "bot_avatar": CHATBOT_AVATAR,
                "situation": situation,
                "engine": "gemini",
                "model": GEMINI_MODEL,
            }
        except Exception:
            return None

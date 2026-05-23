"""
API 없이 동작하는 자체 챗봇 엔진.

- 의도(Intent) 분류: 키워드·패턴 기반
- 응답 선택: 감정 + 상황 + 의도 + 사용자 메시지 키워드 점수화
- 맥락: 최근 대화 이력 반영
- 생성: 고정 문장 조합 + 사용자 발화 일부 반영 (템플릿 합성)

※ ChatGPT 같은 대규모 언어모델(LLM)은 아니며, 서버 안에서만 돌아가는
  '지능형 규칙·검색 기반' 대화 엔진입니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ResponseCandidate:
    text: str
    intents: list[str] = field(default_factory=list)
    emotions: list[str] = field(default_factory=list)
    situations: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class LocalChatEngine:
    INTENT_KEYWORDS: dict[str, list[str]] = {
        "greeting": ["안녕", "하이", "헬로", "반가", "처음"],
        "thanks": ["고마", "감사", "thank"],
        "goodbye": ["잘가", "bye", "나중", "종료", "끝"],
        "study": ["공부", "시험", "수능", "학교", "숙제", "과제", "성적"],
        "friend": ["친구", "우정", "절친", "사이"],
        "family": ["부모", "엄마", "아빠", "가족", "형", "누나", "동생"],
        "love": ["좋아", "사랑", "연애", "짝사", "고백"],
        "stress": ["스트레스", "힘들", "지쳐", "버거", "우울", "답답"],
        "worry": ["걱정", "불안", "무서", "두려", "긴장"],
        "happy_share": ["기쁘", "좋았", "행복", "신나", "재밌", "최고"],
        "sad_share": ["슬프", "울었", "눈물", "서럽", "외로"],
        "angry_share": ["화나", "짜증", "열받", "억울"],
        "ask_advice": ["어떻게", "조언", "방법", "도와", "추천", "뭐가 좋"],
        "ask_why": ["왜", "이유"],
        "lonely": ["외로", "혼자", "쓸쓸"],
        "tired": ["피곤", "졸려", "잠"],
    }

    EMOTION_HINTS: dict[str, list[str]] = {
        "happy": ["기쁨", "행복", "웃"],
        "sad": ["슬픔", "우울", "눈물"],
        "angry": ["화", "분노", "짜증"],
        "fear": ["불안", "걱정", "무서움"],
        "neutral": ["보통", "그냥", "평범"],
    }

    CANDIDATES: list[ResponseCandidate] = [
        ResponseCandidate(
            "안녕하세요! 저는 감정을 읽고 맞춤 대화를 도와주는 EmotionAI예요. 오늘 무슨 일이 있었나요?",
            intents=["greeting"],
            emotions=["neutral", "happy"],
        ),
        ResponseCandidate(
            "반가워요. 편한 말투로 아무거나 말해 주세요. 표정으로 읽은 기분도 함께 반영할게요.",
            intents=["greeting"],
            emotions=["happy", "neutral"],
        ),
        ResponseCandidate(
            "천만해요. 도움이 됐다면 다행이에요. 더 나누고 싶은 이야기가 있으면 이어서 말해 주세요.",
            intents=["thanks"],
            emotions=["happy", "neutral"],
        ),
        ResponseCandidate(
            "공부 때문에 많이 지치셨군요. 잠깐 쉬고, 작은 목표 하나만 정해 보면 부담이 줄어요. 지금 가장 막히는 과목이 뭐예요?",
            intents=["study", "stress", "ask_advice"],
            emotions=["sad", "fear", "neutral"],
            keywords=["공부", "시험", "학교"],
        ),
        ResponseCandidate(
            "시험이 걱정되시는 것 같아요. ‘완벽’보다 ‘오늘 할 수 있는 분량’만 정해 보는 건 어떨까요?",
            intents=["study", "worry"],
            emotions=["fear", "sad"],
            situations=["reassurance"],
        ),
        ResponseCandidate(
            "친구 관계가 마음에 걸리시네요. 상대 입장과 내 입장을 나눠 적어 보면 감정이 정리될 때가 많아요. 어떤 일이 있었는지 더 말해줄 수 있어요?",
            intents=["friend", "ask_advice"],
            emotions=["sad", "angry", "neutral"],
            keywords=["친구"],
        ),
        ResponseCandidate(
            "가족 때문에 힘드셨군요. 가까운 사이일수록 감정이 크게 느껴져요. 지금 가장 서운했던 순간이 언제였나요?",
            intents=["family", "sad_share", "stress"],
            emotions=["sad", "angry"],
            keywords=["가족", "부모", "엄마", "아빠"],
        ),
        ResponseCandidate(
            "좋아하는 마음이 생겼군요. 설레면서도 불안할 수 있어요. 상대와의 관계에서 가장 궁금한 점이 뭐예요?",
            intents=["love", "happy_share"],
            emotions=["happy", "fear", "surprise"],
            keywords=["좋아", "사랑"],
        ),
        ResponseCandidate(
            "많이 지치셨네요. 오늘은 ‘해야 할 일’ 목록에서 하나만 줄여도 괜찮아요. 잠은 좀 주무셨어요?",
            intents=["tired", "stress"],
            emotions=["sad", "neutral"],
            situations=["gentle_support", "comfort_needed"],
        ),
        ResponseCandidate(
            "외로움을 느끼고 계시는군요. 그 감정은 자연스러워요. 지금 옆에 있는 사람·편한 취미 중 하나라도 떠올려 볼까요?",
            intents=["lonely", "sad_share"],
            emotions=["sad", "fear"],
            situations=["comfort_needed"],
            keywords=["외로", "혼자"],
        ),
        ResponseCandidate(
            "화가 나는 일이 있었군요. 지금은 감정을 인정하는 게 먼저예요. ‘무엇이 불공평했다’고 느꼈는지 한 문장으로 말해줄 수 있어요?",
            intents=["angry_share", "stress"],
            emotions=["angry"],
            situations=["de_escalation"],
        ),
        ResponseCandidate(
            "걱정이 크시네요. 걱정을 ‘할 수 있는 일’과 ‘통제 밖’으로 나눠 보면 마음이 가벼워질 때가 있어요. 지금 가장 걱정되는 게 뭐예요?",
            intents=["worry", "ask_advice"],
            emotions=["fear", "sad"],
            situations=["reassurance"],
        ),
        ResponseCandidate(
            "좋은 일이 있었군요! 그 기분을 조금만 더 자세히 들려주세요. 무엇이 가장 기뻤어요?",
            intents=["happy_share"],
            emotions=["happy", "surprise"],
            situations=["celebration", "excited_chat"],
        ),
        ResponseCandidate(
            "슬픈 일이 있었군요. 괜찮아요, 천천히 말해도 돼요. 혼자 감당하지 않아도 됩니다.",
            intents=["sad_share"],
            emotions=["sad"],
            situations=["comfort_needed", "gentle_support"],
        ),
        ResponseCandidate(
            "‘{topic}’에 대해 말해 주셔서 고마워요. 제가 읽은 표정상으로는 지금 {emotion_ko} 기분에 가깝고, 그 마음을 존중하면서 이야기할게요.",
            intents=["general"],
            emotions=["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"],
        ),
        ResponseCandidate(
            "왜 그런지 궁금하시군요. 이유는 하나가 아닐 때가 많아요. 상황·사람·내 기대 중 어디가 가장 크게 느껴지나요?",
            intents=["ask_why"],
            emotions=["neutral", "sad", "angry"],
        ),
        ResponseCandidate(
            "지금은 조용히 들을게요. 말하고 싶을 때 이어서 적어 주세요.",
            intents=["general"],
            emotions=["sad", "neutral"],
            situations=["gentle_support"],
        ),
        ResponseCandidate(
            "오늘 대화 잘 나눴어요. 또 언제든 찾아와 주세요. 좋은 하루 보내요!",
            intents=["goodbye"],
            emotions=["happy", "neutral"],
        ),
    ]

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def detect_intents(self, message: str) -> list[str]:
        msg = self._normalize(message)
        found = []
        for intent, words in self.INTENT_KEYWORDS.items():
            if any(w in msg for w in words):
                found.append(intent)
        if not found:
            found.append("general")
        return found

    def extract_topic_snippet(self, message: str, max_len: int = 24) -> str:
        msg = message.strip()
        if not msg:
            return "이야기"
        if len(msg) <= max_len:
            return msg
        return msg[: max_len - 1] + "…"

    def score_candidate(
        self,
        cand: ResponseCandidate,
        intents: list[str],
        fused_emotion: str,
        situation: str,
        message: str,
        recent_bot_replies: list[str],
    ) -> float:
        score = 0.0
        msg = self._normalize(message)

        for intent in intents:
            if intent in cand.intents or "general" in cand.intents:
                score += 3.0 if intent in cand.intents else 0.5

        if fused_emotion in cand.emotions:
            score += 2.5
        elif "neutral" in cand.emotions:
            score += 0.8

        if situation in cand.situations:
            score += 2.0

        for kw in cand.keywords:
            if kw in msg:
                score += 1.5

        if cand.text in recent_bot_replies:
            score -= 5.0

        return score

    def pick_response(
        self,
        user_message: str,
        fused_emotion: str,
        situation: str,
        emotion_ko: str,
        display_name: str,
        recent_bot_replies: list[str] | None = None,
    ) -> tuple[str, str]:
        recent = recent_bot_replies or []
        intents = self.detect_intents(user_message)
        topic = self.extract_topic_snippet(user_message)

        best: ResponseCandidate | None = None
        best_score = -1.0

        for cand in self.CANDIDATES:
            s = self.score_candidate(
                cand, intents, fused_emotion, situation, user_message, recent
            )
            if s > best_score:
                best_score = s
                best = cand

        if best is None:
            best = self.CANDIDATES[-2]

        try:
            text = best.text.format(topic=topic, emotion_ko=emotion_ko)
        except (KeyError, ValueError):
            text = best.text.replace("{topic}", topic).replace("{emotion_ko}", emotion_ko)

        if display_name and not text.startswith(display_name):
            prefix = f"{display_name}님, "
            if intents == ["greeting"]:
                text = f"{prefix}{text}"
            elif user_message.strip() and "general" not in best.intents[:1]:
                text = f"{prefix}{text}"

        detected = ", ".join(intents[:3])
        return text, detected

    def generate(
        self,
        user_message: str,
        fused_emotion: str,
        situation: str,
        emotion_ko: str,
        display_name: str = "친구",
        chat_history: list[dict] | None = None,
    ) -> dict:
        recent_bot = []
        if chat_history:
            for item in chat_history[-6:]:
                if item.get("role") == "assistant":
                    recent_bot.append(item.get("content", ""))

        reply, intent = self.pick_response(
            user_message=user_message,
            fused_emotion=fused_emotion,
            situation=situation,
            emotion_ko=emotion_ko,
            display_name=display_name,
            recent_bot_replies=recent_bot,
        )

        return {
            "reply": reply,
            "emotion": fused_emotion,
            "emotion_ko": emotion_ko,
            "situation": situation,
            "engine": "local",
            "detected_intent": intent,
        }

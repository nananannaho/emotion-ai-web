"""회원가입·얼굴 로그인·세션 관리 (DB 영구 저장)."""

from __future__ import annotations

import json
import logging

from werkzeug.security import check_password_hash, generate_password_hash

from models.face_encoder import FaceEncoder
from services.database import get_db

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.encoder = FaceEncoder()
        self.db = get_db()

    def user_exists(self, username: str) -> bool:
        return self.db.user_exists(username)

    def register(
        self,
        username: str,
        password: str,
        display_name: str,
        preferences: dict | None,
        face_image_bgr,
    ) -> dict:
        if not username or len(username) < 2:
            return {"success": False, "error": "사용자 이름은 2자 이상이어야 합니다."}
        if self.user_exists(username):
            return {"success": False, "error": "이미 존재하는 사용자입니다."}

        embedding = self.encoder.encode(face_image_bgr)
        if embedding is None:
            return {"success": False, "error": "얼굴을 인식하지 못했습니다. 다시 촬영해 주세요."}

        prefs = preferences or {
            "preferred_tone": "neutral",
            "topics": ["일상", "학교", "취미"],
        }

        self.db.create_user(
            username=username,
            display_name=display_name or username,
            password_hash=generate_password_hash(password),
            preferences=prefs,
            embedding=embedding,
        )
        return {"success": True, "username": username}

    def login_password(self, username: str, password: str) -> dict:
        profile = self.db.get_user_full(username)
        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        if not check_password_hash(profile["password_hash"], password):
            return {"success": False, "error": "비밀번호가 올바르지 않습니다."}
        return {"success": True, "profile": self._public_profile(profile)}

    def login_face(self, face_image_bgr) -> dict:
        embeddings = self.db.get_all_embeddings()
        if not embeddings:
            return {"success": False, "error": "등록된 얼굴 데이터가 없습니다."}

        user, score = self.encoder.match_user(face_image_bgr, embeddings)
        if user is None:
            return {
                "success": False,
                "error": "등록된 얼굴과 일치하지 않습니다.",
                "match_score": round(score, 3),
            }

        profile = self.db.get_user_full(user)
        return {
            "success": True,
            "profile": self._public_profile(profile),
            "match_score": round(score, 3),
        }

    def get_chat_history(self, username: str, limit: int = 20) -> list[dict]:
        profile = self.db.get_user_full(username)
        if not profile:
            return []
        chats = profile["chat_history"]
        if isinstance(chats, str):
            chats = json.loads(chats)
        return chats[-limit:]

    def get_profile(self, username: str) -> dict | None:
        profile = self.db.get_user_full(username)
        if not profile:
            return None
        return self._public_profile(profile)

    def update_mood_history(self, username: str, emotion: str, limit: int = 20):
        self.db.update_mood_history(username, emotion, limit)

    def append_chat(self, username: str, role: str, content: str, limit: int = 50):
        self.db.append_chat(username, role, content, limit)

    @staticmethod
    def _public_profile(profile: dict) -> dict:
        prefs = profile.get("preferences", {})
        moods = profile.get("mood_history", [])
        if isinstance(prefs, str):
            prefs = json.loads(prefs)
        if isinstance(moods, str):
            moods = json.loads(moods)
        return {
            "username": profile["username"],
            "display_name": profile["display_name"],
            "preferences": prefs,
            "mood_history": moods[-10:],
        }

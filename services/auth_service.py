"""회원가입·얼굴 로그인·세션 관리."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from werkzeug.security import check_password_hash, generate_password_hash

from config import FACES_DIR, USERS_DIR
from models.face_encoder import FaceEncoder

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.encoder = FaceEncoder()

    def _user_path(self, username: str) -> Path:
        safe = "".join(c for c in username if c.isalnum() or c in "_-")
        return USERS_DIR / f"{safe}.json"

    def _embedding_path(self, username: str) -> Path:
        safe = "".join(c for c in username if c.isalnum() or c in "_-")
        return FACES_DIR / f"{safe}.npy"

    def user_exists(self, username: str) -> bool:
        return self._user_path(username).exists()

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

        profile = {
            "username": username,
            "display_name": display_name or username,
            "password_hash": generate_password_hash(password),
            "preferences": preferences or {
                "preferred_tone": "neutral",
                "topics": ["일상", "학교", "취미"],
            },
            "mood_history": [],
            "chat_history": [],
        }
        self._user_path(username).write_text(
            json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        np.save(self._embedding_path(username), embedding)
        return {"success": True, "username": username}

    def login_password(self, username: str, password: str) -> dict:
        path = self._user_path(username)
        if not path.exists():
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        profile = json.loads(path.read_text(encoding="utf-8"))
        if not check_password_hash(profile["password_hash"], password):
            return {"success": False, "error": "비밀번호가 올바르지 않습니다."}
        return {"success": True, "profile": self._public_profile(profile)}

    def login_face(self, face_image_bgr) -> dict:
        embeddings = {}
        for npy in FACES_DIR.glob("*.npy"):
            username = npy.stem
            embeddings[username] = np.load(npy)

        if not embeddings:
            return {"success": False, "error": "등록된 얼굴 데이터가 없습니다."}

        user, score = self.encoder.match_user(face_image_bgr, embeddings)
        if user is None:
            return {
                "success": False,
                "error": "등록된 얼굴과 일치하지 않습니다.",
                "match_score": round(score, 3),
            }

        profile = json.loads(self._user_path(user).read_text(encoding="utf-8"))
        return {
            "success": True,
            "profile": self._public_profile(profile),
            "match_score": round(score, 3),
        }

    def get_chat_history(self, username: str, limit: int = 20) -> list[dict]:
        path = self._user_path(username)
        if not path.exists():
            return []
        profile = json.loads(path.read_text(encoding="utf-8"))
        return profile.get("chat_history", [])[-limit:]

    def get_profile(self, username: str) -> dict | None:
        path = self._user_path(username)
        if not path.exists():
            return None
        profile = json.loads(path.read_text(encoding="utf-8"))
        return self._public_profile(profile)

    def update_mood_history(self, username: str, emotion: str, limit: int = 20):
        path = self._user_path(username)
        if not path.exists():
            return
        profile = json.loads(path.read_text(encoding="utf-8"))
        history = profile.get("mood_history", [])
        history.append(emotion)
        profile["mood_history"] = history[-limit:]
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_chat(self, username: str, role: str, content: str, limit: int = 50):
        path = self._user_path(username)
        if not path.exists():
            return
        profile = json.loads(path.read_text(encoding="utf-8"))
        chats = profile.get("chat_history", [])
        chats.append({"role": role, "content": content})
        profile["chat_history"] = chats[-limit:]
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _public_profile(profile: dict) -> dict:
        return {
            "username": profile["username"],
            "display_name": profile["display_name"],
            "preferences": profile.get("preferences", {}),
            "mood_history": profile.get("mood_history", [])[-10:],
        }

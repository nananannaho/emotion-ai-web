"""회원가입·얼굴 로그인·세션 관리 (DB 영구 저장)."""

from __future__ import annotations

import json
import logging

from werkzeug.security import check_password_hash, generate_password_hash

from config import ADMIN_PASSWORD, ADMIN_USERNAME
from models.face_encoder import FaceEncoder
from services.database import get_db
from utils.password_validation import validate_password

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.encoder = FaceEncoder()
        self.db = get_db()

    def user_exists(self, username: str) -> bool:
        return self.db.user_exists(username)

    def _find_face_conflict(
        self,
        embedding,
        *,
        exclude_username: str | None = None,
    ) -> tuple[str, float] | None:
        embeddings = self.db.get_all_embeddings()
        probe = self.encoder.normalize_embedding(embedding)
        if probe is None:
            return None

        threshold = self.encoder.duplicate_threshold()
        for username, stored in embeddings.items():
            if exclude_username and username == exclude_username:
                continue
            score = self.encoder.cosine_similarity(probe, stored)
            if score >= threshold:
                return username, score
        return None

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
        if username == ADMIN_USERNAME:
            return {"success": False, "error": "사용할 수 없는 사용자 이름입니다."}
        try:
            exists = self.user_exists(username)
        except Exception as exc:
            logger.exception("user_exists 실패: %s", exc)
            return {"success": False, "error": "데이터베이스 연결 오류입니다. 잠시 후 다시 시도해 주세요."}
        if exists:
            return {"success": False, "error": "이미 존재하는 사용자입니다."}

        pwd_err = validate_password(password)
        if pwd_err:
            return {"success": False, "error": pwd_err}

        try:
            embedding = self.encoder.encode_robust(face_image_bgr)
        except Exception as exc:
            logger.exception("얼굴 인코딩 오류: %s", exc)
            return {"success": False, "error": "얼굴 처리 중 오류가 발생했습니다. 사진을 다시 선택해 주세요."}
        if embedding is None:
            return {"success": False, "error": "얼굴을 인식하지 못했습니다. 다시 촬영해 주세요."}
        try:
            conflict = self._find_face_conflict(embedding)
        except Exception as exc:
            logger.exception("가입 전 얼굴 중복 검사 실패: %s", exc)
            return {"success": False, "error": "가입 검증 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}
        if conflict:
            return {
                "success": False,
                "error": "이미 다른 계정에 등록된 얼굴입니다. 다른 얼굴 사진으로 가입해 주세요.",
            }

        prefs = preferences or {
            "preferred_tone": "neutral",
            "topics": ["일상", "학교", "취미"],
        }

        try:
            self.db.create_user(
                username=username,
                display_name=display_name or username,
                password_hash=generate_password_hash(password),
                preferences=prefs,
                embedding=embedding,
            )
        except Exception as exc:
            logger.exception("create_user 실패 (%s): %s", username, exc)
            msg = str(exc).lower()
            if "duplicate" in msg or "unique" in msg or "already exists" in msg:
                return {"success": False, "error": "이미 존재하는 사용자입니다."}
            if "foreign key" in msg:
                return {"success": False, "error": "가입 저장에 실패했습니다. 다시 시도해 주세요."}
            return {
                "success": False,
                "error": "가입 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            }
        return {"success": True, "username": username}

    def login_password(self, username: str, password: str) -> dict:
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return {
                "success": True,
                "is_admin": True,
                "redirect_to": "/admin",
                "profile": {
                    "username": ADMIN_USERNAME,
                    "display_name": "관리자",
                    "preferences": {},
                    "mood_history": [],
                },
            }
        profile = self.db.get_user_full(username)
        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        if not check_password_hash(profile["password_hash"], password):
            return {"success": False, "error": "비밀번호가 올바르지 않습니다."}
        return {"success": True, "profile": self.public_profile(profile)}

    def login_face(self, username: str, face_image_bgr) -> dict:
        username = (username or "").strip()
        if not username:
            return {"success": False, "error": "사용자 이름을 입력해 주세요."}

        try:
            profile = self.db.get_user_full(username)
            stored_embedding = self.db.get_embedding(username)
        except Exception as exc:
            logger.exception("얼굴 로그인 사용자 조회 실패: %s", exc)
            return {
                "success": False,
                "error": "데이터베이스 연결 오류입니다. 잠시 후 다시 시도해 주세요.",
            }

        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        if stored_embedding is None:
            return {"success": False, "error": "이 계정에는 등록된 얼굴 데이터가 없습니다."}

        try:
            matched, score = self.encoder.verify_user(face_image_bgr, stored_embedding)
        except ValueError as exc:
            if str(exc) == "stored_embeddings_incompatible":
                return {
                    "success": False,
                    "error": (
                        "저장된 얼굴 데이터 형식이 맞지 않습니다. "
                        "비밀번호로 로그인한 뒤 얼굴을 다시 등록해 주세요."
                    ),
                }
            logger.exception("얼굴 매칭 값 오류: %s", exc)
            return {
                "success": False,
                "error": "얼굴 인식 처리 중 오류가 발생했습니다. 사진을 다시 선택해 주세요.",
            }
        except Exception as exc:
            logger.exception("얼굴 매칭 오류: %s", exc)
            return {
                "success": False,
                "error": "얼굴 인식 처리 중 오류가 발생했습니다. 사진을 다시 선택해 주세요.",
            }

        if not matched and score <= 0.0:
            probe = self.encoder.encode(face_image_bgr, allow_center_fallback=True)
            if probe is None:
                return {
                    "success": False,
                    "error": (
                        "사진에서 얼굴을 찾지 못했습니다. "
                        "가입할 때와 같이 정면·밝은 곳에서 다시 촬영하거나 「사진 촬영/선택」을 이용해 주세요."
                    ),
                }

        if not matched:
            hint = (
                f"이 계정에 등록된 얼굴과 일치하지 않습니다. (유사도 {round(score * 100)}%) "
                "가입할 때와 같이 정면·밝은 곳에서 다시 시도하거나 '사진 촬영/선택'을 이용해 주세요."
            )
            return {
                "success": False,
                "error": hint,
                "match_score": round(score, 3),
            }

        return {
            "success": True,
            "profile": self.public_profile(profile),
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
        if username == ADMIN_USERNAME:
            return {
                "username": ADMIN_USERNAME,
                "display_name": "관리자",
                "preferences": {},
                "mood_history": [],
            }
        profile = self.db.get_user_full(username)
        if not profile:
            return None
        return self.public_profile(profile)

    def append_chat(self, username: str, role: str, content: str, limit: int = 50):
        if username == ADMIN_USERNAME:
            return
        self.db.append_chat(username, role, content, limit)

    def get_admin_users(self, limit: int = 200) -> list[dict]:
        return self.db.list_users_summary(limit=limit)

    def delete_account(self, username: str, password: str) -> dict:
        profile = self.db.get_user_full(username)
        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        if not password:
            return {"success": False, "error": "비밀번호를 입력해 주세요."}
        if not check_password_hash(profile["password_hash"], password):
            return {"success": False, "error": "비밀번호가 올바르지 않습니다."}
        try:
            self.db.delete_user(username)
        except Exception as exc:
            logger.exception("계정 삭제 실패 (%s): %s", username, exc)
            return {
                "success": False,
                "error": "계정 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            }
        return {"success": True, "message": "계정이 삭제되었습니다."}

    def update_face(self, username: str, face_image_bgr) -> dict:
        try:
            embedding = self.encoder.encode_robust(face_image_bgr)
        except Exception as exc:
            logger.exception("얼굴 재등록 오류: %s", exc)
            return {"success": False, "error": "얼굴 처리 중 오류가 발생했습니다."}
        if embedding is None:
            return {"success": False, "error": "얼굴을 인식하지 못했습니다. 정면 사진으로 다시 시도해 주세요."}
        try:
            conflict = self._find_face_conflict(embedding, exclude_username=username)
        except Exception as exc:
            logger.exception("얼굴 재등록 중복 검사 실패: %s", exc)
            return {"success": False, "error": "얼굴 검증 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}
        if conflict:
            return {
                "success": False,
                "error": "이미 다른 계정에 등록된 얼굴과 너무 비슷합니다. 다른 사진으로 다시 시도해 주세요.",
            }
        self.db.save_embedding(username, embedding)
        return {"success": True, "message": "얼굴이 새로 등록되었습니다."}

    @staticmethod
    def public_profile(profile: dict) -> dict:
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

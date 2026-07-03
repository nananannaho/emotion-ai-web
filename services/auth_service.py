"""회원가입·얼굴 로그인·세션 관리 (DB 영구 저장)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    EMAIL_VERIFICATION_TTL_MINUTES,
    PASSWORD_RESET_TTL_MINUTES,
)
from models.face_encoder import FaceEncoder
from services.database import get_db
from utils.password_validation import validate_password

logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIGNUP_EMAIL_VERIFICATION_PURPOSE = "signup"


class AuthService:
    def __init__(self):
        self.encoder = FaceEncoder()
        self.db = get_db()

    def user_exists(self, username: str) -> bool:
        return self.db.user_exists(username)

    @staticmethod
    def normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def is_valid_email(email: str) -> bool:
        return bool(EMAIL_RE.match((email or "").strip()))

    def _get_signup_email_verification(self, email: str) -> dict | None:
        email = self.normalize_email(email)
        if not email:
            return None
        record = self.db.get_email_verification_token(email, SIGNUP_EMAIL_VERIFICATION_PURPOSE)
        if not record:
            return None
        expires_at = datetime.fromisoformat(str(record["expires_at"]))
        if expires_at < datetime.now(timezone.utc):
            return None
        return record

    def request_signup_email_verification(self, email: str) -> dict:
        email = self.normalize_email(email)
        if not self.is_valid_email(email):
            return {"success": False, "error": "올바른 이메일 주소를 입력해 주세요."}
        if self.db.email_exists(email):
            return {"success": False, "error": "이미 가입된 이메일입니다."}

        verification_code = f"{secrets.randbelow(1000000):06d}"
        code_hash = hashlib.sha256(verification_code.encode("utf-8")).hexdigest()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=EMAIL_VERIFICATION_TTL_MINUTES)
        ).isoformat()
        self.db.save_email_verification_token(
            email=email,
            purpose=SIGNUP_EMAIL_VERIFICATION_PURPOSE,
            code_hash=code_hash,
            expires_at=expires_at,
        )
        return {
            "success": True,
            "email_sent": True,
            "email": email,
            "verification_code": verification_code,
            "expires_at": expires_at,
        }

    def verify_signup_email_code(self, email: str, code: str) -> dict:
        email = self.normalize_email(email)
        code = (code or "").strip()
        if not self.is_valid_email(email):
            return {"success": False, "error": "올바른 이메일 주소를 입력해 주세요."}
        if not code:
            return {"success": False, "error": "이메일 인증번호를 입력해 주세요."}
        if self.db.email_exists(email):
            return {"success": False, "error": "이미 가입된 이메일입니다."}

        record = self._get_signup_email_verification(email)
        if not record:
            return {"success": False, "error": "인증번호를 먼저 요청하거나 다시 요청해 주세요."}

        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if code_hash != record.get("code_hash"):
            return {"success": False, "error": "이메일 인증번호가 올바르지 않습니다."}

        self.db.mark_email_verification_verified(email, SIGNUP_EMAIL_VERIFICATION_PURPOSE)
        return {"success": True, "message": "이메일 인증이 완료되었습니다."}

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
        email: str,
        password: str,
        display_name: str,
        preferences: dict | None,
        face_image_bgr,
    ) -> dict:
        if not username or len(username) < 2:
            return {"success": False, "error": "사용자 이름은 2자 이상이어야 합니다."}
        if username == ADMIN_USERNAME:
            return {"success": False, "error": "사용할 수 없는 사용자 이름입니다."}
        email = self.normalize_email(email)
        if not self.is_valid_email(email):
            return {"success": False, "error": "올바른 이메일 주소를 입력해 주세요."}
        try:
            exists = self.user_exists(username)
        except Exception as exc:
            logger.exception("user_exists 실패: %s", exc)
            return {"success": False, "error": "데이터베이스 연결 오류입니다. 잠시 후 다시 시도해 주세요."}
        if exists:
            return {"success": False, "error": "이미 존재하는 사용자입니다."}
        try:
            if self.db.email_exists(email):
                return {"success": False, "error": "이미 가입된 이메일입니다."}
        except Exception as exc:
            logger.exception("email_exists 실패: %s", exc)
            return {"success": False, "error": "데이터베이스 연결 오류입니다. 잠시 후 다시 시도해 주세요."}

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
                email=email,
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

    def request_password_reset(self, email: str) -> dict:
        email = self.normalize_email(email)
        if not self.is_valid_email(email):
            return {"success": False, "error": "올바른 이메일 주소를 입력해 주세요."}

        profile = self.db.get_user_by_email(email)
        if not profile or profile["username"] == ADMIN_USERNAME:
            return {"success": True, "email_sent": False}

        selector = secrets.token_urlsafe(12)
        verifier = secrets.token_urlsafe(32)
        reset_code = f"{secrets.randbelow(1000000):06d}"
        token_hash = hashlib.sha256(verifier.encode("utf-8")).hexdigest()
        code_hash = hashlib.sha256(reset_code.encode("utf-8")).hexdigest()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
        ).isoformat()
        self.db.save_password_reset_token(
            username=profile["username"],
            selector=selector,
            token_hash=token_hash,
            code_hash=code_hash,
            expires_at=expires_at,
        )
        return {
            "success": True,
            "email_sent": True,
            "username": profile["username"],
            "display_name": profile.get("display_name") or profile["username"],
            "email": email,
            "selector": selector,
            "token": verifier,
            "reset_code": reset_code,
            "expires_at": expires_at,
        }

    def verify_password_reset_token(self, selector: str, token: str) -> dict:
        selector = (selector or "").strip()
        token = (token or "").strip()
        if not selector or not token:
            return {"success": False, "error": "재설정 링크가 올바르지 않습니다."}

        record = self.db.get_password_reset_token(selector)
        if not record:
            return {"success": False, "error": "재설정 링크가 유효하지 않습니다."}
        if record.get("used_at"):
            return {"success": False, "error": "이미 사용된 재설정 링크입니다."}

        expires_at = datetime.fromisoformat(str(record["expires_at"]))
        if expires_at < datetime.now(timezone.utc):
            return {"success": False, "error": "재설정 링크가 만료되었습니다."}

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if token_hash != record.get("token_hash"):
            return {"success": False, "error": "재설정 링크가 유효하지 않습니다."}

        profile = self.db.get_user_full(record["username"])
        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        return {"success": True, "username": profile["username"], "email": profile.get("email", "")}

    def verify_password_reset_code(self, email: str, code: str) -> dict:
        email = self.normalize_email(email)
        code = (code or "").strip()
        if not self.is_valid_email(email):
            return {"success": False, "error": "올바른 이메일 주소를 입력해 주세요."}
        if not code:
            return {"success": False, "error": "이메일 인증번호를 입력해 주세요."}

        profile = self.db.get_user_by_email(email)
        if not profile or profile["username"] == ADMIN_USERNAME:
            return {"success": False, "error": "이메일 인증번호가 올바르지 않습니다."}

        record = self.db.get_latest_password_reset_token_for_user(profile["username"])
        if not record:
            return {"success": False, "error": "재설정 요청을 먼저 진행해 주세요."}
        if record.get("used_at"):
            return {"success": False, "error": "이미 사용된 인증번호입니다. 새로 요청해 주세요."}

        expires_at = datetime.fromisoformat(str(record["expires_at"]))
        if expires_at < datetime.now(timezone.utc):
            return {"success": False, "error": "인증번호가 만료되었습니다. 다시 요청해 주세요."}

        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if code_hash != record.get("code_hash"):
            return {"success": False, "error": "이메일 인증번호가 올바르지 않습니다."}

        return {
            "success": True,
            "username": profile["username"],
            "selector": record["token_selector"],
        }

    def reset_password(self, selector: str, token: str, new_password: str) -> dict:
        token_check = self.verify_password_reset_token(selector, token)
        if not token_check.get("success"):
            return token_check

        pwd_err = validate_password(new_password)
        if pwd_err:
            return {"success": False, "error": pwd_err}

        username = token_check["username"]
        self.db.update_password_hash(username, generate_password_hash(new_password))
        self.db.mark_password_reset_token_used((selector or "").strip())
        return {"success": True, "message": "비밀번호가 재설정되었습니다."}

    def reset_password_with_code(self, email: str, code: str, new_password: str) -> dict:
        code_check = self.verify_password_reset_code(email, code)
        if not code_check.get("success"):
            return code_check

        pwd_err = validate_password(new_password)
        if pwd_err:
            return {"success": False, "error": pwd_err}

        self.db.update_password_hash(
            code_check["username"],
            generate_password_hash(new_password),
        )
        self.db.mark_password_reset_token_used(code_check["selector"])
        return {"success": True, "message": "비밀번호가 재설정되었습니다."}

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

    def admin_delete_user(self, username: str) -> dict:
        username = (username or "").strip()
        if not username:
            return {"success": False, "error": "삭제할 사용자 이름이 필요합니다."}
        if username == ADMIN_USERNAME:
            return {"success": False, "error": "관리자 계정은 삭제할 수 없습니다."}
        profile = self.db.get_user_full(username)
        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        try:
            self.db.delete_user(username)
        except Exception as exc:
            logger.exception("관리자 계정 삭제 실패 (%s): %s", username, exc)
            return {"success": False, "error": "계정 삭제 중 오류가 발생했습니다."}
        return {"success": True, "message": f"{username} 계정을 삭제했습니다."}

    def delete_account(self, username: str, email: str) -> dict:
        profile = self.db.get_user_full(username)
        if not profile:
            return {"success": False, "error": "사용자를 찾을 수 없습니다."}
        email = self.normalize_email(email)
        if not email:
            return {"success": False, "error": "이메일 주소를 입력해 주세요."}
        if not self.is_valid_email(email):
            return {"success": False, "error": "올바른 이메일 주소를 입력해 주세요."}
        profile_email = self.normalize_email(profile.get("email", ""))
        if email != profile_email:
            return {"success": False, "error": "가입 시 등록한 이메일과 일치하지 않습니다."}
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
            "email": profile.get("email", ""),
            "preferences": prefs,
            "mood_history": moods[-10:],
        }

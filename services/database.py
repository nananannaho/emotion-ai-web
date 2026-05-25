"""
회원·얼굴·대화 데이터 영구 저장 (SQLite / PostgreSQL).

다중 사용자: username마다 별도 행으로 저장 (A의 채팅·얼굴 ≠ B의 데이터).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import numpy as np

from config import DATA_DIR, LEGACY_FACES_DIR, LEGACY_USERS_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "emotionai.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


def _normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "sslmode=" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


def _safe_username(username: str) -> str:
    raw = (username or "").strip()
    safe = re.sub(r"[^\w\-]", "", raw, flags=re.UNICODE).strip()
    return (safe or raw)[:64]


def _embedding_to_bytes(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def _bytes_to_embedding(data: bytes) -> np.ndarray | None:
    if not data:
        return None
    raw = bytes(data) if not isinstance(data, (bytes, bytearray)) else data
    if len(raw) % 4 != 0:
        return None
    arr = np.frombuffer(raw, dtype=np.float32)
    if arr.size == 0 or not np.isfinite(arr).all():
        return None
    return arr.copy()


class Database:
    def __init__(self):
        self._postgres = None
        self._pg_url = None
        self._pg_extras = None
        if _USE_POSTGRES:
            self._pg_url = _normalize_pg_url(DATABASE_URL)
            self._connect_postgres()

        if not self._postgres:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            logger.info("SQLite 데이터베이스: %s", DB_PATH)

        try:
            self.init_schema()
            self.migrate_legacy_json()
        except Exception as exc:
            logger.error("DB 초기화 실패: %s", exc)
            self._disconnect_postgres()
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.init_schema()
            self.migrate_legacy_json()

    def _disconnect_postgres(self):
        if self._postgres:
            try:
                self._postgres.close()
            except Exception:
                pass
        self._postgres = None

    def _connect_postgres(self):
        try:
            import psycopg2
            import psycopg2.extras

            self._postgres = psycopg2.connect(self._pg_url, connect_timeout=10)
            self._postgres.autocommit = False
            self._pg_extras = psycopg2.extras
            logger.info("PostgreSQL 연결됨")
        except Exception as exc:
            logger.error("PostgreSQL 연결 실패, SQLite 사용: %s", exc)
            self._disconnect_postgres()

    def _pg_ensure_alive(self):
        if not self._postgres:
            return
        try:
            with self._postgres.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            logger.warning("PostgreSQL 재연결 시도")
            try:
                self._postgres.close()
            except Exception:
                pass
            self._postgres = None
            self._connect_postgres()

    def _pg_cursor(self):
        self._pg_ensure_alive()
        if not self._postgres:
            raise RuntimeError("PostgreSQL 사용 불가")
        return self._postgres.cursor()

    def _pg_commit(self):
        if self._postgres:
            self._postgres.commit()

    def _pg_rollback(self):
        if self._postgres:
            try:
                self._postgres.rollback()
            except Exception:
                pass

    def _pg_run(self, sql: str, params=None):
        try:
            with self._pg_cursor() as cur:
                cur.execute(sql, params)
            self._pg_commit()
        except Exception:
            self._pg_rollback()
            raise

    @property
    def backend(self) -> str:
        return "postgresql" if self._postgres else "sqlite"

    def init_schema(self):
        if self._postgres:
            try:
                self._pg_run(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        username VARCHAR(64) PRIMARY KEY,
                        display_name VARCHAR(128) NOT NULL,
                        email VARCHAR(255),
                        password_hash TEXT NOT NULL,
                        preferences TEXT NOT NULL DEFAULT '{}',
                        mood_history TEXT NOT NULL DEFAULT '[]',
                        chat_history TEXT NOT NULL DEFAULT '[]',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                self._pg_run(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)"
                )
                self._pg_run(
                    """
                    CREATE TABLE IF NOT EXISTS face_embeddings (
                        username VARCHAR(64) PRIMARY KEY REFERENCES users(username) ON DELETE CASCADE,
                        embedding BYTEA NOT NULL
                    )
                    """
                )
                self._pg_run(
                    """
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        token_selector VARCHAR(64) PRIMARY KEY,
                        token_hash TEXT NOT NULL,
                        username VARCHAR(64) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                        expires_at TIMESTAMPTZ NOT NULL,
                        used_at TIMESTAMPTZ NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                self._pg_run(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
                    ON users (LOWER(email))
                    WHERE email IS NOT NULL AND email <> ''
                    """
                )
                return
            except Exception as exc:
                logger.error("PostgreSQL 스키마 생성 실패, SQLite로 전환: %s", exc)
                self._disconnect_postgres()

        with self._sqlite() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    preferences TEXT NOT NULL DEFAULT '{}',
                    mood_history TEXT NOT NULL DEFAULT '[]',
                    chat_history TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS face_embeddings (
                    username TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token_selector TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    username TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );
                """
            )
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            if "email" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique
                ON users(email COLLATE NOCASE)
                WHERE email IS NOT NULL AND email <> ''
                """
            )

    def delete_user(self, username: str) -> bool:
        u = _safe_username(username)
        if not u:
            return False
        if self._postgres:
            self._pg_run("DELETE FROM users WHERE username = %s", (u,))
        else:
            with self._sqlite() as conn:
                conn.execute("DELETE FROM face_embeddings WHERE username = ?", (u,))
                conn.execute("DELETE FROM users WHERE username = ?", (u,))
        return True

    @contextmanager
    def _sqlite(self):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate_legacy_json(self):
        """예전 JSON/npy 파일 → DB 이전 (한 번만)."""
        if not LEGACY_USERS_DIR.exists():
            return
        for path in LEGACY_USERS_DIR.glob("*.json"):
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
                username = profile.get("username") or path.stem
                if self.user_exists(username):
                    continue
                self._insert_user(
                    username=username,
                    display_name=profile.get("display_name", username),
                    email=profile.get("email", ""),
                    password_hash=profile["password_hash"],
                    preferences=profile.get("preferences", {}),
                    mood_history=profile.get("mood_history", []),
                    chat_history=profile.get("chat_history", []),
                )
                npy = LEGACY_FACES_DIR / f"{_safe_username(username)}.npy"
                if npy.exists():
                    emb = np.load(npy)
                    self.save_embedding(username, emb)
                logger.info("JSON 마이그레이션: %s", username)
            except Exception as exc:
                logger.warning("마이그레이션 건너뜀 %s: %s", path, exc)

    def user_exists(self, username: str) -> bool:
        u = _safe_username(username)
        if not u:
            return False
        if self._postgres:
            for attempt in range(2):
                try:
                    self._pg_ensure_alive()
                    with self._postgres.cursor() as cur:
                        cur.execute("SELECT 1 FROM users WHERE username = %s", (u,))
                        return cur.fetchone() is not None
                except Exception as exc:
                    logger.error("user_exists 오류 (시도 %s): %s", attempt + 1, exc)
                    self._pg_rollback()
                    self._postgres = None
                    self._connect_postgres()
            return False
        with self._sqlite() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE username = ?", (u,)).fetchone()
            return row is not None

    def _insert_user(
        self,
        username: str,
        display_name: str,
        email: str,
        password_hash: str,
        preferences: dict,
        mood_history: list,
        chat_history: list,
    ):
        u = _safe_username(username)
        if not u:
            raise ValueError("유효하지 않은 사용자 이름입니다.")
        now = datetime.now(timezone.utc).isoformat()
        prefs = json.dumps(preferences, ensure_ascii=False)
        moods = json.dumps(mood_history, ensure_ascii=False)
        chats = json.dumps(chat_history, ensure_ascii=False)

        if self._postgres:
            self._pg_run(
                """
                INSERT INTO users (username, display_name, email, password_hash, preferences, mood_history, chat_history, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (username) DO NOTHING
                """,
                (u, display_name, email or None, password_hash, prefs, moods, chats),
            )
        else:
            with self._sqlite() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users
                    (username, display_name, email, password_hash, preferences, mood_history, chat_history, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (u, display_name, email or "", password_hash, prefs, moods, chats, now),
                )

    def create_user(
        self,
        username: str,
        display_name: str,
        email: str,
        password_hash: str,
        preferences: dict,
        embedding: np.ndarray,
    ):
        u = _safe_username(username)
        if not u:
            raise ValueError("유효하지 않은 사용자 이름입니다.")

        if self._postgres:
            import psycopg2

            prefs = json.dumps(preferences, ensure_ascii=False)
            blob = psycopg2.Binary(_embedding_to_bytes(embedding))
            try:
                with self._pg_cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (username, display_name, email, password_hash, preferences, mood_history, chat_history, created_at)
                        VALUES (%s, %s, %s, %s, %s, '[]', '[]', NOW())
                        """,
                        (u, display_name, email or None, password_hash, prefs),
                    )
                    cur.execute(
                        """
                        INSERT INTO face_embeddings (username, embedding)
                        VALUES (%s, %s)
                        """,
                        (u, blob),
                    )
                self._pg_commit()
            except Exception:
                self._pg_rollback()
                raise
            return

        self._insert_user(
            username=u,
            display_name=display_name,
            email=email,
            password_hash=password_hash,
            preferences=preferences,
            mood_history=[],
            chat_history=[],
        )
        self.save_embedding(u, embedding)

    def save_embedding(self, username: str, embedding: np.ndarray):
        u = _safe_username(username)
        if not u:
            raise ValueError("유효하지 않은 사용자 이름입니다.")
        blob = _embedding_to_bytes(embedding)
        if self._postgres:
            import psycopg2

            pg_blob = psycopg2.Binary(blob)
            self._pg_run(
                """
                INSERT INTO face_embeddings (username, embedding)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                (u, pg_blob),
            )
        else:
            with self._sqlite() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO face_embeddings (username, embedding)
                    VALUES (?, ?)
                    """,
                    (u, blob),
                )

    def get_user_full(self, username: str) -> dict | None:
        u = _safe_username(username)
        if not u:
            return None
        if self._postgres:
            try:
                self._pg_ensure_alive()
                with self._postgres.cursor(cursor_factory=self._pg_extras.RealDictCursor) as cur:
                    cur.execute("SELECT * FROM users WHERE username = %s", (u,))
                    row = cur.fetchone()
                    return dict(row) if row else None
            except Exception as exc:
                logger.error("get_user_full 오류: %s", exc)
                self._pg_rollback()
                raise
        with self._sqlite() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (u,)).fetchone()
            if not row:
                return None
            return dict(row)

    def get_user_by_email(self, email: str) -> dict | None:
        target = (email or "").strip().lower()
        if not target:
            return None
        if self._postgres:
            try:
                self._pg_ensure_alive()
                with self._postgres.cursor(cursor_factory=self._pg_extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM users WHERE LOWER(email) = %s LIMIT 1",
                        (target,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
            except Exception as exc:
                logger.error("get_user_by_email 오류: %s", exc)
                self._pg_rollback()
                raise
        with self._sqlite() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE LOWER(email) = ? LIMIT 1",
                (target,),
            ).fetchone()
            return dict(row) if row else None

    def email_exists(self, email: str, exclude_username: str | None = None) -> bool:
        target = (email or "").strip().lower()
        if not target:
            return False
        exclude = _safe_username(exclude_username or "")
        if self._postgres:
            try:
                with self._pg_cursor() as cur:
                    if exclude:
                        cur.execute(
                            """
                            SELECT 1 FROM users
                            WHERE LOWER(email) = %s AND username <> %s
                            LIMIT 1
                            """,
                            (target, exclude),
                        )
                    else:
                        cur.execute(
                            "SELECT 1 FROM users WHERE LOWER(email) = %s LIMIT 1",
                            (target,),
                        )
                    return cur.fetchone() is not None
            except Exception as exc:
                logger.error("email_exists 오류: %s", exc)
                self._pg_rollback()
                raise
        with self._sqlite() as conn:
            if exclude:
                row = conn.execute(
                    """
                    SELECT 1 FROM users
                    WHERE LOWER(email) = ? AND username <> ?
                    LIMIT 1
                    """,
                    (target, exclude),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM users WHERE LOWER(email) = ? LIMIT 1",
                    (target,),
                ).fetchone()
            return row is not None

    def update_password_hash(self, username: str, password_hash: str) -> None:
        u = _safe_username(username)
        if not u:
            raise ValueError("유효하지 않은 사용자 이름입니다.")
        if self._postgres:
            self._pg_run(
                "UPDATE users SET password_hash = %s WHERE username = %s",
                (password_hash, u),
            )
            return
        with self._sqlite() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, u),
            )

    def save_password_reset_token(
        self,
        username: str,
        selector: str,
        token_hash: str,
        expires_at: str,
    ) -> None:
        u = _safe_username(username)
        if not u:
            raise ValueError("유효하지 않은 사용자 이름입니다.")
        created_at = datetime.now(timezone.utc).isoformat()
        if self._postgres:
            try:
                with self._pg_cursor() as cur:
                    cur.execute(
                        "DELETE FROM password_reset_tokens WHERE username = %s OR expires_at < NOW()",
                        (u,),
                    )
                    cur.execute(
                        """
                        INSERT INTO password_reset_tokens
                        (token_selector, token_hash, username, expires_at, used_at, created_at)
                        VALUES (%s, %s, %s, %s, NULL, %s)
                        """,
                        (selector, token_hash, u, expires_at, created_at),
                    )
                self._pg_commit()
            except Exception:
                self._pg_rollback()
                raise
            return

        with self._sqlite() as conn:
            conn.execute(
                """
                DELETE FROM password_reset_tokens
                WHERE username = ? OR expires_at < ?
                """,
                (u, created_at),
            )
            conn.execute(
                """
                INSERT INTO password_reset_tokens
                (token_selector, token_hash, username, expires_at, used_at, created_at)
                VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (selector, token_hash, u, expires_at, created_at),
            )

    def get_password_reset_token(self, selector: str) -> dict | None:
        if not selector:
            return None
        if self._postgres:
            try:
                with self._pg_cursor() as cur:
                    cur.execute(
                        """
                        SELECT token_selector, token_hash, username, expires_at, used_at, created_at
                        FROM password_reset_tokens
                        WHERE token_selector = %s
                        LIMIT 1
                        """,
                        (selector,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "token_selector": row[0],
                        "token_hash": row[1],
                        "username": row[2],
                        "expires_at": str(row[3]),
                        "used_at": str(row[4]) if row[4] else None,
                        "created_at": str(row[5]),
                    }
            except Exception as exc:
                logger.error("get_password_reset_token 오류: %s", exc)
                self._pg_rollback()
                raise

        with self._sqlite() as conn:
            row = conn.execute(
                """
                SELECT token_selector, token_hash, username, expires_at, used_at, created_at
                FROM password_reset_tokens
                WHERE token_selector = ?
                LIMIT 1
                """,
                (selector,),
            ).fetchone()
            return dict(row) if row else None

    def mark_password_reset_token_used(self, selector: str) -> None:
        if not selector:
            return
        now = datetime.now(timezone.utc).isoformat()
        if self._postgres:
            self._pg_run(
                "UPDATE password_reset_tokens SET used_at = %s WHERE token_selector = %s",
                (now, selector),
            )
            return
        with self._sqlite() as conn:
            conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE token_selector = ?",
                (now, selector),
            )

    def delete_password_reset_tokens_for_user(self, username: str) -> None:
        u = _safe_username(username)
        if not u:
            return
        if self._postgres:
            self._pg_run(
                "DELETE FROM password_reset_tokens WHERE username = %s",
                (u,),
            )
            return
        with self._sqlite() as conn:
            conn.execute(
                "DELETE FROM password_reset_tokens WHERE username = ?",
                (u,),
            )

    def get_embedding(self, username: str) -> np.ndarray | None:
        u = _safe_username(username)
        if not u:
            return None
        if self._postgres:
            try:
                with self._pg_cursor() as cur:
                    cur.execute(
                        "SELECT embedding FROM face_embeddings WHERE username = %s",
                        (u,),
                    )
                    row = cur.fetchone()
                    return _bytes_to_embedding(row[0]) if row else None
            except Exception as exc:
                logger.error("get_embedding 오류: %s", exc)
                self._pg_rollback()
                raise

        with self._sqlite() as conn:
            row = conn.execute(
                "SELECT embedding FROM face_embeddings WHERE username = ?",
                (u,),
            ).fetchone()
            return _bytes_to_embedding(row["embedding"]) if row else None

    def get_all_embeddings(self) -> dict[str, np.ndarray]:
        result = {}
        if self._postgres:
            try:
                with self._pg_cursor() as cur:
                    cur.execute("SELECT username, embedding FROM face_embeddings")
                    for username, blob in cur.fetchall():
                        emb = _bytes_to_embedding(blob)
                        if emb is not None:
                            result[username] = emb
            except Exception as exc:
                logger.error("get_all_embeddings 오류: %s", exc)
                self._pg_rollback()
                raise
            return result

        with self._sqlite() as conn:
            rows = conn.execute("SELECT username, embedding FROM face_embeddings").fetchall()
            for row in rows:
                emb = _bytes_to_embedding(row["embedding"])
                if emb is not None:
                    result[row["username"]] = emb
        return result

    def list_users_summary(self, limit: int = 200) -> list[dict]:
        users: list[dict] = []
        if self._postgres:
            try:
                with self._pg_cursor() as cur:
                    cur.execute(
                        """
                        SELECT username, display_name, created_at, mood_history, chat_history
                        FROM users
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = cur.fetchall()
            except Exception as exc:
                logger.error("list_users_summary 오류: %s", exc)
                self._pg_rollback()
                raise

            for username, display_name, created_at, moods, chats in rows:
                mood_history = json.loads(moods) if isinstance(moods, str) else (moods or [])
                chat_history = json.loads(chats) if isinstance(chats, str) else (chats or [])
                users.append({
                    "username": username,
                    "display_name": display_name,
                    "created_at": str(created_at),
                    "mood_count": len(mood_history),
                    "chat_count": len(chat_history),
                })
            return users

        with self._sqlite() as conn:
            rows = conn.execute(
                """
                SELECT username, display_name, created_at, mood_history, chat_history
                FROM users
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for row in rows:
                mood_history = json.loads(row["mood_history"]) if isinstance(row["mood_history"], str) else (row["mood_history"] or [])
                chat_history = json.loads(row["chat_history"]) if isinstance(row["chat_history"], str) else (row["chat_history"] or [])
                users.append({
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "created_at": row["created_at"],
                    "mood_count": len(mood_history),
                    "chat_count": len(chat_history),
                })
        return users

    def update_mood_history(self, username: str, emotion: str, limit: int = 20):
        profile = self.get_user_full(username)
        if not profile:
            return
        history = json.loads(profile["mood_history"]) if isinstance(profile["mood_history"], str) else profile["mood_history"]
        history.append(emotion)
        history = history[-limit:]
        self._update_json_field(username, "mood_history", history)

    def append_chat(self, username: str, role: str, content: str, limit: int = 50):
        profile = self.get_user_full(username)
        if not profile:
            return
        chats = json.loads(profile["chat_history"]) if isinstance(profile["chat_history"], str) else profile["chat_history"]
        chats.append({"role": role, "content": content})
        chats = chats[-limit:]
        self._update_json_field(username, "chat_history", chats)

    def _update_json_field(self, username: str, field: str, value: list):
        u = _safe_username(username)
        if not u:
            return
        data = json.dumps(value, ensure_ascii=False)
        if field not in ("mood_history", "chat_history"):
            return
        if self._postgres:
            self._pg_run(
                f"UPDATE users SET {field} = %s WHERE username = %s",
                (data, u),
            )
        else:
            with self._sqlite() as conn:
                conn.execute(f"UPDATE users SET {field} = ? WHERE username = ?", (data, u))


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db

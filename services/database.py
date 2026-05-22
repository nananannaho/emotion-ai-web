"""
회원·얼굴·대화 데이터 영구 저장 (SQLite / PostgreSQL).

다중 사용자: username마다 별도 행으로 저장 (A의 채팅·얼굴 ≠ B의 데이터).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from config import DATA_DIR, FACES_DIR, USERS_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "emotionai.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


def _safe_username(username: str) -> str:
    return "".join(c for c in username if c.isalnum() or c in "_-")


def _embedding_to_bytes(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def _bytes_to_embedding(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)


class Database:
    def __init__(self):
        self._postgres = None
        if _USE_POSTGRES:
            try:
                import psycopg2
                import psycopg2.extras

                url = DATABASE_URL
                if url.startswith("postgres://"):
                    url = url.replace("postgres://", "postgresql://", 1)
                self._postgres = psycopg2.connect(url)
                self._pg_extras = psycopg2.extras
                logger.info("PostgreSQL 데이터베이스 연결됨 (데이터 영구 저장)")
            except Exception as exc:
                logger.error("PostgreSQL 연결 실패, SQLite 사용: %s", exc)
                self._postgres = None

        if not self._postgres:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            logger.info("SQLite 데이터베이스: %s", DB_PATH)

        self.init_schema()
        self.migrate_legacy_json()

    @property
    def backend(self) -> str:
        return "postgresql" if self._postgres else "sqlite"

    def init_schema(self):
        if self._postgres:
            cur = self._postgres.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username VARCHAR(64) PRIMARY KEY,
                    display_name VARCHAR(128) NOT NULL,
                    password_hash TEXT NOT NULL,
                    preferences TEXT NOT NULL DEFAULT '{}',
                    mood_history TEXT NOT NULL DEFAULT '[]',
                    chat_history TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS face_embeddings (
                    username VARCHAR(64) PRIMARY KEY REFERENCES users(username) ON DELETE CASCADE,
                    embedding BYTEA NOT NULL
                )
                """
            )
            self._postgres.commit()
        else:
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
                    """
                )

    @contextmanager
    def _sqlite(self):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
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
        if not USERS_DIR.exists():
            return
        for path in USERS_DIR.glob("*.json"):
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
                username = profile.get("username") or path.stem
                if self.user_exists(username):
                    continue
                self._insert_user(
                    username=username,
                    display_name=profile.get("display_name", username),
                    password_hash=profile["password_hash"],
                    preferences=profile.get("preferences", {}),
                    mood_history=profile.get("mood_history", []),
                    chat_history=profile.get("chat_history", []),
                )
                npy = FACES_DIR / f"{_safe_username(username)}.npy"
                if npy.exists():
                    emb = np.load(npy)
                    self.save_embedding(username, emb)
                logger.info("JSON 마이그레이션: %s", username)
            except Exception as exc:
                logger.warning("마이그레이션 건너뜀 %s: %s", path, exc)

    def user_exists(self, username: str) -> bool:
        u = _safe_username(username)
        if self._postgres:
            cur = self._postgres.cursor()
            cur.execute("SELECT 1 FROM users WHERE username = %s", (u,))
            return cur.fetchone() is not None
        with self._sqlite() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE username = ?", (u,)).fetchone()
            return row is not None

    def _insert_user(
        self,
        username: str,
        display_name: str,
        password_hash: str,
        preferences: dict,
        mood_history: list,
        chat_history: list,
    ):
        u = _safe_username(username)
        now = datetime.now(timezone.utc).isoformat()
        prefs = json.dumps(preferences, ensure_ascii=False)
        moods = json.dumps(mood_history, ensure_ascii=False)
        chats = json.dumps(chat_history, ensure_ascii=False)

        if self._postgres:
            cur = self._postgres.cursor()
            cur.execute(
                """
                INSERT INTO users (username, display_name, password_hash, preferences, mood_history, chat_history, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (username) DO NOTHING
                """,
                (u, display_name, password_hash, prefs, moods, chats),
            )
            self._postgres.commit()
        else:
            with self._sqlite() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users
                    (username, display_name, password_hash, preferences, mood_history, chat_history, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (u, display_name, password_hash, prefs, moods, chats, now),
                )

    def create_user(
        self,
        username: str,
        display_name: str,
        password_hash: str,
        preferences: dict,
        embedding: np.ndarray,
    ):
        u = _safe_username(username)
        self._insert_user(
            username=u,
            display_name=display_name,
            password_hash=password_hash,
            preferences=preferences,
            mood_history=[],
            chat_history=[],
        )
        self.save_embedding(u, embedding)

    def save_embedding(self, username: str, embedding: np.ndarray):
        u = _safe_username(username)
        blob = _embedding_to_bytes(embedding)
        if self._postgres:
            cur = self._postgres.cursor()
            cur.execute(
                """
                INSERT INTO face_embeddings (username, embedding)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                (u, blob),
            )
            self._postgres.commit()
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
        if self._postgres:
            cur = self._postgres.cursor(cursor_factory=self._pg_extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE username = %s", (u,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)
        with self._sqlite() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (u,)).fetchone()
            if not row:
                return None
            return dict(row)

    def get_all_embeddings(self) -> dict[str, np.ndarray]:
        result = {}
        if self._postgres:
            cur = self._postgres.cursor()
            cur.execute("SELECT username, embedding FROM face_embeddings")
            for username, blob in cur.fetchall():
                result[username] = _bytes_to_embedding(bytes(blob))
        else:
            with self._sqlite() as conn:
                rows = conn.execute("SELECT username, embedding FROM face_embeddings").fetchall()
                for row in rows:
                    result[row["username"]] = _bytes_to_embedding(row["embedding"])
        return result

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
        data = json.dumps(value, ensure_ascii=False)
        if field not in ("mood_history", "chat_history"):
            return
        if self._postgres:
            cur = self._postgres.cursor()
            cur.execute(
                f"UPDATE users SET {field} = %s WHERE username = %s",
                (data, u),
            )
            self._postgres.commit()
        else:
            with self._sqlite() as conn:
                conn.execute(f"UPDATE users SET {field} = ? WHERE username = ?", (data, u))


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db

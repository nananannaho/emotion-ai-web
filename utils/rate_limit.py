"""간단한 인메모리 요청 제한 (단일 워커 배포용)."""

from __future__ import annotations

import time
from collections import defaultdict
from functools import wraps
from threading import Lock

from flask import jsonify, request

from config import RATE_LIMIT_ENABLED

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _client_key(endpoint: str) -> str:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    addr = forwarded or (request.remote_addr or "unknown")
    return f"{addr}:{endpoint}"


def rate_limit(max_calls: int, window_seconds: int):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not RATE_LIMIT_ENABLED:
                return func(*args, **kwargs)

            key = _client_key(request.endpoint or func.__name__)
            now = time.monotonic()
            with _lock:
                hits = _buckets[key]
                _buckets[key] = [t for t in hits if now - t < window_seconds]
                if len(_buckets[key]) >= max_calls:
                    return jsonify({
                        "success": False,
                        "error": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                    }), 429
                _buckets[key].append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator

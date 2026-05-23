"""비밀번호 규칙: *, &, \" 는 금지, 그 외 특수문자 1개 이상 필수."""

from __future__ import annotations

import re

FORBIDDEN_CHARS = frozenset('*&"')
# *, &, " 제외한 특수문자
SPECIAL_RE = re.compile(r"[!@#$%^()_+\-=\[\]{}|;:',.<>?/\\`~]")


def validate_password(password: str) -> str | None:
    if not password or len(password) < 8:
        return "비밀번호는 8자 이상이어야 합니다."
    if any(c in FORBIDDEN_CHARS for c in password):
        return '비밀번호에 *, &, " 문자는 사용할 수 없습니다.'
    if not SPECIAL_RE.search(password):
        return '비밀번호에 특수문자를 포함해 주세요 (*, &, " 제외).'
    return None

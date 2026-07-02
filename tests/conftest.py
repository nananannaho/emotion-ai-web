# 테스트 실행 전 환경 (로컬 SQLite, 이메일 인증 생략)
import os

os.environ.setdefault("SKIP_EMAIL_VERIFICATION", "1")
os.environ.pop("RENDER", None)
os.environ.pop("RAILWAY_ENVIRONMENT", None)
os.environ.pop("DATABASE_URL", None)

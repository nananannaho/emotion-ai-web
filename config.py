import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WEIGHTS_DIR = BASE_DIR / "weights"

# 예전 JSON 저장소 (최초 1회 DB로 이전용)
LEGACY_USERS_DIR = DATA_DIR / "users"
LEGACY_FACES_DIR = DATA_DIR / "faces"
# 예전 이름 호환 (GitHub/Render 구버전 참조용)
USERS_DIR = LEGACY_USERS_DIR
FACES_DIR = LEGACY_FACES_DIR

for directory in (DATA_DIR, WEIGHTS_DIR, LEGACY_USERS_DIR, LEGACY_FACES_DIR):
    directory.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "emotion-ai-club-dev-key-change-in-production")
MAX_CONTENT_LENGTH = 8 * 1024 * 1024

USE_LIGHT_ML = os.environ.get("USE_LIGHT_ML", "").lower() in ("1", "true", "yes")
IS_CLOUD = bool(os.environ.get("RENDER") or os.environ.get("RAILWAY_ENVIRONMENT"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = DATA_DIR / "emotionai.db"

EMOTION_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
EMOTION_LABELS_KO = {
    "angry": "분노",
    "disgust": "혐오",
    "fear": "불안",
    "happy": "기쁨",
    "sad": "슬픔",
    "surprise": "놀람",
    "neutral": "평온",
}

FACE_MATCH_THRESHOLD = 0.72
FACE_MATCH_THRESHOLD_LIGHT = 0.74
FACE_MATCH_MARGIN = 0.08
FACE_MATCH_MARGIN_LIGHT = 0.05
EMOTION_IMG_SIZE = (48, 48)
FACE_IMG_SIZE = (96, 96)

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
USERS_DIR = DATA_DIR / "users"
FACES_DIR = DATA_DIR / "faces"
WEIGHTS_DIR = BASE_DIR / "weights"
UPLOAD_DIR = DATA_DIR / "uploads"

for directory in (DATA_DIR, USERS_DIR, FACES_DIR, WEIGHTS_DIR, UPLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "emotion-ai-club-dev-key-change-in-production")
MAX_CONTENT_LENGTH = 8 * 1024 * 1024

# 클라우드 배포: TensorFlow 없이 OpenCV·휴리스틱 ML 사용 (무료 서버 메모리 절약)
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
EMOTION_IMG_SIZE = (48, 48)
FACE_IMG_SIZE = (96, 96)

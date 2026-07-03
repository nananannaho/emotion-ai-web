"""CNN 가중치 초기화 — 최초 1회 실행."""

import sys
from pathlib import Path

print("EmotionAI 모델 초기화를 시작합니다...")
print("TensorFlow 설치 여부를 확인합니다. (처음 실행 시 시간이 걸릴 수 있습니다)\n")

try:
    import subprocess

    from models.emotion_cnn import EmotionCNN
    from models.face_encoder import FaceEncoder

    print("[1/3] FER2013 다운로드 (없을 때만)...")
    fer_csv = Path(__file__).resolve().parent / "data" / "fer2013" / "fer2013.csv"
    if not fer_csv.exists():
        subprocess.check_call([sys.executable, "scripts/download_fer2013.py"])

    print("[2/3] 감정 ML 분류기 학습 (FER2013 실제 얼굴, Render용)...")
    subprocess.check_call([sys.executable, "scripts/train_emotion_classifier.py"])

    print("[3/3] 감정 분류 CNN 학습·저장 (로컬 TensorFlow용)...")
    path1 = EmotionCNN.train_minimal_weights(epochs=2)
    print(f"  → 저장 완료: {path1}\n")

    if fer_csv.exists():
        print("[선택] FER2013 CNN (더 정확): python scripts/train_emotion_cnn_fer2013.py")

    print("[4/4] 얼굴 인코더 CNN 저장...")
    path2 = FaceEncoder.train_minimal_weights()
    print(f"  → 저장 완료: {path2}\n")

    print("모든 모델이 준비되었습니다. python app.py 로 서버를 실행하세요.")
except ImportError as e:
    print("오류: 의존성이 설치되지 않았습니다.")
    print("  pip install -r requirements.txt")
    print(f"  상세: {e}")
    sys.exit(1)
except Exception as e:
    print(f"오류: {e}")
    sys.exit(1)

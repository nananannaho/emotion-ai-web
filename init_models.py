"""CNN 가중치 초기화 — 최초 1회 실행."""

import sys

print("EmotionAI 모델 초기화를 시작합니다...")
print("TensorFlow 설치 여부를 확인합니다. (처음 실행 시 시간이 걸릴 수 있습니다)\n")

try:
    from models.emotion_cnn import EmotionCNN
    from models.face_encoder import FaceEncoder

    print("[1/2] 감정 분류 CNN 학습·저장...")
    path1 = EmotionCNN.train_minimal_weights(epochs=2)
    print(f"  → 저장 완료: {path1}\n")

    print("[2/2] 얼굴 인코더 CNN 저장...")
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

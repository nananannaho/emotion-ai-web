# 표정 학습용 사진 넣는 곳 (직접 촬영)

프로젝트 폴더 기준 경로:

```
data/emotions/
  happy/      ← 웃는 표정  .jpg .png .jpeg
  sad/        ← 슬픈 표정
  angry/      ← 화난 표정
  neutral/    ← 무표정·평온
  fear/       ← 불안·긴장
  surprise/   ← 놀람
  disgust/     ← 찡그림·혐오
```

## 권장

- 감정마다 **20장 이상** (다양한 각도·조명)
- **정면**, 얼굴이 크게, 밝은 곳
- 파일 이름은 아무거나 가능 (`photo1.jpg` 등)

## 학습 방법 (PC에서)

1. 위 폴더에 사진 복사
2. `학습-실행.bat` 더블클릭  
   또는:
   ```bash
   python scripts/train_emotion_classifier.py
   ```
3. `weights/emotion_clf.joblib` 생성 확인
4. `git add weights/emotion_clf.joblib` → `git push` → Render Manual Deploy

FER2013 기본 데이터는 `data/fer2013/fer2013.csv` (자동 다운로드, Git에는 안 올림).

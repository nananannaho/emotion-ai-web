@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo  EmotionAI 감정 모델 학습 (FER2013)
echo ========================================
echo.

python scripts/download_fer2013.py
if errorlevel 1 exit /b 1

echo.
python scripts/train_emotion_classifier.py
if errorlevel 1 exit /b 1

echo.
echo 완료. weights\emotion_clf.joblib 이 갱신되었습니다.
echo git push 후 Render에서 Manual Deploy 하세요.
pause

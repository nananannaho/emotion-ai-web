@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] Python이 설치되어 있지 않습니다.
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo 가상환경 생성 중...
  python -m venv venv
)

echo 경량 패키지 설치 중 ^(TensorFlow 제외, 약 200MB^)...
"venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo [오류] 패키지 설치에 실패했습니다.
  pause
  exit /b 1
)

if not exist "weights\emotion_clf.joblib" (
  echo [오류] weights\emotion_clf.joblib 이 없습니다.
  echo GitHub에서 프로젝트를 다시 받거나 배포된 저장소를 clone 하세요.
  pause
  exit /b 1
)

set USE_LIGHT_ML=1
set SKIP_EMAIL_VERIFICATION=1

echo.
echo ============================================
echo   PC:      http://127.0.0.1:5000
echo   경량 ML  ^(joblib, TensorFlow 없음^)
echo   CNN 학습: pip install -r requirements-dev.txt
echo ============================================
echo.

"venv\Scripts\python.exe" app.py
pause

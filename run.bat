@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [오류] Python이 설치되어 있지 않습니다.
  echo https://www.python.org 에서 Python 3.10 이상을 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo 가상환경 생성 중...
  python -m venv venv
  if errorlevel 1 (
    echo [오류] 가상환경 생성에 실패했습니다.
    pause
    exit /b 1
  )
)

echo 패키지 확인 중...
"venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo [오류] 패키지 설치에 실패했습니다.
  pause
  exit /b 1
)

if not exist "weights\emotion_cnn.keras" (
  echo CNN 모델 초기화 중... ^(최초 1회, 1~2분 소요^)
  "venv\Scripts\python.exe" init_models.py
  if errorlevel 1 (
    echo [오류] 모델 초기화에 실패했습니다.
    pause
    exit /b 1
  )
)

echo.
echo ============================================
echo   PC:      http://127.0.0.1:5000
echo   모바일:  아래 서버 시작 후 표시되는
echo            http://192.168.x.x:5000 주소
echo            (같은 Wi-Fi 필요)
echo   이 창을 닫으면 사이트가 꺼집니다.
echo ============================================
echo.

"venv\Scripts\python.exe" app.py
if errorlevel 1 (
  echo.
  echo [오류] 서버가 종료되었습니다. 위 메시지를 확인하세요.
)
pause

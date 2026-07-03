@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

echo ============================================
echo   Felunai 로컬 디스크 정리
echo ============================================
echo.

if exist "venv" (
  echo [1] venv 삭제 ^(TensorFlow 포함, 약 1.5GB^)...
  rmdir /s /q "venv"
  echo     완료. run.bat 실행 시 경량 venv가 다시 만들어집니다.
) else (
  echo [1] venv 없음 — 건너뜀
)

if exist "data\fer2013" (
  echo [2] data\fer2013 삭제 ^(학습용 CSV, Git 미포함^)...
  rmdir /s /q "data\fer2013"
) else (
  echo [2] fer2013 없음 — 건너뜀
)

if exist "weights\emotion_clf.joblib.bak" (
  echo [3] 모델 백업 파일 삭제...
  del /q "weights\emotion_clf.joblib.bak"
) else (
  echo [3] 모델 백업 없음 — 건너뜀
)

if exist "weights\emotion_cnn.keras" del /q "weights\emotion_cnn.keras"
if exist "weights\face_encoder.keras" del /q "weights\face_encoder.keras"
echo [4] 로컬 CNN 가중치 ^(.keras^) 삭제 완료

for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
if exist ".pytest_cache" rmdir /s /q ".pytest_cache"
echo [5] 캐시 폴더 정리 완료

where git >nul 2>&1
if not errorlevel 1 (
  echo [6] Git 저장소 압축 ^(.git 용량 축소^)...
  git gc --prune=now
  git repack -ad
)

echo.
echo 정리 완료. run.bat 으로 서버를 다시 실행하세요.
pause

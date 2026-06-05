@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;%PATH%"
set "REPO_URL=https://github.com/nananannaho/emotion-ai-web.git"

where git >nul 2>&1
if errorlevel 1 (
  echo [오류] Git이 설치되어 있지 않습니다.
  pause
  exit /b 1
)

git remote remove origin 2>nul
git remote add origin "%REPO_URL%"

echo GitHub 최신 상태 받는 중...
git pull origin main
if errorlevel 1 (
  echo [오류] pull 실패. 충돌이 있으면 Cursor에서 해결 후 다시 실행하세요.
  pause
  exit /b 1
)

echo 변경된 추적 파일만 커밋합니다 ^(새 로컬 파일·venv·데이터 제외^)
git add -u
git status
git commit -m "EmotionAI 업데이트 %date% %time%"
if errorlevel 1 (
  echo 커밋할 변경 없음.
  pause
  exit /b 0
)

git push origin main
if errorlevel 1 (
  echo [push 실패] gh auth login 후 다시 실행하세요.
) else (
  echo.
  echo push 완료! Render 재배포 5~10분 대기
  echo https://emotion-ai-5whv.onrender.com
)
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;%PATH%"

where git >nul 2>&1
if errorlevel 1 (
  echo [오류] Git이 설치되어 있지 않습니다.
  pause
  exit /b 1
)

if not exist ".git" (
  echo [오류] Git 저장소가 없습니다. Cursor에서 초기 설정을 먼저 실행하세요.
  pause
  exit /b 1
)

if not exist "repo.url" (
  echo GitHub 저장소 URL이 없습니다.
  echo repo.url 파일을 만들거나 아래에 URL을 입력하세요.
  echo 예: https://github.com/아이디/emotion-ai-web.git
  set /p REPO_URL="저장소 URL: "
  if "!REPO_URL!"=="" (
    echo URL이 비어 있습니다.
    pause
    exit /b 1
  )
  echo !REPO_URL!> repo.url
)

set /p REPO_URL=<repo.url
git remote remove origin 2>nul
git remote add origin "%REPO_URL%"

git add .
git status
git commit -m "EmotionAI 업데이트 %date% %time%"
if errorlevel 1 echo 커밋할 변경 없음 — push만 시도합니다.

git branch -M main
git push -u origin main

if errorlevel 1 (
  echo.
  echo [push 실패] GitHub 로그인이 필요할 수 있습니다.
  echo PowerShell에서: gh auth login
  echo 그 다음 이 파일을 다시 실행하세요.
) else (
  echo.
  echo ============================================
  echo   push 완료! Render 재배포 5~10분 대기
  echo   https://emotion-ai-5whv.onrender.com
  echo ============================================
)
pause

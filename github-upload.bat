@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

:: Git 경로 (설치됐는데 git 명령이 안 될 때)
set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=C:\Program Files (x86)\Git\cmd\git.exe"
if not exist "%GIT_EXE%" (
  echo [오류] Git이 설치되어 있지 않습니다.
  echo https://git-scm.com/download/win 에서 설치 후 다시 실행하세요.
  pause
  exit /b 1
)

set "PATH=C:\Program Files\Git\cmd;%PATH%"

echo ============================================
echo   GitHub 업로드 도우미
echo ============================================
"%GIT_EXE%" --version
echo.

"%GIT_EXE%" init 2>nul
"%GIT_EXE%" add .
"%GIT_EXE%" status

echo.
echo --- Git 사용자 설정 (처음 한 번만) ---
"%GIT_EXE%" config user.email 2>nul | findstr /r "." >nul
if errorlevel 1 (
  set /p GIT_EMAIL="이메일 입력 (GitHub 가입 이메일): "
  "%GIT_EXE%" config user.email "!GIT_EMAIL!"
)
"%GIT_EXE%" config user.name 2>nul | findstr /r "." >nul
if errorlevel 1 (
  set /p GIT_NAME="이름 입력 (예: 홍길동): "
  "%GIT_EXE%" config user.name "!GIT_NAME!"
)

"%GIT_EXE%" commit -m "EmotionAI 웹사이트" 2>nul
if errorlevel 1 (
  echo 변경사항이 없거나 이미 커밋됨. 계속합니다...
  "%GIT_EXE%" commit -m "EmotionAI 업데이트" --allow-empty 2>nul
)

echo.
echo --- GitHub 저장소 주소 ---
echo 예: https://github.com/내아이디/emotion-ai-web.git
set /p REPO_URL="저장소 URL 붙여넣기: "
if "%REPO_URL%"=="" (
  echo URL이 비어 있습니다. GitHub에서 저장소를 만든 뒤 다시 실행하세요.
  pause
  exit /b 1
)

"%GIT_EXE%" remote remove origin 2>nul
"%GIT_EXE%" remote add origin "%REPO_URL%"
"%GIT_EXE%" branch -M main

echo.
echo GitHub 로그인 창이 뜨면 로그인하세요...
"%GIT_EXE%" push -u origin main

if errorlevel 1 (
  echo.
  echo [push 실패] GitHub Desktop 사용 또는 Git없이-배포하기.md 참고
) else (
  echo.
  echo ============================================
  echo   GitHub 업로드 완료!
  echo   이제 render.com 에서 Blueprint 배포하세요.
  echo ============================================
)
pause

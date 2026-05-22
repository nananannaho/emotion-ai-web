@echo off
chcp 65001 >nul
set "PATH=C:\Program Files\Git\cmd;%PATH%"
echo Git 확인 중...
where git 2>nul
git --version 2>nul
if errorlevel 1 (
  echo.
  echo Git이 PATH에 없습니다. github-upload.bat 은 자동 경로를 씁니다.
  if exist "C:\Program Files\Git\cmd\git.exe" (
    "C:\Program Files\Git\cmd\git.exe" --version
    echo 설치됨 - github-upload.bat 을 사용하세요.
  ) else (
    echo 미설치 - https://git-scm.com/download/win
  )
) else (
  echo OK - git 명령 사용 가능
)
pause

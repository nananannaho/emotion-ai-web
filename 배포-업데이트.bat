@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

echo GitHub에 코드 올리기 (Render 자동 재배포)
echo.

git add .
git status
echo.

set "MSG=Felunai 업데이트 %date% %time%"
git commit -m "%MSG%"
if errorlevel 1 (
  echo 커밋할 변경 없거나 이미 완료됨
)
git push origin main

if errorlevel 1 (
  echo.
  echo push 실패 - GitHub 로그인 확인
) else (
  echo.
  echo ============================================
  echo   push 완료! Render 재배포 5~10분 대기
  echo   그 다음 확인:
  echo   /health  -^> api_version
  echo   관리자 로그인 후 /health/detail
  echo   -^> database: postgresql
  echo ============================================
)
pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

echo GitHub에 DB 코드 올리기 (Render 자동 재배포)
echo.

git add .
git status
echo.
git commit -m "DB 영구저장 및 사용자별 데이터"
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
  echo   그 다음 /health 확인:
  echo   "database": "postgresql"
  echo   "database_url_set": true
  echo ============================================
)
pause

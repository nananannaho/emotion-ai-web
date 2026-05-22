# Git 설치 없이 GitHub에 올리는 방법

`git` 명령이 안 될 때 (Git 미설치) 이 방법을 사용하세요.

## 1. GitHub 저장소 만들기

1. https://github.com 로그인
2. **+** → **New repository**
3. 이름: `emotion-ai-web` → **Create repository**

## 2. 파일 직접 업로드

1. 만든 저장소 페이지에서 **Add file** → **Upload files**
2. 탐색기에서 프로젝트 폴더 열기:  
   `동아리 웹사이트 제작`
3. **아래 폴더/파일을 전부 드래그**해서 GitHub 페이지에 놓기  
   - ⚠️ **`venv` 폴더는 넣지 마세요** (용량 크고 불필요)
   - ⚠️ **`data` 안의 users, faces 파일**도 안 넣어도 됨

### 꼭 올려야 하는 것

- `app.py`, `config.py`, `init_models.py`, `requirements.txt`, `requirements-deploy.txt`
- `render.yaml`, `Procfile`, `runtime.txt`, `run.bat`
- `models` 폴더 전체
- `services` 폴더 전체
- `static` 폴더 전체
- `templates` 폴더 전체
- `utils` 폴더 전체
- `README.md`, `DEPLOY.md`, `.gitignore`

4. 아래 **Commit changes** 클릭

## 3. Render 배포

1. https://render.com → GitHub 로그인
2. **New +** → **Blueprint**
3. `emotion-ai-web` 저장소 선택 → **Apply**
4. 완료 후 `https://xxxx.onrender.com` 주소 사용

---

## (권장) Git 설치 후 명령어로 올리기

1. https://git-scm.com/download/win 에서 설치 (Next 연속 클릭)
2. **PowerShell을 완전히 닫았다가 다시 열기**
3. `DEPLOY.md` 1단계 명령 다시 실행

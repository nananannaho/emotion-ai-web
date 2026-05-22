# EmotionAI 인터넷 배포 가이드 (Render 무료)

다른 집·학교·LTE에서도 **공개 URL**로 접속할 수 있게 하는 방법입니다.

## 준비물

- [GitHub](https://github.com) 계정 (무료)
- [Render](https://render.com) 계정 (무료, GitHub로 로그인)

## 1단계: GitHub에 코드 올리기

### 방법 A — `git` 명령이 안 될 때 (가장 쉬움)

1. GitHub에서 저장소 먼저 만들기 (아래 1-1 참고)
2. 프로젝트 폴더에서 **`github-upload.bat`** 더블클릭
3. 안내에 따라 이메일·이름·저장소 URL 입력

### 방법 B — PowerShell (Git PATH 적용된 경우)

```powershell
cd "c:\Users\parkj\OneDrive\사진\바탕 화면\동아리 웹사이트 제작"
git init
git add .
git commit -m "EmotionAI 웹사이트 초기 버전"
```

> `git`이 인식되지 않으면 **Cursor를 완전히 종료 후 다시 열기** 또는 **`github-upload.bat`** 사용.

GitHub에서 **New repository** → 이름 예: `emotion-ai-web` → 생성

```powershell
git remote add origin https://github.com/본인아이디/emotion-ai-web.git
git branch -M main
git push -u origin main
```

> `venv` 폴더는 `.gitignore`에 있어 올라가지 않습니다.

## 2단계: Render에 배포

1. [https://dashboard.render.com](https://dashboard.render.com) 접속
2. **New +** → **Blueprint**
3. 방금 만든 GitHub 저장소 **Connect**
4. `render.yaml`이 자동 인식됨 → **Apply**
5. 5~10분 정도 기다리면 **Live** URL 생성  
   예: `https://emotion-ai-xxxx.onrender.com`

이 주소를 친구·교사에게 공유하면 **어디서나** 접속 가능합니다.

## 배포 후 vs 로컬(PC)

| | 로컬 `run.bat` | Render 배포 |
|--|----------------|-------------|
| 접속 | 같은 Wi-Fi / 본인 PC | **전 세계 어디서나** |
| 주소 | `127.0.0.1` / `192.168.x.x` | `https://xxxx.onrender.com` |
| HTTPS | 없음(로컬) | **있음** (휴대폰 카메라에 유리) |
| CNN(TensorFlow) | 사용 가능 | **경량 모드** (OpenCV·규칙 기반) |
| 회원 데이터 | PC에 저장 | 서버 재시작 시 **초기화될 수 있음** (무료 한계) |

무료 서버 메모리 때문에 TensorFlow는 빼고, 감정·얼굴은 **경량 알고리즘**으로 동작합니다.  
과제·시연용으로는 충분하고, 발표 시 “로컬은 CNN 풀버전, 클라우드는 경량 배포”라고 설명하면 됩니다.

## 3단계: 동작 확인

- 배포 URL 접속 → 홈 화면
- 회원가입 → **사진 촬영/선택** (HTTPS라 모바일 카메라가 로컬보다 잘 될 때 많음)
- 로그인 → 대시보드 → 감정 분석 · 채팅

헬스 체크: `https://본인주소.onrender.com/health` → `{"status":"ok"}`

## 자주 묻는 문제

### 배포가 실패해요
- Render 로그에서 `pip install` 오류 확인
- Python 3.11 사용 (`runtime.txt` 참고)

### 15분 안 쓰면 느려져요 (무료 플랜)
- Render 무료는 **슬립 모드** → 첫 접속 시 30초~1분 걸릴 수 있음  
- 과제 제출 URL은 미리 한 번 열어 두기

### 회원가입이 사라져요
- 무료 서버는 재배포·재시작 시 `data/` 폴더가 비워질 수 있음  
- 데모용 계정은 배포 후 다시 만들기

### 코드 수정 후 반영
```powershell
git add .
git commit -m "수정 내용"
git push
```
Render가 자동으로 다시 배포합니다.

## 수동 배포 (Blueprint 없이)

1. Render → **New +** → **Web Service**
2. 저장소 연결
3. 설정:
   - **Build Command:** `pip install -r requirements-deploy.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1`
   - **Environment Variables:**
     - `USE_LIGHT_ML` = `1`
     - `RENDER` = `true`
     - `SECRET_KEY` = (랜덤 긴 문자열)
4. **Create Web Service**

---

로컬 개발은 계속 `run.bat`을 사용하면 됩니다.

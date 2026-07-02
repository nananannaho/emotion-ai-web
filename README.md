# Felunai — 감정 인식 맞춤형 챗봇

딥러닝 감정 분석 · 얼굴 인식 로그인 · 멀티모달 AI 챗봇 · **사용자별 DB 저장**

## 주요 기능

- **CNN 얼굴 인식** — 회원가입 시 얼굴 등록, 로그인 시 본인 확인
- **CNN 감정 분류** — 7가지 감정 실시간 분석
- **멀티모달 융합** — 표정 + 대화 + 사용자 이력
- **맞춤 챗봇** — Gemini API(키 설정 시) 또는 자체 로컬 엔진
- **다중 사용자** — 아이디마다 데이터 분리 저장
- **대화·감정 기록** — 새로고침 후에도 대화 복원, 최근 감정 표시

## 빠른 시작

| 용도 | 방법 |
|------|------|
| PC에서 실행 | `run.bat` → http://127.0.0.1:5000 |
| 인터넷 배포 | [DEPLOY.md](DEPLOY.md) 참고 |
| 코드 수정 후 배포 | `배포-업데이트.bat` 또는 `git push` |

배포 URL 예: https://emotion-ai-5whv.onrender.com

## 로컬 설치 (최초 1회)

```powershell
cd "프로젝트 폴더"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_models.py
python app.py
```

### 로컬 개발 팁

- **이메일 없이 가입 테스트:** `set SKIP_EMAIL_VERIFICATION=1` 후 `python app.py`
- **헬스 체크:** `/health` → `api_version` 확인 (관리자 상세: `/health/detail`)

## 테스트

```powershell
pip install pytest
pytest
```

## 프로젝트 구조

```
app.py                 # Flask 서버
config.py              # 설정
init_models.py         # 로컬 CNN 가중치 생성
run.bat                # PC 실행
배포-업데이트.bat      # GitHub push → Render 재배포
models/                # CNN 감정·얼굴, 멀티모달 융합
services/              # 인증, DB, 감정, 챗봇
utils/                 # OpenCV·요청 제한 유틸
static/  templates/    # 프론트엔드
tests/                 # pytest
data/                  # SQLite (로컬)
DEPLOY.md              # 배포·Neon DB 가이드
```

## 기술 스택

Python · Flask · TensorFlow(로컬) · OpenCV · SQLite / PostgreSQL(Neon) · Google Gemini(선택)

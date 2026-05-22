# EmotionAI — 감정 인식 맞춤형 챗봇 웹사이트

동아리 프로젝트용 **딥러닝 감정 분석 + 얼굴 인식 로그인 + 멀티모달 AI 챗봇** 웹 애플리케이션입니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| **CNN 얼굴 인식 로그인** | 회원가입 시 얼굴 임베딩 저장 → 로그인 시 CNN/코사인 유사도로 본인 확인 |
| **CNN 감정 분류** | 웹캠 얼굴에서 7가지 감정(기쁨, 슬픔, 분노 등) 실시간 분류 |
| **멀티모달 융합** | 표정(45%) + 대화 텍스트(30%) + 사용자 이력·선호(25%) 가중 결합 |
| **맞춤 챗봇** | 융합된 감정·상황에 맞는 한국어 응답 |

## 기술 스택

- **백엔드**: Python 3.10+, Flask
- **딥러닝**: TensorFlow/Keras (CNN), OpenCV (얼굴 검출)
- **프론트엔드**: HTML, CSS, JavaScript (반응형 UI)

## 인터넷에 배포 (누구나 접속)

다른 집·학교에서도 URL로 접속하려면 **Render 무료 배포**를 사용하세요.

👉 **[DEPLOY.md](DEPLOY.md)** 에 GitHub + Render 단계별 가이드가 있습니다.

배포 후 예: `https://emotion-ai-xxxx.onrender.com` (HTTPS, 전국 어디서나 접속)

## 설치 및 실행 (본인 PC)

### 1. 가상환경 (권장)

```powershell
cd "c:\Users\parkj\OneDrive\사진\바탕 화면\동아리 웹사이트 제작"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. CNN 모델 가중치 생성 (최초 1회)

```powershell
python init_models.py
```

실제 FER2013 등 공개 데이터셋으로 재학습하면 감정 분류 정확도가 크게 향상됩니다.

### 3. 서버 실행

```powershell
python app.py
```

브라우저에서 **http://127.0.0.1:5000** 접속

### 모바일(스마트폰)에서 사용하기

1. PC에서 `run.bat`으로 서버 실행
2. 터미널에 표시되는 **`http://192.168.x.x:5000`** 주소 확인
3. **휴대폰을 PC와 같은 Wi-Fi**에 연결
4. 휴대폰 브라우저(Chrome·Safari) 주소창에 위 주소 입력

| 기능 | 모바일 |
|------|--------|
| 화면 | 반응형 UI, 햄버거 메뉴, 터치 버튼 |
| 카메라 | 전면 카메라 / **사진 촬영·선택** 버튼 |
| iPhone | Wi-Fi IP 접속 시 카메라가 막힐 수 있음 → **사진 선택** 사용 |

> Windows 방화벽이 뜨면 **Python 허용**을 눌러야 휴대폰에서 접속됩니다.

> 카메라: PC는 `localhost`에서, 모바일은 **사진 선택**이 가장 안정적입니다.

## 사용 방법

1. **회원가입** → 얼굴 촬영 후 계정 생성  
2. **로그인** → 얼굴 인식 또는 비밀번호  
3. **대시보드** → `감정 분석하기`로 CNN 분석 → 채팅으로 맞춤 대화  

## 프로젝트 구조

```
├── app.py                 # Flask 메인 서버
├── config.py              # 설정
├── init_models.py         # CNN 가중치 초기화
├── models/
│   ├── emotion_cnn.py     # 감정 분류 CNN
│   ├── face_encoder.py    # 얼굴 임베딩 CNN
│   └── fusion.py          # 멀티모달 융합
├── services/
│   ├── auth_service.py
│   ├── emotion_service.py
│   └── chatbot_service.py
├── static/                # CSS, JS
├── templates/             # HTML 페이지
├── data/                  # 사용자·얼굴 데이터 (자동 생성)
└── weights/               # 학습된 모델 (자동 생성)
```

## 동아리 발표 포인트

- **합성곱 신경망(CNN)**: 감정·얼굴 두 갈래 모델 구조 분리
- **멀티모달**: 시각 + 언어 + 사용자 프로필 융합 알고리즘
- **개인화**: 사용자별 얼굴·감정 이력 저장

## 향후 개선

- FER2013 / CK+ 데이터셋으로 `emotion_cnn.keras` 재학습
- FaceNet 등 사전학습 얼굴 인코더 적용
- OpenAI 등 LLM API 연동으로 대화 품질 향상

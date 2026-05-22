# 회원 데이터 오래 남기기 (Neon + Render)

배포 사이트(`https://emotion-ai-5whv.onrender.com` 등)에서 **가입·로그인 정보가 사라지지 않게** 하는 설정입니다.

---

## ① Neon에서 무료 DB 만들기

1. 브라우저에서 **https://neon.tech** 접속
2. **Sign up** → GitHub 또는 Google로 가입 (무료)
3. 로그인 후 **New Project** 클릭
4. 설정 예시:
   - **Project name:** `emotion-ai` (아무 이름 가능)
   - **Region:** `Asia Pacific (Singapore)` 또는 가까운 지역
   - **PostgreSQL version:** 기본값
5. **Create Project** 클릭

---

## ② 연결 주소(Connection string) 복사

1. 프로젝트 화면에서 **Dashboard** 로 이동
2. **Connection Details** 또는 **Connect** 섹션 찾기
3. **Connection string** 탭 선택
4. 형식이 이런 문자열입니다:

   ```
   postgresql://사용자:비밀번호@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```

5. **Copy** 버튼으로 **전체** 복사 (한 줄 전체)

> `postgres://` 로 시작해도 됩니다. 둘 다 사용 가능합니다.

---

## ③ Render에 연결하기

1. **https://dashboard.render.com** 접속
2. 배포한 서비스 클릭 (예: `emotion-ai`)
3. 왼쪽 메뉴 **Environment** 클릭
4. **Add Environment Variable** 클릭
5. 입력:
   | Key | Value |
   |-----|--------|
   | `DATABASE_URL` | ②에서 복사한 주소 **그대로 붙여넣기** |
6. **Save, rebuild, and deploy** (또는 **Save Changes**)
7. 상단 **Events** / **Logs**에서 **Deploy live** 될 때까지 대기 (3~10분)

---

## ④ 잘 연결됐는지 확인

1. 브라우저에서 접속:

   ```
   https://본인-render주소.onrender.com/health
   ```

   예: `https://emotion-ai-5whv.onrender.com/health`

2. 아래처럼 나오면 **성공**:

   ```json
   {
     "status": "ok",
     "database": "postgresql",
     ...
   }
   ```

   `"database": "sqlite"` 이면 `DATABASE_URL`이 아직 적용 안 된 것 → ③ 다시 확인

---

## ⑤ 사이트에서 테스트

1. `https://emotion-ai-5whv.onrender.com` 접속
2. **새로** 회원가입 (Neon 연결 전 계정은 DB가 달라서 다시 가입하는 것이 좋음)
3. 로그아웃 → 다시 로그인
4. 다음날 또는 PC를 껐다 켠 뒤 **같은 주소**로 다시 로그인 → 되면 **영구 저장 성공**

---

## 체크리스트

- [ ] Neon 프로젝트 생성
- [ ] Connection string 복사
- [ ] Render → Environment → `DATABASE_URL` 추가
- [ ] 재배포 완료
- [ ] `/health` 에 `"database": "postgresql"`
- [ ] 회원가입 후 재로그인 테스트

---

## 주의

- Neon **비밀번호/주소는 GitHub에 올리지 마세요** (Render Environment에만 넣기)
- 무료 Neon·Render는 트래픽·용량 제한이 있으나 **과제·동아리 사용**에는 보통 충분합니다
- 코드 수정 후에는 `git push`만 하면 Render가 자동 재배포합니다 (`DATABASE_URL`은 그대로 유지)

# WOOWANGTHON_TEAM_02_BE

공지 알리미 FastAPI 백엔드.
인증, PostgreSQL 데이터, 공지 수집·태깅·추천 API, 현재 통합 웹 앱

## 로컬 실행

1. `.env.example`을 복사해 `.env`를 만들고 `POSTGRES_PASSWORD`, 32자 이상의 `JWT_SECRET`을 설정합니다.
2. Docker Desktop을 실행하고 `docker compose up --build`를 실행합니다.
3. `http://localhost:8000`에서 화면 확인. `/docs`는 API 문서, `/health`는 DB 연결 상태입니다.

## 폴더

- `app/auth`, `app/notices`, `app/crawler`, `app/tagging`: 백엔드 기능
- `app/db`, `db`: PostgreSQL 연결, 마이그레이션, 시드 데이터
- `app/templates`, `app/static`: 통합 앱이 렌더링하는 웹 화면 (FE 저장소의 화면과 동기화)
- `app/chatbot`: 공지 후보 선별과 기존 LLM 어댑터

FE 화면 소스는 `WOOWANGTHON_TEAM_02_FE` 저장소에서 관리합니다. 화면을 수정하면 FE의 `templates/`, `static/` 내용을 이 저장소의 `app/templates/`, `app/static/`에도 반영해야 통합 앱에 적용됩니다.

AI 독립 서비스의 요청 계약은 AI 저장소의 README를 참고하세요.

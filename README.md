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
- `app/chatbot`: 로그인 사용자의 공지 근거 선별 및 독립 AI 서비스 호출

FE 화면 소스는 `WOOWANGTHON_TEAM_02_FE` 저장소에서 관리합니다. 화면을 수정하면 FE의 `templates/`, `static/` 내용을 이 저장소의 `app/templates/`, `app/static/`에도 반영해야 통합 앱에 적용됩니다.

AI 답변·생성형 요약·게시판 selector 제안은 별도 `WOOWANGTHON_TEAM_02_AI` 서비스가 담당합니다. BE는 로그인/학교별 접근 권한을 확인하고 공지 근거를 선별한 뒤 AI API를 호출합니다. 로컬에서는 AI 저장소를 포트 8001로 실행하고, 이 프로젝트 `.env`의 `AI_SERVICE_URL` 및 `AI_SERVICE_TOKEN`을 맞춰 설정하세요. 제공자 API 키(`LLM_API_KEY`)는 AI 서비스의 `.env`에만 저장합니다. API 계약과 실행 방법은 AI 저장소 README를 참고하세요.

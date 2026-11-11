# WOOWANGTHON_TEAM_02_BE

충북대학교 공지 알리미의 FastAPI 백엔드입니다. 인증, PostgreSQL 데이터, 공지 수집·태깅·추천 API와 현재 통합 웹 앱을 담당합니다.

## 로컬 실행

1. `.env.example`을 복사해 `.env`를 만들고 `POSTGRES_PASSWORD`, 32자 이상의 `JWT_SECRET`을 설정합니다.
2. Docker Desktop을 실행하고 `docker compose up --build`를 실행합니다.
3. `http://localhost:8000`에서 화면을 확인합니다. `/docs`는 API 문서, `/health`는 DB 연결 상태입니다.

## 폴더

- `app/auth`, `app/notices`, `app/crawler`, `app/tagging`: 백엔드 기능
- `app/db`, `db`: PostgreSQL 연결, 마이그레이션, 시드 데이터
- `app/templates`, `app/static`: 통합 앱이 렌더링하는 웹 화면
- `app/chatbot`: 공지 후보 선별과 기존 LLM 어댑터

웹 화면 소스는 FE 저장소에도 분리해 보관합니다. 현 단계에서 BE가 Jinja 화면을 직접 렌더링하기 때문에 실행 가능한 통합 상태를 보존하려고 화면 파일을 BE에도 포함했습니다. 화면을 변경할 때는 FE 저장소와 동기화해 주세요. 후속 분리에서는 FE를 독립 앱으로 전환하고 BE 인증을 JSON API로 제공해야 합니다.

AI 독립 서비스의 요청 계약은 AI 저장소의 README에 있습니다. 현재 BE는 해당 서비스에 아직 연결되어 있지 않습니다.

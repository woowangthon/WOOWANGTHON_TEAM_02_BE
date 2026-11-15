# BE 인수인계

## 저장소 역할과 공통 구조

- BE는 통합 웹 앱의 진입점이며 사용자는 `http://localhost:8000`으로 접속합니다.
- Python 3.12, FastAPI, Jinja2, psycopg 3 raw SQL, PostgreSQL 16, Docker Compose를 사용합니다.
- 사용자 인증, 학교별 접근 권한, 공지 DB, 수집·태깅·추천, API를 맡습니다.
- FE 브라우저 요청은 BE에만 들어옵니다. AI 서비스는 브라우저에 공개하지 않습니다.
- FE 화면 원본은 별도 FE 저장소의 `templates/`, `static/`입니다. 통합 앱에는 `app/templates/`, `app/static/` 복사본이 필요하므로 FE 화면 변경과 함께 동기화합니다.
- 독립 AI 서비스 코드는 별도 AI 저장소에 있습니다. AI가 DB, 계정 인증, 공지 접근 권한을 직접 처리하지 않습니다.

## AI 연동 책임

1. BE는 로그인 사용자의 학교와 권한을 확인합니다.
2. BE가 DB에서 허용된 공지를 검색·선별합니다.
3. BE가 질문과 선별된 공지 근거만 AI 서비스에 전송합니다.
4. AI는 답변·생성형 요약·selector 후보를 반환하고, BE가 브라우저 응답을 구성합니다.

AI 서비스 기본 주소는 `http://host.docker.internal:8001`이며 Docker Compose의 BE 컨테이너에서 호출합니다. 실행 환경에 맞게 `AI_SERVICE_URL`을 설정하세요. BE의 `.env`와 AI의 `.env`에는 같은 `AI_SERVICE_TOKEN`이 필요합니다. 모델 제공자 키(`LLM_API_KEY`)는 AI 서비스에만 저장합니다.

주요 BE 연동 코드는 `app/chatbot/ai_service.py`입니다. provider SDK와 프롬프트는 BE에 두지 않습니다. 게시판 selector 요청도 AI API에 위임하며, selector 후보의 실제 유효성은 BE의 파서로 검사합니다.

## 주요 기능과 경로

- 인증: `app/auth/`; JWT access token을 httpOnly 쿠키로 사용하고 비밀번호는 Argon2로 해시합니다.
- DB: `app/db/`, `db/migrations/`, `db/seeds/`. 스키마는 PostgreSQL 16이며 ORM 대신 psycopg raw SQL을 사용합니다.
- 공지: `app/notices/`; 목록, 상세, 저장/해제, 개인화 추천 API
- 챗봇: `app/chatbot/candidates.py`에서 사용자 학교 공지를 선별하고, `app/chatbot/ai_service.py`가 답변·요약 요청을 보냅니다.
- 크롤러: `app/crawler/`; 공개 게시판 파싱, 공지 수집, 등록 CLI
- 확장프로그램 및 가져오기: `notice_ingestion/`, `app/static/js/extension-import.js`, 관련 API
- AI URL 등록/수집 정책은 `parser_config.terms_checked=true`가 확인되기 전 네트워크 요청을 금지합니다. 크롤러는 공지 출처 설정의 호스트와 robots 정책을 확인해야 합니다.

## 로컬 실행

1. `BE/.env.example`을 `BE/.env`로 복사하고 PostgreSQL 비밀번호와 32자 이상의 `JWT_SECRET`을 설정합니다.
2. `AI_SERVICE_URL`과 `AI_SERVICE_TOKEN`을 설정합니다.
3. `AI/.env.example`을 `AI/.env`로 복사하고 같은 `AI_SERVICE_TOKEN`, AI 제공자와 `LLM_API_KEY`를 설정합니다.
4. AI 서비스를 포트 8001에서 실행합니다.
5. Docker Desktop에서 BE 디렉터리 기준 `docker compose up --build`를 실행합니다. 웹은 `http://localhost:8000`에 표시됩니다. DB 마이그레이션은 앱 시작 시 적용됩니다.
6. 초기 학교·학과·공지 데이터가 필요하면 `docker compose exec app python -m app.db.seed`를 실행합니다.

실제 API 키는 `.env` 파일에만 두고 커밋하지 않습니다. `.env.example`에는 placeholder만 기록합니다.

## GitHub 및 현재 상태

- 이 저장소의 기본 게시 브랜치는 `main`입니다.
- AI 서비스 책임 분리 커밋 `6768a02`까지 `main`에 푸시되어 있습니다.
- FE와 AI 변경은 각 저장소의 `main`에 따로 커밋·푸시합니다.
- 자동 테스트는 마지막 구조 변경에서 실행하지 않았습니다. 배포 전 로그인, 공지 권한, 저장 공지, 챗봇 답변, 요약, 확장프로그램 경로를 실행 환경에서 확인합니다.

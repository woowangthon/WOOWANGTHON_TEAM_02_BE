# Railway 배포 안내

이 저장소는 공개 웹 앱(BE)용입니다. AI 서비스는 별도 `WOOWANGTHON_TEAM_02_AI` 저장소에서 비공개 서비스로 배포합니다. PostgreSQL은 Railway의 별도 데이터베이스 서비스로 추가합니다.

## 서비스 구성

1. Railway에서 프로젝트를 만들고 PostgreSQL 서비스를 추가합니다.
2. GitHub 저장소 `woowangthon/WOOWANGTHON_TEAM_02_AI`를 연결해 `ai` 서비스를 만듭니다. 공개 도메인은 만들지 않습니다. `PORT=8001`을 지정합니다.
3. AI 서비스 변수에 `LLM_PROVIDER=google`, `LLM_MODEL=gemini-3.5-flash-lite`, `LLM_API_KEY`, `AI_SERVICE_TOKEN`을 설정합니다. 토큰은 BE와 동일한 임의의 긴 비밀값을 사용합니다.
4. GitHub 저장소 `woowangthon/WOOWANGTHON_TEAM_02_BE`를 연결해 `app` 서비스를 만듭니다. 이 앱에만 공개 도메인을 생성합니다.
5. BE 서비스 변수에 PostgreSQL 서비스의 `DATABASE_URL` 참조, `JWT_SECRET`(임의의 긴 비밀값), `COOKIE_SECURE=true`, `AI_SERVICE_TOKEN`을 설정합니다.
6. AI의 Railway 사설 도메인을 확인하고 BE의 `AI_SERVICE_URL`을 `http://<AI 서비스의 사설 도메인>:8001`로 설정합니다. 도메인은 `ai.railway.internal` 형식입니다.
7. BE 배포가 완료되면 공개 주소의 `/health`가 `{"status":"ok"}`를 반환하는지 확인합니다.

BE 컨테이너는 시작할 때 데이터베이스 마이그레이션을 적용합니다. Railway가 제공하는 `PORT` 환경변수를 사용합니다. AI 서비스는 8001 포트에서 사설 네트워크 요청을 받습니다.

실제 LLM 호출에는 제공자 사용량 요금이 별도로 발생할 수 있습니다. Railway 체험 크레딧과 제공자 API 사용량을 각각 확인하세요. 비밀값은 저장소 파일에 넣거나 커밋하지 마세요.

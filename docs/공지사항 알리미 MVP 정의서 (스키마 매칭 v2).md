# 공지사항 알리미 MVP 정의서 (스키마 매칭 v2)

`schema.sql` / `erd.mermaid` 기준으로 MVP 기능을 테이블·컬럼과 1:1로 매칭한 문서입니다.

## 0. 설계 검증 결과

- PostgreSQL 16에서 `schema.sql` 전체 실행을 확인했습니다. 샘플 데이터로 추천 쿼리와 제약조건도 검증했습니다.
- 검증 중 발견해 수정한 허점 3건입니다.
  1. **학교-학과 불일치:** A대 사용자에게 B대 학과를 지정할 수 있었습니다. `users (school_id, department_id)`를 `departments (school_id, id)`에 복합 FK로 묶어 해결했습니다.
  2. **단과대 대상 공지 누락:** 상위 학부(단과대) 대상 공지가 소속 학과 학생에게 매칭되지 않았습니다. 추천 쿼리에 상위 학과 재귀 조회(`my_depts`)를 추가했습니다.
  3. **`chat_sessions.updated_at` 미갱신:** 트리거를 추가했습니다.

## 1. MVP 목표

사용자가 회원가입 후 학교 공지를 한곳에서 확인하고, 본인에게 맞는 공지를 추천받고, 챗봇에게 자연어로 질문해 필요한 공지를 찾을 수 있게 합니다.

## 2. 확정된 설계 결정

| 쟁점 | 결정 | 스키마 반영 |
| --- | --- | --- |
| 공지 대상·주제 얻는 법 | 키워드 규칙 기반 자동 태깅 | `tag_keywords`, `notice_tags.origin`, `notice_targets.origin` |
| 추천 결과 저장 | 저장하지 않고 실시간 계산 | 추천용 테이블 없음 |
| 챗봇 대화 이력 | 저장 | `chat_sessions`, `chat_messages`, `chat_message_sources` |
| 마감일 | MVP 제외 | `notices.deadline_at` 컬럼만 예약 |
| 지원 범위 | 학교 1\~2곳, 게시판 제한 | `schools`, `notice_sources` 시드 데이터 |

## 3. In-Scope 기능 ↔ 스키마 매칭

### F1. 회원가입 / 로그인

| 구분 | 내용 |
| --- | --- |
| 입력 | 이메일, 비밀번호, 학교, 학과·학부, 학년, 관심 분야(복수) |
| 저장 | `users` (email, password\_hash, school\_id, department\_id, grade), `user_interests` (user\_id, tag\_id) |
| 규칙 | 이메일은 대소문자 구분 없이 중복 불가 (`uq_users_email`). 학과는 선택한 학교 소속만 가능 (복합 FK). 관심 분야는 `tags.is_user_selectable = true`인 태그에서만 선택. 로그인은 `status = 'active'`만 허용하고 `last_login_at`을 갱신 |
| 제외 | 이메일 인증, 비밀번호 찾기, 권한 관리 |

### F2. 학교 공식 홈페이지 공지 수집

| 구분 | 내용 |
| --- | --- |
| 수집 대상 | `notice_sources` (school\_id, name, list\_url, parser\_config, crawl\_interval\_minutes, is\_active) |
| 수집 필드 | 제목 `notices.title`, 본문 `notices.content`, 게시일 `notices.posted_at`, 분류 `notice_categories.name` → `notices.category_id`, 원문 링크 `notices.original_url` |
| 주기 실행 | `last_crawled_at` + `crawl_interval_minutes` 기준으로 대상 선정. 실행마다 `crawl_runs`에 기록 (status, fetched/new/updated\_count, error\_message) |
| 중복 방지 | `UNIQUE (source_id, external_id)`. 글번호가 없으면 원문 URL 해시를 `external_id`로 사용 |
| 변경 감지 | `content_hash`가 달라지면 본문을 갱신하고 태깅을 다시 수행. 게시판에서 사라진 글은 `status = 'removed'` |
| 자동 태깅 | `tag_keywords`와 제목·본문을 매칭해 `notice_tags (origin='rule')` 생성. 학과명이 등장하면 `notice_targets.department_id`, "N학년" 패턴이 있으면 `notice_targets.grade`를 생성 |

### F3. 공지사항 통합 목록 / 상세

| 구분 | 내용 |
| --- | --- |
| 목록 | `notices` 중 `status = 'active'`이고 `notice_sources.school_id = 내 학교`인 공지. `posted_at DESC` 정렬, 페이지네이션 |
| 표시 | 제목, 게시일, 분류(`notice_categories.name`), 본문 미리보기(`left(content, N)`을 쿼리에서 계산) |
| 필터 | 분류 (`category_id`) |
| 상세 | `content` 전체 + `original_url` 원문 링크 |
| 인덱스 | `idx_notices_posted`, `idx_notices_source_posted`, `idx_notices_category` |

### F4. 사용자 정보 기반 추천

| 구분 | 내용 |
| --- | --- |
| 비교 대상 | 사용자: `users.department_id`, `users.grade`, `user_interests`. 공지: `notice_targets`, `notice_tags` |
| 점수 | 학과 일치 +3 (상위 학부 대상도 포함), 학년 일치 +2, 관심 분야 태그당 +2 |
| 제외 | 다른 학과·학년만 대상인 공지는 노출하지 않음. `notice_targets` 행이 없으면 전체 대상으로 취급 |
| 추천 이유 | 일치한 관심 분야 이름(`matched_interests`)으로 "관심 분야 'OO' 관련" 문구 생성. 학과·학년 일치도 문구로 표시 |
| 저장 | 없음 (요청 시 계산). 쿼리는 `schema.sql` 하단 참고 |

### F5. 공지사항 질문 챗봇

| 단계 | 처리 | 테이블 |
| --- | --- | --- |
| 1 | 질문 저장 | `chat_sessions`(없으면 생성), `chat_messages (role='user')` |
| 2 | 질문에서 키워드·주제를 뽑아 관련 공지 N개(예: 5개) 선별. 태그 매칭과 `pg_trgm` 제목·본문 검색을 함께 사용하고 내 학교 공지만 대상 | `notice_tags`, `notices` (`idx_notices_title_trgm`, `idx_notices_content_trgm`) |
| 3 | 선별된 공지 + 사용자 프로필(학과·학년·관심 분야)만 생성형 AI API에 전달. API 키는 서버 환경변수로 관리하고 DB에는 저장하지 않음 | `users`, `user_interests` |
| 4 | 답변 저장. 사용한 모델명과 토큰 수를 기록 | `chat_messages (role='assistant', model, prompt_tokens, completion_tokens)` |
| 5 | 근거 공지의 제목·원문 링크를 답변과 함께 표시 | `chat_message_sources (message_id, notice_id, rank, relevance_score)` → `notices.title`, `original_url` |
| 6 | 근거가 없으면 "확인할 수 없다"고 답하고 추측하지 않음 | `chat_messages.is_grounded = false`, `chat_message_sources` 행 없음 |

### F6. 관련 공지 선별 후 AI 답변 생성

- F5의 2\~3단계와 같은 기능입니다. 키워드·주제 기준으로 후보를 먼저 추리고, 해당 공지 내용만 API에 전달합니다.
- 전체 공지를 API에 보내지 않으므로 비용과 오답 위험이 줄어듭니다.

## 4. Out-of-Scope ↔ 후속 확장 포인트

| 미룬 기능 | 후속 추가 시 사용할 구조 (MVP에서는 비워 둠) |
| --- | --- |
| LMS 공지 수집 | `notice_sources.source_type = 'lms'`, `requires_auth` |
| 임의 사이트 링크 수집 | `source_type = 'custom_url'`, `parser_config`(JSONB), `created_by_user_id` |
| 이미지·첨부파일 분석 | `notice_attachments` (extracted\_text, extract\_status) |
| 캘린더 연동·일정 등록 | `notice_events` (starts\_at, ends\_at, event\_type), `notices.deadline_at` |
| 고도화 개인화 추천 | `user_notice_interactions` (view, click\_original, bookmark, dismiss) |
| 계정·보안 고도화 | `users.role`, `users.status`, `user_identities` (소셜·학교 SSO) |

## 5. 알려진 한계 (구현 시 주의)

- `notice_targets`의 학과가 공지 출처 학교와 같은 학교인지는 DB가 강제하지 않습니다. 태깅 로직에서 같은 학교의 학과만 매칭하세요.
- `chat_message_sources`는 assistant 메시지에만 연결해야 하지만 DB가 강제하지 않습니다. 애플리케이션에서 지켜 주세요.
- 로그인을 JWT로 구현하면 추가 테이블이 필요 없습니다. 서버 세션이나 리프레시 토큰을 DB에 저장하려면 `sessions` 테이블을 추가해야 합니다.
- `pg_trgm` 검색은 MVP 규모(수천\~수만 건)에서는 충분합니다. 공지가 크게 늘면 전문검색 엔진 도입을 검토하세요.
- 키워드 기반 태깅은 정확도에 한계가 있습니다. 필요해지면 `origin = 'ai'` 태깅을 추가하세요.

-- =====================================================================
-- 공지사항 알리미 - PostgreSQL 스키마 (MVP + 확장 대비)
-- 규칙
--  * PK: BIGINT GENERATED ALWAYS AS IDENTITY
--  * 열거형은 ENUM 타입 대신 TEXT + CHECK (값 추가 시 마이그레이션이 쉬움)
--  * 시간은 TIMESTAMPTZ
--  * [MVP] = 이번 범위에서 사용 / [FUTURE] = 구조만 준비, MVP에서는 비워 둠
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 한국어 부분 일치 검색용

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 1. 학교 / 학과  [MVP]
-- ---------------------------------------------------------------------
CREATE TABLE schools (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name          TEXT        NOT NULL UNIQUE,
  homepage_url  TEXT,
  is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 학부/단과대 -> 학과 계층을 parent_id 로 표현
CREATE TABLE departments (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  school_id   BIGINT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  parent_id   BIGINT REFERENCES departments(id) ON DELETE SET NULL,
  name        TEXT   NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_id, name),
  UNIQUE (school_id, id)          -- users 의 복합 FK 대상
);
CREATE INDEX idx_departments_school ON departments(school_id);

-- ---------------------------------------------------------------------
-- 2. 사용자  [MVP]
-- ---------------------------------------------------------------------
CREATE TABLE users (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email          TEXT     NOT NULL,
  password_hash  TEXT     NOT NULL,
  school_id      BIGINT   NOT NULL REFERENCES schools(id),
  department_id  BIGINT   NOT NULL,
  grade          SMALLINT NOT NULL CHECK (grade BETWEEN 1 AND 6),
  role           TEXT     NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
  status         TEXT     NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deleted')),
  last_login_at  TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- 다른 학교의 학과를 지정하지 못하게 강제
  FOREIGN KEY (school_id, department_id) REFERENCES departments (school_id, id)
);
CREATE UNIQUE INDEX uq_users_email ON users (lower(email));
CREATE INDEX idx_users_school_dept ON users (school_id, department_id);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- [FUTURE] 소셜 로그인 / 학교 SSO: users 수정 없이 추가
CREATE TABLE user_identities (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider          TEXT   NOT NULL,            -- 'google', 'kakao', 'school_sso' ...
  provider_user_id  TEXT   NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_user_id)
);

-- ---------------------------------------------------------------------
-- 3. 태그 (관심 분야 = 공지 주제 가 같은 체계)  [MVP]
-- ---------------------------------------------------------------------
CREATE TABLE tags (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code                  TEXT    NOT NULL UNIQUE,     -- 'campus_activity', 'scholarship' ...
  name                  TEXT    NOT NULL,            -- 화면 표시용 (교내 활동, 장학 ...)
  is_user_selectable    BOOLEAN NOT NULL DEFAULT TRUE,  -- 회원가입 관심 분야로 노출할지
  sort_order            INT     NOT NULL DEFAULT 0,
  is_active             BOOLEAN NOT NULL DEFAULT TRUE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 규칙 기반 자동 태깅용 키워드 (코드 수정 없이 데이터로 관리)
CREATE TABLE tag_keywords (
  id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tag_id    BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  keyword   TEXT   NOT NULL,
  weight    SMALLINT NOT NULL DEFAULT 1,
  UNIQUE (tag_id, keyword)
);

CREATE TABLE user_interests (
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tag_id      BIGINT NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, tag_id)
);
CREATE INDEX idx_user_interests_tag ON user_interests(tag_id);

-- ---------------------------------------------------------------------
-- 4. 수집 대상 (학교 + 게시판)  [MVP]
--    source_type 으로 LMS / 임의 사이트도 같은 테이블에서 확장
-- ---------------------------------------------------------------------
CREATE TABLE notice_sources (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  school_id               BIGINT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  name                    TEXT   NOT NULL,                 -- '학사공지', '장학공지' ...
  source_type             TEXT   NOT NULL DEFAULT 'school_website'
                          CHECK (source_type IN ('school_website','lms','custom_url')),
  list_url                TEXT   NOT NULL,
  parser_config           JSONB  NOT NULL DEFAULT '{}'::jsonb,  -- 선택자, 페이지 규칙 등
  requires_auth           BOOLEAN NOT NULL DEFAULT FALSE,       -- [FUTURE] LMS
  crawl_interval_minutes  INT    NOT NULL DEFAULT 60 CHECK (crawl_interval_minutes > 0),
  is_active               BOOLEAN NOT NULL DEFAULT TRUE,
  last_crawled_at         TIMESTAMPTZ,
  created_by_user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL, -- [FUTURE] 사용자 링크 등록
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_id, list_url)
);
CREATE TRIGGER trg_sources_updated BEFORE UPDATE ON notice_sources
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE notice_categories (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id  BIGINT NOT NULL REFERENCES notice_sources(id) ON DELETE CASCADE,
  name       TEXT   NOT NULL,
  UNIQUE (source_id, name)
);

-- 수집 실행 기록
CREATE TABLE crawl_runs (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id      BIGINT NOT NULL REFERENCES notice_sources(id) ON DELETE CASCADE,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ,
  status         TEXT NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running','success','partial','failed')),
  fetched_count  INT NOT NULL DEFAULT 0,
  new_count      INT NOT NULL DEFAULT 0,
  updated_count  INT NOT NULL DEFAULT 0,
  error_message  TEXT
);
CREATE INDEX idx_crawl_runs_source ON crawl_runs(source_id, started_at DESC);

-- ---------------------------------------------------------------------
-- 5. 공지  [MVP]
-- ---------------------------------------------------------------------
CREATE TABLE notices (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id     BIGINT NOT NULL REFERENCES notice_sources(id) ON DELETE CASCADE,
  category_id   BIGINT REFERENCES notice_categories(id) ON DELETE SET NULL,
  external_id   TEXT   NOT NULL,        -- 게시판 글번호. 없으면 원문 URL 해시 사용
  title         TEXT   NOT NULL,
  content       TEXT   NOT NULL DEFAULT '',
  summary       TEXT   NOT NULL DEFAULT '',
  original_url  TEXT   NOT NULL,
  posted_at     TIMESTAMPTZ NOT NULL,
  content_hash  TEXT,                   -- 본문 변경 감지 (변경 시 갱신 + 재태깅)
  deadline_at   TIMESTAMPTZ,            -- [FUTURE] 마감일 추출
  status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','removed')),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)       -- 중복 수집 방지
);
CREATE INDEX idx_notices_posted        ON notices (posted_at DESC) WHERE status = 'active';
CREATE INDEX idx_notices_source_posted ON notices (source_id, posted_at DESC);
CREATE INDEX idx_notices_category      ON notices (category_id);
CREATE INDEX idx_notices_title_trgm    ON notices USING gin (title   gin_trgm_ops);
CREATE INDEX idx_notices_content_trgm  ON notices USING gin (content gin_trgm_ops);
CREATE TRIGGER trg_notices_updated BEFORE UPDATE ON notices
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 공지 <-> 주제 태그 (추천/챗봇 후보 선별에 사용)
CREATE TABLE notice_tags (
  notice_id   BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  tag_id      BIGINT NOT NULL REFERENCES tags(id)    ON DELETE CASCADE,
  origin      TEXT   NOT NULL DEFAULT 'rule' CHECK (origin IN ('rule','ai','manual')),
  confidence  REAL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (notice_id, tag_id)
);
CREATE INDEX idx_notice_tags_tag ON notice_tags(tag_id);

-- 공지 대상 (학과/학년). 행이 하나도 없으면 '전체 대상'
CREATE TABLE notice_targets (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  notice_id      BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  department_id  BIGINT REFERENCES departments(id) ON DELETE CASCADE,  -- NULL = 모든 학과
  grade          SMALLINT CHECK (grade BETWEEN 1 AND 6),               -- NULL = 모든 학년
  origin         TEXT NOT NULL DEFAULT 'rule' CHECK (origin IN ('rule','ai','manual')),
  CHECK (department_id IS NOT NULL OR grade IS NOT NULL)
);
CREATE UNIQUE INDEX uq_notice_targets
  ON notice_targets (notice_id, COALESCE(department_id, 0), COALESCE(grade, 0));
CREATE INDEX idx_notice_targets_dept ON notice_targets(department_id);

-- [FUTURE] 첨부파일 / 이미지 내용 분석
CREATE TABLE notice_attachments (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  notice_id       BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  kind            TEXT   NOT NULL CHECK (kind IN ('file','image')),
  file_name       TEXT,
  file_url        TEXT   NOT NULL,
  mime_type       TEXT,
  extracted_text  TEXT,
  extract_status  TEXT NOT NULL DEFAULT 'pending'
                  CHECK (extract_status IN ('pending','done','failed','skipped')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notice_attachments_notice ON notice_attachments(notice_id);

-- [FUTURE] 공지에서 추출한 일정 -> 캘린더 연동
CREATE TABLE notice_events (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  notice_id   BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  title       TEXT   NOT NULL,
  event_type  TEXT   NOT NULL DEFAULT 'etc'
              CHECK (event_type IN ('deadline','event','application','etc')),
  starts_at   TIMESTAMPTZ,
  ends_at     TIMESTAMPTZ,
  location    TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notice_events_notice ON notice_events(notice_id);

-- ---------------------------------------------------------------------
-- 6. 사용자-공지 상호작용  [FUTURE] 고도화 개인화 추천용 (조회/클릭/북마크)
-- ---------------------------------------------------------------------
CREATE TABLE user_notice_interactions (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
  notice_id   BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
  action      TEXT   NOT NULL CHECK (action IN ('view','click_original','bookmark','dismiss')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_interactions_user   ON user_notice_interactions(user_id, created_at DESC);
CREATE INDEX idx_interactions_notice ON user_notice_interactions(notice_id);

-- ---------------------------------------------------------------------
-- 7. 챗봇  [MVP]
-- ---------------------------------------------------------------------
CREATE TABLE chat_sessions (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id, updated_at DESC);
CREATE TRIGGER trg_chat_sessions_updated BEFORE UPDATE ON chat_sessions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE chat_messages (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id         BIGINT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role               TEXT   NOT NULL CHECK (role IN ('user','assistant')),
  content            TEXT   NOT NULL,
  is_grounded        BOOLEAN,              -- assistant: 근거 공지로 답했는지 (FALSE = '확인할 수 없음' 응답)
  model              TEXT,                 -- 사용한 생성형 AI 모델명
  prompt_tokens      INT,
  completion_tokens  INT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id, created_at);

-- 답변의 근거가 된 공지 (제목 + 원문 링크 표시용)
CREATE TABLE chat_message_sources (
  message_id       BIGINT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  notice_id        BIGINT NOT NULL REFERENCES notices(id)       ON DELETE CASCADE,
  rank             SMALLINT NOT NULL DEFAULT 1,
  relevance_score  REAL,
  PRIMARY KEY (message_id, notice_id)
);
CREATE INDEX idx_chat_sources_notice ON chat_message_sources(notice_id);

-- ---------------------------------------------------------------------
-- 시드 예시 (태그)
-- ---------------------------------------------------------------------
INSERT INTO tags (code, name, sort_order) VALUES
  ('campus_activity', '교내 활동', 1),
  ('scholarship',     '장학',     2),
  ('contest',         '공모전·대회', 3),
  ('career',          '취업·진로', 4),
  ('academic',        '학사',     5),
  ('exchange',        '교환·해외', 6);

-- =====================================================================
-- 참고: 추천 쿼리 (추천 결과는 저장하지 않고 실시간 계산)
-- :uid = 로그인 사용자 id
--  * 공지에 notice_targets 행이 없으면 '전체 대상'
--  * 단과대(상위 학과) 대상 공지도 소속 학과 학생에게 매칭 (my_depts = 본인 학과 + 상위 학과들)
-- =====================================================================
/*
WITH RECURSIVE me AS (
  SELECT id, school_id, department_id, grade FROM users WHERE id = :uid
), my_depts AS (
  SELECT d.id, d.parent_id FROM departments d JOIN me ON d.id = me.department_id
  UNION ALL
  SELECT p.id, p.parent_id FROM departments p JOIN my_depts c ON p.id = c.parent_id
)
SELECT n.id, n.title, n.posted_at, n.original_url,
  ( 3 * EXISTS (SELECT 1 FROM notice_targets t
                WHERE t.notice_id = n.id AND t.department_id IN (SELECT id FROM my_depts))::int
  + 2 * EXISTS (SELECT 1 FROM notice_targets t, me
                WHERE t.notice_id = n.id AND t.grade = me.grade)::int
  + 2 * (SELECT count(*) FROM notice_tags nt
         JOIN user_interests ui ON ui.tag_id = nt.tag_id AND ui.user_id = :uid
         WHERE nt.notice_id = n.id)
  ) AS score,
  ARRAY(SELECT tg.name FROM notice_tags nt
        JOIN user_interests ui ON ui.tag_id = nt.tag_id AND ui.user_id = :uid
        JOIN tags tg ON tg.id = nt.tag_id
        WHERE nt.notice_id = n.id) AS matched_interests   -- 추천 이유 표시용
FROM notices n
JOIN notice_sources s ON s.id = n.source_id
JOIN me ON s.school_id = me.school_id
WHERE n.status = 'active'
  AND ( NOT EXISTS (SELECT 1 FROM notice_targets t WHERE t.notice_id = n.id)
        OR EXISTS (SELECT 1 FROM notice_targets t
                   WHERE t.notice_id = n.id
                     AND (t.department_id IS NULL OR t.department_id IN (SELECT id FROM my_depts))
                     AND (t.grade IS NULL OR t.grade = me.grade)) )
ORDER BY score DESC, n.posted_at DESC
LIMIT 20;
*/

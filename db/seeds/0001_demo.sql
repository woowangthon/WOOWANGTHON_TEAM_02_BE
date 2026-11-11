-- 반복 실행해도 같은 데모 구성을 유지하는 개발용 시드.
-- .invalid 도메인은 실제 학교 사이트가 아니므로 크롤링하지 않는다.

INSERT INTO schools (name, homepage_url, is_active)
VALUES ('우왕톤 데모대학교', 'https://demo-university.invalid', TRUE)
ON CONFLICT (name) DO UPDATE
SET homepage_url = EXCLUDED.homepage_url,
    is_active = EXCLUDED.is_active;

INSERT INTO departments (school_id, parent_id, name)
SELECT s.id, NULL, '공과대학'
FROM schools AS s
WHERE s.name = '우왕톤 데모대학교'
ON CONFLICT (school_id, name) DO UPDATE
SET parent_id = EXCLUDED.parent_id;

INSERT INTO departments (school_id, parent_id, name)
SELECT s.id, p.id, '컴퓨터공학과'
FROM schools AS s
JOIN departments AS p ON p.school_id = s.id AND p.name = '공과대학'
WHERE s.name = '우왕톤 데모대학교'
ON CONFLICT (school_id, name) DO UPDATE
SET parent_id = EXCLUDED.parent_id;

INSERT INTO departments (school_id, parent_id, name)
SELECT s.id, NULL, '인문대학'
FROM schools AS s
WHERE s.name = '우왕톤 데모대학교'
ON CONFLICT (school_id, name) DO UPDATE
SET parent_id = EXCLUDED.parent_id;

INSERT INTO departments (school_id, parent_id, name)
SELECT s.id, p.id, '국어국문학과'
FROM schools AS s
JOIN departments AS p ON p.school_id = s.id AND p.name = '인문대학'
WHERE s.name = '우왕톤 데모대학교'
ON CONFLICT (school_id, name) DO UPDATE
SET parent_id = EXCLUDED.parent_id;

INSERT INTO notice_sources (school_id, name, list_url, parser_config, is_active)
SELECT s.id,
       '데모 공지사항',
       'https://demo-university.invalid/notices',
       '{}'::jsonb,
       TRUE
FROM schools AS s
WHERE s.name = '우왕톤 데모대학교'
ON CONFLICT (school_id, list_url) DO UPDATE
SET name = EXCLUDED.name,
    parser_config = EXCLUDED.parser_config,
    is_active = EXCLUDED.is_active;

INSERT INTO notice_categories (source_id, name)
SELECT ns.id, category.name
FROM notice_sources AS ns
JOIN schools AS s ON s.id = ns.school_id
CROSS JOIN (VALUES ('일반공지'), ('학사공지'), ('장학공지')) AS category(name)
WHERE s.name = '우왕톤 데모대학교'
  AND ns.list_url = 'https://demo-university.invalid/notices'
ON CONFLICT (source_id, name) DO NOTHING;

INSERT INTO tags (code, name, sort_order, is_user_selectable, is_active)
VALUES
    ('campus_activity', '교내 활동', 1, TRUE, TRUE),
    ('scholarship', '장학', 2, TRUE, TRUE),
    ('contest', '공모전·대회', 3, TRUE, TRUE),
    ('career', '취업·진로', 4, TRUE, TRUE),
    ('academic', '학사', 5, TRUE, TRUE),
    ('exchange', '교환·해외', 6, TRUE, TRUE)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name,
    sort_order = EXCLUDED.sort_order,
    is_user_selectable = EXCLUDED.is_user_selectable,
    is_active = EXCLUDED.is_active;

INSERT INTO tag_keywords (tag_id, keyword, weight)
SELECT t.id, keyword.keyword, keyword.weight
FROM tags AS t
JOIN (VALUES
    ('campus_activity', '동아리', 2),
    ('campus_activity', '학생회', 2),
    ('campus_activity', '교내 프로그램', 2),
    ('scholarship', '장학금', 3),
    ('scholarship', '장학생', 2),
    ('scholarship', '학자금', 2),
    ('contest', '공모전', 3),
    ('contest', '경진대회', 3),
    ('contest', '아이디어 대회', 2),
    ('career', '취업', 2),
    ('career', '인턴', 2),
    ('career', '채용', 2),
    ('academic', '수강신청', 3),
    ('academic', '학사일정', 2),
    ('academic', '휴학', 2),
    ('exchange', '교환학생', 3),
    ('exchange', '해외연수', 2),
    ('exchange', '국제교류', 2)
) AS keyword(code, keyword, weight) ON keyword.code = t.code
ON CONFLICT (tag_id, keyword) DO UPDATE
SET weight = EXCLUDED.weight;

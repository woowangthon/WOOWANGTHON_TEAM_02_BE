-- 공식 컴퓨터공학과 홈페이지 첫 화면에 공개된 학부 공지 링크를 수집한다.
-- 상세 게시판 경로가 외부에서 404를 반환해 첫 화면의 공지 제목·원문 링크·게시일만 사용한다.
WITH cbnu AS (
    SELECT id FROM schools WHERE name = '충북대학교'
)
INSERT INTO notice_sources (
    school_id, name, source_type, list_url, parser_config,
    is_active, crawl_interval_minutes
)
SELECT cbnu.id,
       '컴퓨터공학과 공지',
       'school_website',
       'https://computer.cbnu.ac.kr/',
       '{
         "terms_checked": false,
         "operator_directed_public_content": true,
         "source_scope": "department",
         "target_department_name": "컴퓨터공학과",
         "item_selector": "span.defaulttabshowlist_subject",
         "title_selector": "a",
         "link_selector": "a",
         "date_from_ancestor": true,
         "item_limit": 10,
         "id_query_parameter": "no",
         "max_pages": 1,
         "complete_snapshot": false
       }'::jsonb,
       TRUE,
       60
FROM cbnu
ON CONFLICT (school_id, list_url) DO UPDATE
SET name = EXCLUDED.name,
    parser_config = EXCLUDED.parser_config,
    is_active = EXCLUDED.is_active,
    crawl_interval_minutes = EXCLUDED.crawl_interval_minutes;

-- 충북대 공식 전자정보대학 안내 페이지가 연결하는 소프트웨어학부 공지.
-- robots.txt에서 공개 접근이 허용된 공지 목록과 상세 본문을 요약한다.
WITH cbnu AS (
    SELECT id FROM schools WHERE name = '충북대학교'
)
INSERT INTO notice_sources (
    school_id, name, source_type, list_url, parser_config,
    is_active, crawl_interval_minutes
)
SELECT cbnu.id,
       '소프트웨어학부 공지',
       'school_website',
       'https://software.cbnu.ac.kr/sub0401',
       '{
         "terms_checked": false,
         "operator_directed_public_content": true,
         "source_scope": "department",
         "target_department_name": "소프트웨어학부",
         "item_selector": "tr.notice",
         "title_selector": "td.title a",
         "link_selector": "td.title a",
         "date_selector": "td.time",
         "category_selector": "td.cate",
         "content_selector": ".rd_body",
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

INSERT INTO notice_categories (source_id, name)
SELECT source.id, category.name
FROM notice_sources AS source
CROSS JOIN (VALUES ('학부'), ('장학')) AS category(name)
WHERE source.list_url = 'https://software.cbnu.ac.kr/sub0401'
ON CONFLICT (source_id, name) DO NOTHING;

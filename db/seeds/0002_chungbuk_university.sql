-- 충북대학교 전체 공지 게시판. selector 및 수집 허용 여부 확인 전에는
-- terms_checked=false 상태로 두어 수집기가 요청하지 않게 한다.
INSERT INTO schools (name, homepage_url, is_active)
VALUES ('충북대학교', 'https://www.cbnu.ac.kr/', TRUE)
ON CONFLICT (name) DO UPDATE
SET homepage_url = EXCLUDED.homepage_url,
    is_active = EXCLUDED.is_active;

INSERT INTO notice_sources (school_id, name, list_url, parser_config, is_active)
SELECT s.id,
       '전체 공지사항',
       'https://www.cbnu.ac.kr/www/selectBbsNttList.do?bbsNo=8&key=814&pageIndex=1&searchCnd=all&searchCtgry=',
       '{"terms_checked": false, "max_pages": 1, "complete_snapshot": false}'::jsonb,
       TRUE
FROM schools AS s
WHERE s.name = '충북대학교'
ON CONFLICT (school_id, list_url) DO NOTHING;

INSERT INTO notice_categories (source_id, name)
SELECT ns.id, category.name
FROM notice_sources AS ns
JOIN schools AS s ON s.id = ns.school_id
CROSS JOIN (
    VALUES
        ('일반'),
        ('학사/장학'),
        ('입학/등록'),
        ('채용/인사'),
        ('행사/세미나'),
        ('모집/공모')
) AS category(name)
WHERE s.name = '충북대학교'
  AND ns.name = '전체 공지사항'
ON CONFLICT (source_id, name) DO NOTHING;

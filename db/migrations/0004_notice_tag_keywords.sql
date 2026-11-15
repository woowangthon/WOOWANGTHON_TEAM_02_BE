-- Expand topic synonyms and repair tags on notices already in the database.
INSERT INTO tag_keywords (tag_id, keyword, weight)
SELECT tag.id, keyword.keyword, keyword.weight
FROM tags AS tag
JOIN (VALUES
    ('contest', '대회', 3),
    ('contest', '경진', 3),
    ('contest', '경연', 2),
    ('contest', '해커톤', 3),
    ('contest', '아이디어톤', 3),
    ('contest', '캡스톤', 2),
    ('campus_activity', '행사', 2),
    ('campus_activity', '세미나', 2),
    ('campus_activity', '캠프', 2),
    ('campus_activity', '특강', 2),
    ('campus_activity', '워크숍', 2),
    ('campus_activity', '워크샵', 2),
    ('campus_activity', '프로그램', 1),
    ('campus_activity', '설명회', 2),
    ('scholarship', '장학', 3),
    ('academic', '강의평가', 3)
) AS keyword(code, keyword, weight) ON keyword.code = tag.code
ON CONFLICT (tag_id, keyword) DO UPDATE SET weight = EXCLUDED.weight;

-- Apply the current keyword map to every active notice without replacing
-- manually assigned tags.
INSERT INTO notice_tags (notice_id, tag_id, origin)
SELECT DISTINCT notice.id, tag.id, 'rule'
FROM notices AS notice
JOIN notice_sources AS source ON source.id = notice.source_id
JOIN tags AS tag ON tag.is_active
JOIN tag_keywords AS keyword ON keyword.tag_id = tag.id
WHERE notice.status = 'active'
  AND position(
      lower(keyword.keyword)
      IN lower(coalesce(notice.title, '') || ' ' || coalesce(notice.content, ''))
  ) > 0
ON CONFLICT (notice_id, tag_id) DO NOTHING;

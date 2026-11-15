-- The generic word "공모" also appears in scholarship and course selection
-- notices. Keep explicit "공모전" and other contest terms instead.
DELETE FROM tag_keywords AS keyword
USING tags AS tag
WHERE keyword.tag_id = tag.id
  AND tag.code = 'contest'
  AND keyword.keyword = '공모';

-- Rebuild only rule-generated contest tags. For scholarship-titled notices,
-- evidence in the body alone (e.g. award requirements) does not make the notice
-- itself a contest announcement; the contest term must be in the title.
DELETE FROM notice_tags AS notice_tag
USING tags AS tag
WHERE notice_tag.tag_id = tag.id
  AND tag.code = 'contest'
  AND notice_tag.origin = 'rule';

INSERT INTO notice_tags (notice_id, tag_id, origin)
SELECT DISTINCT notice.id, tag.id, 'rule'
FROM notices AS notice
JOIN tags AS tag ON tag.code = 'contest' AND tag.is_active
JOIN tag_keywords AS keyword ON keyword.tag_id = tag.id
WHERE notice.status = 'active'
  AND (
      position(lower(keyword.keyword) IN lower(coalesce(notice.title, ''))) > 0
      OR (
          coalesce(notice.title, '') !~* '장학'
          AND position(lower(keyword.keyword) IN lower(coalesce(notice.content, ''))) > 0
      )
  )
ON CONFLICT (notice_id, tag_id) DO NOTHING;

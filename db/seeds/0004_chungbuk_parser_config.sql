-- 충북대 공식 전체 공지의 페이지 소스에서 selector를 확인했다.
-- 이용약관 확인 상태는 미확인으로 유지한다. 공개 목록과 robots 허용 범위
-- 안의 상세 본문을 읽어 짧은 요약을 만든다.
UPDATE notice_sources
SET parser_config = (parser_config - 'content_selector') ||
    '{
      "terms_checked": false,
      "operator_directed_public_content": true,
      "source_scope": "school",
      "item_selector": ".p-table.simple tbody.text_center > tr",
      "title_selector": "td.p-subject a",
      "link_selector": "td.p-subject a",
      "date_selector": "td:nth-child(6)",
      "id_selector": ".bbs_num",
      "category_selector": "td:nth-child(2)",
      "content_selector": ".bbs_viewbox .viewcontentbox .contenttext",
      "max_pages": 1,
      "complete_snapshot": false
    }'::jsonb
WHERE list_url = 'https://www.cbnu.ac.kr/www/selectBbsNttList.do?bbsNo=8&key=814&pageIndex=1&searchCnd=all&searchCtgry=';

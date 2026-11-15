"""Command line interface for local HTML-only notice processing."""
import argparse
import json
from pathlib import Path

from .config import DEFAULT_DATABASE, SAMPLE_FILES
from .database import DatabaseManager
from .models import Notice
from .parsers import ComputerEngineeringCrawler, ElectricalEngineeringCrawler

CRAWLERS = {
    "computer": ComputerEngineeringCrawler,
    "electrical": ElectricalEngineeringCrawler,
}


def ingest_local_html(db, crawler, html: Path, source_url: str | None = None) -> dict:
    """Store listing metadata first, then enrich it if the same file has a detail view."""
    new_posts = {}
    listed = crawler.list_notices(html)
    for item in listed:
        key = item["post_number"]
        if not db.exists(item["department"], key):
            new_posts[key] = item["title"]
        db.upsert(Notice(item["department"], item["post_number"], item["title"], item.get("author", ""),
                         item.get("date", ""), item["url"], "", []))
    try:
        detail = crawler.parse_detail(html, source_url)
        if not db.exists(detail.department, detail.post_number):
            new_posts[detail.post_number] = detail.title
        db.upsert(detail)
        return {"department": crawler.department, "list_entries": len(listed), "detail_saved": True,
                "detail_post_number": detail.post_number, "new_notices": new_posts}
    except ValueError as exc:
        if not listed:
            raise
        return {"department": crawler.department, "list_entries": len(listed), "detail_saved": False,
                "detail_note": str(exc), "new_notices": new_posts}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="충북대학교 공지 샘플 HTML 로컬 처리 도구 (네트워크 요청 없음)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE, help="SQLite DB 경로")
    commands = parser.add_subparsers(dest="command", required=True)
    for key in CRAWLERS:
        cmd = commands.add_parser(key, help=f"{key} 샘플 HTML 처리")
        cmd.add_argument("--html", type=Path, default=SAMPLE_FILES[key], help="사용자가 저장한 HTML 파일")
        cmd.add_argument("--url", help="원본 상세 URL (샘플에 게시글 번호가 없을 때 선택 입력)")
    import_cmd = commands.add_parser("import", help="저장한 HTML을 반영하고 새 공지 여부 확인")
    import_cmd.add_argument("--department", choices=CRAWLERS.keys(), required=True)
    import_cmd.add_argument("--html", type=Path, required=True, help="브라우저에서 저장한 HTML 파일")
    import_cmd.add_argument("--url", help="상세 페이지 URL (필요 시)")
    commands.add_parser("all", help="기본 컴퓨터/전기공학 샘플 모두 처리")
    search = commands.add_parser("search", help="제목 또는 본문 검색")
    search.add_argument("query")
    detail = commands.add_parser("detail", help="게시글 상세 조회")
    detail.add_argument("department", choices=[c().department for c in CRAWLERS.values()])
    detail.add_argument("post_number")
    listing = commands.add_parser("list", help="저장 자료 전체 목록 조회")
    listing.add_argument("--department")
    commands.add_parser("latest", help="학과별 DB 최신 공지 확인 (사이트 접속 없음)")
    export = commands.add_parser("export", help="JSON으로 내보내기")
    export.add_argument("--output", type=Path, default=Path("notices_export.json"))
    args = parser.parse_args(argv)

    db = DatabaseManager(args.db)
    if args.command == "import":
        result = ingest_local_html(db, CRAWLERS[args.department](), args.html, args.url)
        new_posts = result["new_notices"]
        print(f"{result['department']}: 목록 {result['list_entries']}건 확인")
        if new_posts:
            print(f"새 공지 {len(new_posts)}건을 DB에 추가했습니다.")
            for number, title in new_posts.items():
                print(f"- [{number}] {title}")
        else:
            print("새 공지가 없습니다. (이미 저장된 공지입니다.)")
        if result.get("detail_saved"):
            print(f"상세 본문 저장 완료: [{result['detail_post_number']}]")
        return 0
    elif args.command in CRAWLERS:
        crawler = CRAWLERS[args.command]()
        result = ingest_local_html(db, crawler, args.html, args.url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "all":
        results = []
        for key, crawler_type in CRAWLERS.items():
            try:
                results.append(ingest_local_html(db, crawler_type(), SAMPLE_FILES[key]))
            except Exception as exc:
                results.append({"department": crawler_type.department, "saved": False, "error": str(exc)})
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.command == "search":
        print(json.dumps(db.search(args.query), ensure_ascii=False, indent=2))
    elif args.command == "detail":
        item = db.get(args.department, args.post_number)
        print(json.dumps(item, ensure_ascii=False, indent=2) if item else "해당 게시글이 없습니다.")
    elif args.command == "list":
        print(json.dumps(db.all(args.department), ensure_ascii=False, indent=2))
    elif args.command == "latest":
        latest = db.latest_by_department()
        if not latest:
            print("저장된 공지가 없습니다.")
        else:
            for item in latest:
                print(f"{item['department']}: [{item['post_number']}] {item['date']} - {item['title']}")
    elif args.command == "export":
        db.export_json(args.output)
        print(f"JSON 저장 완료: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

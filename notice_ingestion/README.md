# 충북대학교 공지 HTML 로컬 처리기

두 학과 사이트에서 **사용자가 직접 저장한 HTML 파일만** 읽어 공지 자료를 구조화하고 SQLite에 저장합니다. 이 도구는 사이트로 네트워크 요청을 보내지 않습니다. 제공된 robots.txt 정책이 자동 접근을 금지하고 있어, 관리자 허가 전까지 자동 수집 기능은 제공하지 않습니다.

## 구성

- `parsers/computer.py`, `parsers/electrical.py`: 사이트별 상세 파서와 목록 링크 파서
- `parsers/base.py`: 공통 HTML 읽기, 본문/첨부파일 추출
- `database/schema.sql`, `database/manager.py`: SQLite 스키마와 중복 방지 upsert
- `samples/`: 이번에 제공된 원본 HTML 샘플
- `tests/`: 샘플 파싱, 저장/검색/내보내기 확인

샘플의 메타 태그는 EUC-KR을 선언하지만 제공 파일 바이트는 UTF-8이어서 UTF-8을 우선 읽고, UTF-8이 아닌 로컬 파일은 EUC-KR로 읽습니다. 상세 본문은 `div#articles`, 제목/작성자/작성일은 확인한 `.view_subject`, `.view_name`, `.view_text` 요소에서 추출합니다. 목록 링크는 실제 HTML의 `task=view`와 `no` 값으로 식별합니다.

## 실행

프로젝트 루트 기준:

```powershell
$env:PYTHONPATH = "BE"
python -m pip install -r BE/notice_ingestion/requirements.txt
python -m notice_ingestion.main all
```

### 매번 쓰는 간편 가져오기

1. 브라우저에서 해당 학과 공지 목록을 열고 `Ctrl+S`로 HTML 파일을 저장합니다.
2. `BE/notice_ingestion/import-notices.bat`을 더블클릭합니다.
3. 학과 번호를 선택하고 저장한 HTML을 고릅니다.

목록을 기존 DB와 비교해 새 게시글 번호가 있으면 제목과 함께 알려주고, HTML에 포함된 목록 정보를 저장합니다. 이미 저장된 공지만 있으면 새 공지가 없다고 표시합니다. 같은 게시글의 상세 HTML을 선택해 가져오면 본문과 첨부파일 정보도 채우며, 나중에 목록 HTML만 다시 가져와도 저장된 상세 본문을 빈 값으로 덮어쓰지 않습니다. 새 공지 확인은 **마지막으로 DB에 반영된 HTML**과 비교하므로, 최신 HTML을 일정 간격으로 직접 저장해 이 도구에 넣어야 합니다.

명령으로 실행하려면 프로젝트 루트 PowerShell에서:

```powershell
$env:PYTHONPATH = "BE"
python -m notice_ingestion.main import --department electrical --html "C:\경로\저장한공지.html"
```

학과 값은 `computer` 또는 `electrical`입니다. 이 방식은 새 HTML 파일을 반영하는 시점에만 비교하므로, 자동 알림이나 백그라운드 감시는 하지 않습니다.

PowerShell에서 모듈 경로가 필요하면:

```powershell
$env:PYTHONPATH = "BE"
python -m notice_ingestion.main all
```

세부 명령:

```powershell
python -m notice_ingestion.main computer --html 경로\computer.html
python -m notice_ingestion.main electrical --html 경로\electrical.html
python -m notice_ingestion.main list
python -m notice_ingestion.main latest
python -m notice_ingestion.main search "장학금"
python -m notice_ingestion.main detail 컴퓨터공학과 2792
python -m notice_ingestion.main export --output notices_export.json
```

사이트를 열어 새 글만 빠르게 비교하려면 `latest` 명령으로 DB에 마지막 반영된 학과별 번호·날짜·제목을 확인한 뒤 사이트 목록 첫 글과 대조하면 됩니다. 이 명령은 사이트에 접속하지 않습니다.

기본 데이터베이스는 `BE/notice_ingestion/data/notices.db`입니다. `--db 경로`로 위치를 바꿀 수 있습니다. `(department, post_number)`가 같으면 기존 행을 최신 파싱 내용으로 갱신합니다. 날짜 순으로 조회하며, 첨부파일은 파일명/URL 객체의 JSON 배열로 저장합니다.

## 테스트

프로젝트 루트에서:

```powershell
$env:PYTHONPATH = "BE"
python -m unittest discover -s BE/notice_ingestion/tests -v
```

## 브라우저에서 현재 공지와 DB 비교

`browser_extension/`은 사용자가 직접 누른 경우에만 컴퓨터공학과 또는 전기공학부 홈페이지를 열고, 화면의 공지 번호·제목·날짜·링크를 읽어 알려줌 DB와 비교합니다. 목록을 읽고 비교하면 학과 홈페이지 탭은 자동으로 닫히고 결과 탭만 남습니다. 새 글뿐 아니라 DB에 이미 있지만 공백을 제외한 본문이 비어 있는 글도 **본문 보완** 대상으로 표시합니다. 상세 페이지에서 내용을 다시 가져온 뒤 **공지 DB에 저장**을 누르면 기존 게시글 행을 갱신하므로 중복을 만들지 않습니다. 저장 성공 후 저장 확인 탭과 원문 상세 탭은 자동으로 닫히고, 결과 탭에는 저장 완료 상태가 남습니다. `Ctrl+S`나 저장 위치 선택은 필요 없습니다. 이 기능은 사용자가 버튼을 눌렀을 때만 동작하며 백그라운드에서 사이트를 주기적으로 확인하지 않습니다.

Chrome에 시험 설치하려면:

1. 주소창에 `chrome://extensions`를 입력합니다.
2. 개발자 모드를 켜고 **압축해제된 확장 프로그램을 로드**를 선택합니다.
3. `BE/notice_ingestion/browser_extension` 폴더를 선택합니다. 이미 설치한 경우 확장 프로그램 카드의 새로고침 버튼을 눌러 변경된 버전을 적용합니다.
4. 알려줌 백엔드(`localhost:8000` 또는 `localhost:8001`)를 실행하고 로그인한 상태에서 확장 프로그램의 학과별 확인 버튼을 누릅니다.

새 공지의 상세 페이지를 열면 확장 프로그램이 읽은 내용을 알려줌 확인 화면으로 보냅니다. 저장은 로그인한 사용자가 확인 화면의 버튼을 누를 때만 이루어집니다. 앱을 다시 빌드하면 `0003_notice_author.sql` 마이그레이션이 작성자 필드를 추가합니다.

## 범위와 제한

- 저장된 상세 HTML에서 확인된 필드만 추출합니다. 게시판의 개별 목록 행마다 작성자/날짜가 노출되지 않으면 목록 결과에는 제목/번호/URL만 있습니다.
- 컴퓨터공학과 샘플의 게시글 번호는 샘플 HTML에 포함된 다운로드 링크에서 확인했습니다. 다른 샘플에서 번호를 찾을 수 없으면 `--url`로 실제 상세 URL을 전달해야 합니다.
- 자동 접속/수집, 페이지네이션 요청은 구현하지 않았습니다. 관리자 허가가 확인된 뒤에 해당 범위를 별도로 검증해야 합니다.
- 실제 샘플에서 추출한 정보만 보존합니다. 샘플에 없는 게시글은 생성하지 않습니다.

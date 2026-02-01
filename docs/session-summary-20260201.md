# Session Summary - 2026-02-01

## 구현 완료 사항

### Phase A: 모든 AI 챗봇 Collector 수정
- `src/collectors/base.py` — 4개 SPA 공유 헬퍼 추가 (`_wait_for_content`, `_scroll_to_load_all`, `_find_working_selector`, `_extract_date_from_text`)
- `src/collectors/claude.py` — base 헬퍼 사용으로 리팩토링, 날짜 추출 추가
- `src/collectors/chatgpt.py` — `networkidle` 제거, polling + scroll + date/preview 추가
- `src/collectors/gemini.py` — 동일 처리, sidebar-open 로직 유지
- `src/collectors/granola.py` — 동일 처리
- `src/collectors/fyxer.py` — 동일 처리
- `src/collectors/runner.py` — `_filter_by_date()` 함수 + `days` 파라미터 (보수적: 날짜 없는 항목 유지)
- `src/cli/main.py` — `collect` 명령에 `--days` 플래그 추가 (기본값 30)

### Phase B: Write & Publish 기능
- `src/storage/schema.sql` — `posts` 테이블 추가 (status/tags/category 인덱스)
- `src/storage/dao.py` — frozen `Post` dataclass + `PostDAO` (insert, update, find_by_id, find_all, delete)
- `src/ingest/post_writer.py` — Obsidian 내보내기 (YAML frontmatter + markdown) + 독립 HTML 내보내기
- `src/web/server.py` — 7개 새 라우트: GET/POST `/write`, GET `/posts`, GET/POST `/posts/{id}/edit`, POST `/posts/{id}/publish`, POST `/posts/{id}/delete`
- `src/web/templates/write.html` — 마크다운 에디터 + 실시간 JS 미리보기
- `src/web/templates/posts.html` — 포스트 목록 + 상태 필터 탭 + 액션 버튼
- `src/web/templates/base.html` — Write + Posts 네비게이션 링크 추가

### Phase C: 뉴스 소스 (RSS + Twitter/X Nitter)
- `src/app/config.py` — `rss_feeds`, `nitter_instance`, `twitter_accounts` 설정 + 파서 헬퍼
- `src/morning/sources/rss.py` — 날짜 필터링, `classify()` 분류, 중요도 스코어링, 키워드 부스트, 50개로 제한 증가
- `src/morning/sources/twitter.py` — Nitter RSS 프록시를 통한 Twitter/X (API 키 불필요), Nitter URL → X URL 변환
- `src/morning/sources/fetch_all.py` — RSS + Twitter 통합 페처
- `src/cli/main.py` — `morning fetch --days 7` 명령
- `.env` — RSS_FEEDS, TWITTER_ACCOUNTS, NITTER_INSTANCE 설정 추가

### 테스트: 95개 전체 통과
- `tests/test_collectors.py` — 30개 (날짜 추출, 셀렉터, 스크롤, 로그인 감지, 날짜 필터링, 대화 추출)
- `tests/test_news_sources.py` — 22개 (중요도 스코어링, 날짜 필터링, RSS, Twitter/Nitter, 설정 파싱, 통합 페처)
- `tests/test_posts.py` — 7개 (PostDAO CRUD, Obsidian 내보내기, HTML 내보내기)
- 기존 36개 (hybrid search, vector search) 모두 유지

---

## 핵심 이슈: Chrome 프로필 / 쿠키 문제

### 문제
Playwright로 Chrome 프로필을 사용하여 AI 챗봇에 자동 로그인하려 했으나 실패:

1. **프로필 복사 방식**: Chrome 쿠키가 macOS Keychain으로 암호화되어 있어, 복사된 프로필에서는 복호화 불가
2. **원본 프로필 직접 사용**: Chrome이 자체 기본 data directory를 remote debugging과 함께 사용하는 것을 거부 (`DevTools remote debugging requires a non-default data directory`)
3. **Chrome 실행 중**: 프로필이 잠겨있어 사용 불가

### 시도한 방법들
| 방법 | 결과 |
|------|------|
| 프로필을 temp dir에 복사 → Playwright 사용 | 쿠키 복호화 실패 (Keychain 암호화) |
| 원본 Chrome 프로필 직접 사용 | Chrome이 거부 (non-default dir 요구) |
| Chrome 종료 후 시도 | 위 두 가지 모두 실패 |

### 가능한 대안

#### 1. 전용 Playwright 프로필 (수동 1회 로그인)
- `data/playwright_profile/` 에 별도 Playwright 프로필 유지
- 첫 실행 시 브라우저 열림 → 사용자가 수동 로그인
- 이후 세션 쿠키 재사용
- **장점**: 가장 안정적, 구현 간단
- **단점**: 플랫폼별 1회 수동 로그인 필요, 세션 만료 시 재로그인

#### 2. 각 AI 챗봇 API 활용
- Claude: Anthropic API로 대화 내역 조회 (가능 여부 확인 필요)
- ChatGPT: OpenAI API conversations endpoint
- Gemini: Google AI API
- **장점**: 브라우저 자동화 불필요, 안정적
- **단점**: API 키 필요, 일부 플랫폼은 대화 내역 API 미제공

#### 3. 각 챗봇에서 자동 저장 설정
- Claude Projects: 자동 저장 기능 없음 (수동 내보내기만 가능)
- ChatGPT: "Data controls" → export 가능하지만 자동화 아님
- Gemini: Google Takeout으로 내보내기 가능
- **장점**: 챗봇 자체 기능 활용
- **단점**: 대부분 수동 내보내기만 지원, 자동화 어려움

#### 4. 브라우저 확장 프로그램
- Chrome extension으로 대화 내용을 로컬 DB에 자동 저장
- `chrome.history` / `content_script`로 AI 챗봇 페이지 감지 → 대화 내용 추출
- **장점**: Chrome 로그인 세션 그대로 활용, 실시간 자동 저장
- **단점**: 확장 프로그램 개발 필요, 각 챗봇 DOM 구조 의존

#### 5. CDP (Chrome DevTools Protocol) 직접 연결
- Chrome을 `--remote-debugging-port=9222`로 실행
- Playwright가 기존 Chrome 인스턴스에 CDP로 연결
- **장점**: 기존 로그인 세션 그대로 사용
- **단점**: Chrome 시작 방법 변경 필요

---

## Git 상태
- **브랜치**: master
- **마지막 커밋**: `442d883` - `feat: add collector SPA fixes, write/publish feature, and news sources`
- **push 완료**: origin/master에 반영됨
- **runner.py**: 마지막 수정 (직접 프로필 사용 시도) 은 아직 커밋 안 됨 — 동작하지 않으므로 되돌려야 함

## 실행 방법

```bash
# 웹 서버
python -m src.cli.main serve

# 검색
python -m src.cli.main search --q "python" --mode hybrid

# 뉴스 소스 가져오기
python -m src.cli.main morning fetch --days 7

# 모닝 다이제스트 빌드
python -m src.cli.main morning build

# 테스트
pytest tests/ -v
```

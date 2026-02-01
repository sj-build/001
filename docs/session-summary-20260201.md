# Session Summary - 2026-02-01

## 구현 완료 사항

### Phase A: 모든 AI 챗봇 Collector 수정
- `src/collectors/base.py` — 4개 SPA 공유 헬퍼 추가 (`_wait_for_content`, `_scroll_to_load_all`, `_find_working_selector`, `_extract_date_from_text`)
- `src/collectors/claude.py` — base 헬퍼 사용으로 리팩토링, 날짜 추출 추가
- `src/collectors/chatgpt.py` — `networkidle` 제거, polling + scroll + date/preview 추가
- `src/collectors/gemini.py` — 동일 처리, sidebar-open 로직 유지
- `src/collectors/granola.py` — 동일 처리
- `src/collectors/fyxer.py` — 동일 처리
- `src/collectors/runner.py` — CDP 방식 + `_filter_by_date()` 함수 + `days` 파라미터
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
- `src/app/config.py` — `rss_feeds`, `nitter_instance`, `twitter_accounts`, `cdp_port`, `chrome_path` 설정
- `src/morning/sources/rss.py` — 날짜 필터링, `classify()` 분류, 중요도 스코어링, 키워드 부스트, 50개로 제한 증가
- `src/morning/sources/twitter.py` — Nitter RSS 프록시를 통한 Twitter/X (API 키 불필요), Nitter URL → X URL 변환
- `src/morning/sources/fetch_all.py` — RSS + Twitter 통합 페처
- `src/cli/main.py` — `morning fetch --days 7` 명령
- `.env` — RSS_FEEDS, TWITTER_ACCOUNTS, NITTER_INSTANCE 설정 추가

### 테스트: 103개 전체 통과
- `tests/test_collectors.py` — 38개 (날짜 추출, 셀렉터, 스크롤, 로그인 감지, 날짜 필터링, 대화 추출, CDP 헬퍼, 프로필 복사)
- `tests/test_news_sources.py` — 22개 (중요도 스코어링, 날짜 필터링, RSS, Twitter/Nitter, 설정 파싱, 통합 페처)
- `tests/test_posts.py` — 7개 (PostDAO CRUD, Obsidian 내보내기, HTML 내보내기)
- 기존 36개 (hybrid search, vector search) 모두 유지

---

## 해결됨: Chrome CDP 방식으로 Collector 동작 확인

### 최종 구현: CDP (Chrome DevTools Protocol) + 전용 프로필

Chrome이 기본 데이터 디렉토리에서는 `--remote-debugging-port`를 거부하므로,
전용 CDP 프로필 디렉토리(`data/chrome_cdp_profile/`)를 사용.

**동작 플로우:**
1. Chrome이 안 실행중 → 자동으로 `--remote-debugging-port=9222 --user-data-dir=data/chrome_cdp_profile/`로 실행
2. Chrome이 CDP 포트 열린 상태 → 바로 연결
3. Chrome이 CDP 없이 실행중 → 사용자에게 Chrome 종료 요청

**첫 실행:** 플랫폼별 1회 수동 로그인 필요 (Chrome 창에서 직접)
**이후 실행:** CDP 프로필에 세션 저장되어 자동 로그인

**검증 완료:** Claude에서 60개 대화 수집 성공

### 시도했으나 실패한 방법들
| 방법 | 결과 |
|------|------|
| Chrome 프로필을 temp dir에 복사 → Playwright 사용 | 쿠키 복호화 실패 (Keychain 암호화) |
| Chrome 원본 프로필 직접 사용 (CDP) | Chrome이 거부 (non-default dir 요구) |
| Chrome 프로필 복사 → CDP user-data-dir로 사용 | 쿠키 복호화 실패 (동일 Keychain 이슈) |
| Playwright persistent context (전용 프로필) | 동작하지만 별도 로그인 필요 |

### Chrome 프로필 정보
- `Default` = SJ (개인메일) ← 사용 중
- `Profile 3` = Hashed (SJ Baek)

---

## 남은 작업 / 다음 할 일

### 다른 플랫폼 수집
- [ ] ChatGPT — CDP Chrome에서 로그인 후 수집 테스트
- [ ] Gemini — 동일
- [ ] Granola — 동일
- [ ] Fyxer — 동일
- 실행: `python -m src.cli.main collect --platform chatgpt --days 30`

### 추가 개선 가능 사항
- [ ] 세션 만료 시 자동 감지 + 재로그인 안내
- [ ] `collect --platform all`로 전체 플랫폼 일괄 수집
- [ ] 수집 스케줄러 (cron 또는 launchd)
- [ ] Morning digest에 수집된 대화 요약 포함

---

## Git 상태
- **브랜치**: master
- **마지막 커밋**: `768e6a5` - `feat: implement CDP connection for collector browser automation`
- **push 필요**: `git push origin master`

## 실행 방법

```bash
# 대화 수집 (Chrome 자동 실행됨, 첫 실행 시 수동 로그인 필요)
python -m src.cli.main collect --platform claude --days 30

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

# Hedge Fund Investment Tracker

글로벌 Top 10 헤지펀드들의 분기별 투자 현황을 추적하고 분석하는 웹 애플리케이션입니다.

## 주요 기능

### 1. 분기별 Top 10 주식 집계
- 10개 헤지펀드의 13F 공시 데이터를 합산
- 분기별로 가장 많이 투자된 주식 Top 10 표시
- 각 주식을 보유한 펀드 수, 총 투자액 표시

### 2. 각 펀드별 1위 주식 상세 분석
- 각 헤지펀드의 최대 보유 주식(10개) 식별
- 각 주식에 대해:
  - 최근 1년 주가 차트 (Recharts)
  - 밸류에이션 멀티플: P/E, P/B, P/S, EV/EBITDA
  - 펀드 내 포트폴리오 비중

## 기술 스택

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS v3
- **Charts**: Recharts
- **Data Sources**:
  - SEC EDGAR API (13F filings)
  - Yahoo Finance API via yfinance (주가 + 밸류에이션)

## 추적 중인 헤지펀드 (Top 10)

1. Bridgewater Associates, LP
2. Citadel Advisors LLC
3. Millennium Management LLC
4. Two Sigma Investments, LP
5. Renaissance Technologies LLC
6. D.E. Shaw & Co., Inc.
7. AQR Capital Management LLC
8. Elliott Management Corp
9. Point72 Asset Management
10. Farallon Capital Management

## 시작하기

### 1. 개발 서버 실행 (Mock 데이터 사용)

현재 샘플 데이터가 이미 생성되어 있으므로, 바로 앱을 실행할 수 있습니다:

```bash
npm run dev
```

브라우저에서 http://localhost:5173/ 를 열어 앱을 확인하세요.

### 2. 실제 데이터 수집 (선택사항)

실제 SEC EDGAR API에서 13F 데이터를 수집하려면:

#### 필수 요구사항:
- Node.js 18+
- Python 3.8+ with pip

#### Python 패키지 설치:
```bash
pip install yfinance pandas
```

#### 데이터 생성:
```bash
node scripts/buildQuarterData.js --quarter 2025-Q4
```

**주의사항:**
- SEC API 호출은 시간이 오래 걸립니다 (10-20분)
- SEC API rate limit: 10 requests/second
- 일부 펀드의 13F 데이터를 찾지 못할 수 있습니다
- Yahoo Finance API도 rate limit이 있으므로 0.5초 delay가 적용됩니다

### 3. 프로덕션 빌드

```bash
npm run build
npm run preview  # 빌드 결과 미리보기
```

## 프로젝트 구조

```
hedge-fund-tracker/
├── public/
│   └── data/
│       └── quarters/           # 분기별 JSON 데이터
│           ├── 2025-Q4.json
│           └── 2025-Q4-detailed.json
│
├── src/
│   ├── components/             # React 컴포넌트
│   │   ├── QuarterSelector.tsx
│   │   ├── TopStocksTable.tsx
│   │   ├── StockChart.tsx
│   │   ├── ValuationMetrics.tsx
│   │   ├── StockDetailCard.tsx
│   │   └── FundTopHoldings.tsx
│   │
│   ├── types/                  # TypeScript 타입 정의
│   │   └── index.ts
│   │
│   ├── utils/                  # 유틸리티 함수
│   │   ├── dataLoader.ts
│   │   └── formatters.ts
│   │
│   └── App.tsx                 # 메인 앱 컴포넌트
│
├── scripts/                    # 데이터 수집 스크립트
│   ├── config.js               # 헤지펀드 CIK 목록
│   ├── fetch13F.js             # SEC EDGAR API 호출
│   ├── parsers/
│   │   └── xml13FParser.js     # 13F XML 파싱
│   ├── aggregator.js           # Holdings 집계
│   ├── identifyTopHoldings.js  # 각 펀드의 top 1 식별
│   ├── fetchStockData.py       # Yahoo Finance 데이터
│   ├── buildQuarterData.js     # 전체 파이프라인 orchestrator
│   └── generateMockData.cjs    # 테스트용 mock 데이터 생성
│
└── package.json
```

## 데이터 구조

### Quarter Summary (`2025-Q4.json`)
- 분기 정보
- 10개 헤지펀드 기본 정보
- Top 10 집계 주식
- 메타데이터 (총 AUM, 분석된 펀드 수 등)

### Detailed Quarter Data (`2025-Q4-detailed.json`)
- 각 펀드의 1위 보유 주식
- 1년 주가 히스토리 (일별)
- 밸류에이션 멀티플 (P/E, P/B, P/S, EV/EBITDA)

## 사용 가능한 명령어

```bash
# 개발 서버 실행
npm run dev

# 프로덕션 빌드
npm run build

# 빌드 미리보기
npm run preview

# Mock 데이터 생성 (빠른 테스트용)
node scripts/generateMockData.cjs

# 실제 데이터 수집 (느림, SEC API 호출)
node scripts/buildQuarterData.js --quarter 2025-Q4
```

## 주요 제한사항

1. **데이터 지연**: 13F 공시는 분기 종료 후 45일 이내 제출되므로 항상 1.5-2개월 지연됩니다.

2. **CUSIP → Ticker 매핑**:
   - 현재 주요 주식만 하드코딩되어 있습니다
   - 완전한 매핑을 위해서는 OpenFIGI API 또는 CUSIP 데이터베이스가 필요합니다

3. **SEC API 제약**:
   - CORS 지원 없음 (빌드타임에만 데이터 수집 가능)
   - Rate limit: 10 requests/second
   - User-Agent 헤더 필수

4. **Yahoo Finance 제약**:
   - 비공식 API (언제든지 변경될 수 있음)
   - Rate limiting 존재
   - 일부 주식의 밸류에이션 데이터 누락 가능

## 향후 개선 사항

- [ ] 과거 여러 분기 데이터 비교 기능
- [ ] 섹터별 집계 및 분석
- [ ] 주식 검색 및 필터링
- [ ] 포트폴리오 변화 추적 (분기별 변동)
- [ ] CSV/Excel 내보내기
- [ ] 자동화된 분기별 데이터 업데이트 (GitHub Actions)
- [ ] 차트 인터랙션 개선
- [ ] OpenFIGI API를 통한 완전한 CUSIP 매핑

## 라이선스

Educational project - MIT License

## 참고사항

이 프로젝트는 교육 목적으로 만들어졌으며, 투자 조언을 제공하지 않습니다.
SEC 13F 공시 데이터는 공개 정보이지만, 항상 최신 데이터를 확인하고 전문가와 상담하시기 바랍니다.

// Price data point for chart
export interface PricePoint {
  date: string;
  close: number;
}

// Valuation metrics for a stock
export interface ValuationMetrics {
  peRatio: number | null;
  pbRatio: number | null;
  psRatio: number | null;
  evToEbitda: number | null;
  marketCap: number;
  lastUpdated: string;
}

// Holding by a single fund
export interface HoldingByFund {
  fundName: string;
  value: number;
  shares: number;
  percentOfFundPortfolio: number;
}

// Top stock in the aggregated view
export interface TopStock {
  rank: number;
  cusip: string;
  ticker: string;
  companyName: string;
  totalValue: number;
  totalShares: number;
  numberOfFundsHolding: number;
  percentOfTotalAUM: number;
  holdingsByFund: HoldingByFund[];
}

// Hedge fund information
export interface HedgeFund {
  name: string;
  cik: string;
  totalAUM: number;
  filingDate: string;
}

// Metadata for quarter data
export interface QuarterMetadata {
  totalFundsAnalyzed: number;
  totalAUMAggregated: number;
  uniqueStocksHeld: number;
  dataQuality: string;
}

// Summary data for a quarter (aggregated top 10 stocks)
export interface QuarterSummaryData {
  quarter: string;
  quarterEnd: string;
  filingDeadline: string;
  generatedAt: string;
  hedgeFunds: HedgeFund[];
  topStocks: TopStock[];
  metadata: QuarterMetadata;
}

// Detailed holding information (with price history and valuation metrics)
export interface DetailedHolding {
  ticker: string;
  companyName: string;
  cusip: string;
  value: number;
  shares: number;
  percentOfPortfolio: number;
  priceHistory: PricePoint[];
  valuationMetrics: ValuationMetrics;
}

// Top holding for a specific fund
export interface FundTopHolding {
  fundName: string;
  fundCik: string;
  topHolding: DetailedHolding;
}

// Detailed data for a quarter (individual fund top holdings)
export interface DetailedQuarterData {
  quarter: string;
  fundTopHoldings: FundTopHolding[];
}

// Combined data structure
export interface QuarterData {
  summary: QuarterSummaryData;
  detailed: DetailedQuarterData;
}

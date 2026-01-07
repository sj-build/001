// Investor category type
export type InvestorCategory = 'guru' | 'emerging';

// Investor metadata
export interface InvestorMetadata {
  knownFor: string;
  since?: number;
  type?: string;
  estimatedAUM?: number;
  leader?: string;
}

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
  category: InvestorCategory;
  metadata: InvestorMetadata;
}

// Metadata for quarter data
export interface QuarterMetadata {
  totalFundsAnalyzed: number;
  totalAUMAggregated: number;
  uniqueStocksHeld: number;
  dataQuality: string;
  category: InvestorCategory;
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

// Quarterly position change data
export interface PositionChange {
  previousQuarter: {
    value: number;
    shares: number;
    percentOfPortfolio: number;
  } | null;
  currentQuarter: {
    value: number;
    shares: number;
    percentOfPortfolio: number;
  };
  change: {
    valueChange: number;
    sharesChange: number;
    percentChange: number;
  };
}

// Detailed holding information (with price history and valuation metrics)
export interface DetailedHolding {
  ticker: string;
  companyName: string;
  cusip: string;
  value: number;
  shares: number;
  percentOfPortfolio: number;
  positionChange: PositionChange;
  priceHistory: PricePoint[];
  valuationMetrics: ValuationMetrics;
}

// Most purchased position for a specific fund (largest increase vs previous quarter)
export interface FundTopHolding {
  fundName: string;
  fundCik: string;
  category: InvestorCategory;
  metadata: InvestorMetadata;
  mostPurchased: DetailedHolding;
}

// Detailed data for a quarter (individual fund top holdings)
export interface DetailedQuarterData {
  quarter: string;
  category: InvestorCategory;
  fundTopHoldings: FundTopHolding[];
}

// Combined data structure
export interface QuarterData {
  summary: QuarterSummaryData;
  detailed: DetailedQuarterData;
}

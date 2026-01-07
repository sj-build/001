import type { QuarterSummaryData, DetailedQuarterData, QuarterData, InvestorCategory } from '../types';

/**
 * Load quarter summary data for a specific category
 */
export async function loadQuarterSummary(quarter: string, category: InvestorCategory): Promise<QuarterSummaryData> {
  const response = await fetch(`/data/quarters/${category}-${quarter}.json`);

  if (!response.ok) {
    throw new Error(`Failed to load data for ${category} ${quarter}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Load quarter detailed data for a specific category
 */
export async function loadQuarterDetailed(quarter: string, category: InvestorCategory): Promise<DetailedQuarterData> {
  const response = await fetch(`/data/quarters/${category}-${quarter}-detailed.json`);

  if (!response.ok) {
    throw new Error(`Failed to load detailed data for ${category} ${quarter}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Load both summary and detailed data for a quarter and category
 */
export async function loadQuarterData(quarter: string, category: InvestorCategory): Promise<QuarterData> {
  const [summary, detailed] = await Promise.all([
    loadQuarterSummary(quarter, category),
    loadQuarterDetailed(quarter, category)
  ]);

  return { summary, detailed };
}

/**
 * Load data for all categories for a given quarter
 */
export async function loadAllCategories(quarter: string): Promise<Record<InvestorCategory, QuarterData>> {
  const [guru, emerging] = await Promise.all([
    loadQuarterData(quarter, 'guru'),
    loadQuarterData(quarter, 'emerging')
  ]);

  return { guru, emerging };
}

/**
 * Get list of available quarters
 * This could be dynamically loaded, but for now we'll hardcode
 */
export function getAvailableQuarters(): string[] {
  return ['2025-Q3', '2025-Q2', '2024-Q3', '2024-Q2'];
}

/**
 * Get list of available investor categories
 */
export function getAvailableCategories(): { value: InvestorCategory; label: string; description: string }[] {
  return [
    {
      value: 'guru',
      label: 'Top-tier Guru Investors',
      description: 'Legendary investors and institutional giants'
    },
    {
      value: 'emerging',
      label: 'Fast-Growing Multi-Strategy Funds',
      description: 'Top performing multi-strategy funds with highest AUM growth 2024-2025'
    }
  ];
}

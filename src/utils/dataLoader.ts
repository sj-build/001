import type { QuarterSummaryData, DetailedQuarterData, QuarterData } from '../types';

/**
 * Load quarter summary data
 */
export async function loadQuarterSummary(quarter: string): Promise<QuarterSummaryData> {
  const response = await fetch(`/data/quarters/${quarter}.json`);

  if (!response.ok) {
    throw new Error(`Failed to load data for ${quarter}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Load quarter detailed data
 */
export async function loadQuarterDetailed(quarter: string): Promise<DetailedQuarterData> {
  const response = await fetch(`/data/quarters/${quarter}-detailed.json`);

  if (!response.ok) {
    throw new Error(`Failed to load detailed data for ${quarter}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Load both summary and detailed data for a quarter
 */
export async function loadQuarterData(quarter: string): Promise<QuarterData> {
  const [summary, detailed] = await Promise.all([
    loadQuarterSummary(quarter),
    loadQuarterDetailed(quarter)
  ]);

  return { summary, detailed };
}

/**
 * Get list of available quarters
 * This could be dynamically loaded, but for now we'll hardcode
 */
export function getAvailableQuarters(): string[] {
  return ['2025-Q4', '2025-Q3', '2025-Q2', '2025-Q1'];
}

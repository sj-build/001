/**
 * Format currency value
 */
export function formatCurrency(value: number): string {
  if (value >= 1e12) {
    return `$${(value / 1e12).toFixed(2)}T`;
  } else if (value >= 1e9) {
    return `$${(value / 1e9).toFixed(2)}B`;
  } else if (value >= 1e6) {
    return `$${(value / 1e6).toFixed(2)}M`;
  } else if (value >= 1e3) {
    return `$${(value / 1e3).toFixed(2)}K`;
  } else {
    return `$${value.toFixed(2)}`;
  }
}

/**
 * Format number with commas
 */
export function formatNumber(value: number): string {
  return value.toLocaleString('en-US');
}

/**
 * Format percentage
 */
export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

/**
 * Format date
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

/**
 * Format valuation multiple (with null handling)
 */
export function formatMultiple(value: number | null): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }

  if (value < 0) {
    return 'N/A';
  }

  return value.toFixed(2);
}

/**
 * Format shares count
 */
export function formatShares(shares: number): string {
  if (shares >= 1e9) {
    return `${(shares / 1e9).toFixed(2)}B`;
  } else if (shares >= 1e6) {
    return `${(shares / 1e6).toFixed(2)}M`;
  } else if (shares >= 1e3) {
    return `${(shares / 1e3).toFixed(2)}K`;
  } else {
    return shares.toFixed(0);
  }
}

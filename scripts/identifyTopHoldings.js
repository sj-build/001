/**
 * Identify top 1 holding for each hedge fund
 * @param {Array} fundsData - Array of fund holdings data
 * @returns {Array} Array of top holdings by fund
 */
function identifyTopHoldings(fundsData) {
  console.log('\n=== Identifying top holdings for each fund ===\n');

  const fundTopHoldings = [];

  for (const fundData of fundsData) {
    // Sort holdings by value descending
    const sortedHoldings = [...fundData.holdings].sort((a, b) => b.value - a.value);

    if (sortedHoldings.length === 0) {
      console.warn(`No holdings found for ${fundData.fundName}`);
      continue;
    }

    const topHolding = sortedHoldings[0];
    const fundTotalValue = fundData.holdings.reduce((sum, h) => sum + h.value, 0);

    fundTopHoldings.push({
      fundName: fundData.fundName,
      fundCik: fundData.fundCik,
      topHolding: {
        ticker: '', // Will be enriched later
        companyName: topHolding.companyName,
        cusip: topHolding.cusip,
        value: topHolding.value,
        shares: topHolding.shares,
        percentOfPortfolio: (topHolding.value / fundTotalValue) * 100,
        // These will be added later by fetchStockData.py
        priceHistory: [],
        valuationMetrics: {
          peRatio: null,
          pbRatio: null,
          psRatio: null,
          evToEbitda: null,
          marketCap: 0,
          lastUpdated: ''
        }
      }
    });

    console.log(`${fundData.fundName}: ${topHolding.companyName} ($${(topHolding.value / 1e9).toFixed(2)}B, ${((topHolding.value / fundTotalValue) * 100).toFixed(2)}%)`);
  }

  console.log(`\n=== Found top holdings for ${fundTopHoldings.length} funds ===\n`);

  return fundTopHoldings;
}

/**
 * Extract unique CUSIPs from top holdings
 * @param {Array} fundTopHoldings - Array of top holdings by fund
 * @returns {Array} Array of unique CUSIP objects
 */
function getUniqueCusips(fundTopHoldings) {
  const cusipMap = new Map();

  for (const fund of fundTopHoldings) {
    const cusip = fund.topHolding.cusip;
    if (!cusipMap.has(cusip)) {
      cusipMap.set(cusip, {
        cusip,
        companyName: fund.topHolding.companyName
      });
    }
  }

  return Array.from(cusipMap.values());
}

module.exports = {
  identifyTopHoldings,
  getUniqueCusips
};

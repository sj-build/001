/**
 * Identify top 1 holding for each hedge fund (most purchased stock vs previous quarter)
 * @param {Array} fundsData - Array of fund holdings data for current quarter
 * @param {Array} previousFundsData - Optional array of fund holdings data for previous quarter
 * @returns {Array} Array of top holdings by fund
 */
function identifyTopHoldings(fundsData, previousFundsData = null) {
  console.log('\n=== Identifying most purchased stocks for each fund ===\n');

  const fundTopHoldings = [];

  for (const fundData of fundsData) {
    const fundTotalValue = fundData.holdings.reduce((sum, h) => sum + h.value, 0);

    // Find previous quarter data for this fund if available
    const previousData = previousFundsData?.find(f => f.fundCik === fundData.fundCik);

    if (previousData) {
      // Calculate position changes for all holdings
      const holdingsWithChanges = fundData.holdings.map(currentHolding => {
        const previousHolding = previousData.holdings.find(h => h.cusip === currentHolding.cusip);
        const previousTotalValue = previousData.holdings.reduce((sum, h) => sum + h.value, 0);

        if (previousHolding) {
          // Position existed in previous quarter - calculate change
          const valueChange = currentHolding.value - previousHolding.value;
          const sharesChange = currentHolding.shares - previousHolding.shares;
          const percentChange = ((currentHolding.value - previousHolding.value) / previousHolding.value) * 100;

          return {
            ...currentHolding,
            valueChange,
            sharesChange,
            percentChange,
            previousValue: previousHolding.value,
            previousShares: previousHolding.shares,
            previousPercentOfPortfolio: (previousHolding.value / previousTotalValue) * 100
          };
        } else {
          // New position - entire value is increase
          return {
            ...currentHolding,
            valueChange: currentHolding.value,
            sharesChange: currentHolding.shares,
            percentChange: Infinity, // New position
            previousValue: 0,
            previousShares: 0,
            previousPercentOfPortfolio: 0
          };
        }
      });

      // Filter to only positions that increased, then sort by absolute value change
      const increasedPositions = holdingsWithChanges.filter(h => h.valueChange > 0);
      increasedPositions.sort((a, b) => b.valueChange - a.valueChange);

      if (increasedPositions.length === 0) {
        console.warn(`No increased positions found for ${fundData.fundName}`);
        continue;
      }

      const mostPurchased = increasedPositions[0];

      fundTopHoldings.push({
        fundName: fundData.fundName,
        fundCik: fundData.fundCik,
        mostPurchased: {
          ticker: '', // Will be enriched later
          companyName: mostPurchased.companyName,
          cusip: mostPurchased.cusip,
          value: mostPurchased.value,
          shares: mostPurchased.shares,
          percentOfPortfolio: (mostPurchased.value / fundTotalValue) * 100,
          positionChange: {
            previousQuarter: {
              value: mostPurchased.previousValue,
              shares: mostPurchased.previousShares,
              percentOfPortfolio: mostPurchased.previousPercentOfPortfolio
            },
            currentQuarter: {
              value: mostPurchased.value,
              shares: mostPurchased.shares,
              percentOfPortfolio: (mostPurchased.value / fundTotalValue) * 100
            },
            change: {
              valueChange: mostPurchased.valueChange,
              sharesChange: mostPurchased.sharesChange,
              percentChange: mostPurchased.percentChange
            }
          },
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

      console.log(`${fundData.fundName}: ${mostPurchased.companyName} (+$${(mostPurchased.valueChange / 1e9).toFixed(2)}B, ${mostPurchased.percentChange === Infinity ? 'NEW' : '+' + mostPurchased.percentChange.toFixed(1) + '%'})`);

    } else {
      // No previous quarter data - fall back to largest holding
      const sortedHoldings = [...fundData.holdings].sort((a, b) => b.value - a.value);

      if (sortedHoldings.length === 0) {
        console.warn(`No holdings found for ${fundData.fundName}`);
        continue;
      }

      const topHolding = sortedHoldings[0];

      fundTopHoldings.push({
        fundName: fundData.fundName,
        fundCik: fundData.fundCik,
        mostPurchased: {
          ticker: '', // Will be enriched later
          companyName: topHolding.companyName,
          cusip: topHolding.cusip,
          value: topHolding.value,
          shares: topHolding.shares,
          percentOfPortfolio: (topHolding.value / fundTotalValue) * 100,
          positionChange: null, // No previous quarter data
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

      console.log(`${fundData.fundName}: ${topHolding.companyName} ($${(topHolding.value / 1e9).toFixed(2)}B, ${((topHolding.value / fundTotalValue) * 100).toFixed(2)}%) [No previous quarter data]`);
    }
  }

  console.log(`\n=== Found most purchased stocks for ${fundTopHoldings.length} funds ===\n`);

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
    const cusip = fund.mostPurchased.cusip;
    if (!cusipMap.has(cusip)) {
      cusipMap.set(cusip, {
        cusip,
        companyName: fund.mostPurchased.companyName
      });
    }
  }

  return Array.from(cusipMap.values());
}

module.exports = {
  identifyTopHoldings,
  getUniqueCusips
};

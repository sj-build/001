/**
 * Aggregate holdings across multiple hedge funds
 * @param {Array} fundsData - Array of fund holdings data
 * @returns {Object} Aggregated top stocks
 */
function aggregateHoldings(fundsData) {
  console.log('\n=== Aggregating holdings across funds ===\n');

  // Map to store aggregated holdings by CUSIP
  const holdingsMap = new Map();

  let totalAUM = 0;

  // Iterate through each fund's holdings
  for (const fundData of fundsData) {
    console.log(`Processing ${fundData.holdings.length} holdings from ${fundData.fundName}`);

    const fundTotalValue = fundData.holdings.reduce((sum, h) => sum + h.value, 0);
    totalAUM += fundTotalValue;

    for (const holding of fundData.holdings) {
      const cusip = holding.cusip;

      if (!holdingsMap.has(cusip)) {
        holdingsMap.set(cusip, {
          cusip,
          companyName: holding.companyName,
          ticker: '', // Will be enriched later
          totalValue: 0,
          totalShares: 0,
          fundsHolding: [],
          numberOfFundsHolding: 0
        });
      }

      const aggregated = holdingsMap.get(cusip);
      aggregated.totalValue += holding.value;
      aggregated.totalShares += holding.shares;

      aggregated.fundsHolding.push({
        fundName: fundData.fundName,
        value: holding.value,
        shares: holding.shares,
        percentOfFundPortfolio: (holding.value / fundTotalValue) * 100
      });

      aggregated.numberOfFundsHolding = aggregated.fundsHolding.length;
    }
  }

  // Convert map to array and sort by total value
  const allHoldings = Array.from(holdingsMap.values())
    .sort((a, b) => b.totalValue - a.totalValue);

  // Get top 10
  const top10 = allHoldings.slice(0, 10).map((holding, index) => ({
    rank: index + 1,
    cusip: holding.cusip,
    ticker: holding.ticker,
    companyName: holding.companyName,
    totalValue: holding.totalValue,
    totalShares: holding.totalShares,
    numberOfFundsHolding: holding.numberOfFundsHolding,
    percentOfTotalAUM: (holding.totalValue / totalAUM) * 100,
    holdingsByFund: holding.fundsHolding.sort((a, b) => b.value - a.value)
  }));

  console.log('\n=== Top 10 Most Invested Stocks ===');
  top10.forEach(stock => {
    console.log(`${stock.rank}. ${stock.companyName} - $${(stock.totalValue / 1e9).toFixed(2)}B`);
  });

  return {
    topStocks: top10,
    metadata: {
      totalFundsAnalyzed: fundsData.length,
      totalAUMAggregated: totalAUM,
      uniqueStocksHeld: holdingsMap.size,
      dataQuality: fundsData.length === 10 ? 'complete' : 'partial'
    }
  };
}

module.exports = {
  aggregateHoldings
};

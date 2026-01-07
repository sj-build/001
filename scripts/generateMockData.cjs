#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');
const config = require('./config.cjs');

/**
 * Generate mock data for testing the UI
 */
async function generateMockData(category = 'guru') {
  console.log(`Generating mock data for category: ${category}...\n`);

  const quarter = '2025-Q4';
  const quarterEnd = '2025-12-31';

  // Get investors for the specified category
  const categoryConfig = config.investorCategories[category];
  if (!categoryConfig) {
    throw new Error(`Invalid category: ${category}. Must be 'guru' or 'emerging'`);
  }

  const investors = categoryConfig.investors;
  const mockFunds = investors.map(inv => inv.name);

  console.log(`Using ${mockFunds.length} ${category} investors`);

  // Mock price history (1 year of daily prices)
  function generatePriceHistory(startPrice) {
    const prices = [];
    let price = startPrice;
    const today = new Date();

    for (let i = 365; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);

      // Random walk
      price = price * (1 + (Math.random() - 0.48) * 0.02);

      prices.push({
        date: date.toISOString().split('T')[0],
        close: parseFloat(price.toFixed(2))
      });
    }

    return prices;
  }

  // Mock stocks
  const mockStocks = [
    { ticker: 'AAPL', name: 'Apple Inc.', cusip: '037833100', price: 180 },
    { ticker: 'MSFT', name: 'Microsoft Corp.', cusip: '594918104', price: 380 },
    { ticker: 'NVDA', name: 'NVIDIA Corp.', cusip: '67066G104', price: 495 },
    { ticker: 'GOOGL', name: 'Alphabet Inc.', cusip: '02079K305', price: 140 },
    { ticker: 'AMZN', name: 'Amazon.com Inc.', cusip: '023135106', price: 175 },
    { ticker: 'META', name: 'Meta Platforms Inc.', cusip: '30303M102', price: 350 },
    { ticker: 'TSLA', name: 'Tesla Inc.', cusip: '88160R101', price: 250 },
    { ticker: 'BRK.B', name: 'Berkshire Hathaway Inc.', cusip: '084670702', price: 380 },
    { ticker: 'JPM', name: 'JPMorgan Chase & Co.', cusip: '46625H100', price: 165 },
    { ticker: 'V', name: 'Visa Inc.', cusip: '92826C839', price: 270 }
  ];

  // Generate summary data (top 10 aggregated stocks)
  const summaryData = {
    quarter,
    quarterEnd,
    filingDeadline: '2026-02-17',
    generatedAt: new Date().toISOString(),
    hedgeFunds: investors.map((inv, i) => ({
      name: inv.name,
      cik: inv.cik,
      totalAUM: 50e9 + Math.random() * 50e9,
      filingDate: '2026-02-10',
      category: inv.category,
      metadata: inv.metadata
    })),
    topStocks: mockStocks.map((stock, i) => ({
      rank: i + 1,
      cusip: stock.cusip,
      ticker: stock.ticker,
      companyName: stock.name,
      totalValue: (150 - i * 10) * 1e9 + Math.random() * 10e9,
      totalShares: (500 - i * 30) * 1e6 + Math.random() * 50e6,
      numberOfFundsHolding: 10 - i,
      percentOfTotalAUM: (15 - i * 1.2) + Math.random() * 2,
      holdingsByFund: mockFunds.slice(0, 10 - i).map(fundName => ({
        fundName,
        value: (10 - i) * 1e9 + Math.random() * 5e9,
        shares: (40 - i * 3) * 1e6 + Math.random() * 10e6,
        percentOfFundPortfolio: (8 - i * 0.5) + Math.random() * 2
      }))
    })),
    metadata: {
      totalFundsAnalyzed: investors.length,
      totalAUMAggregated: 750e9,
      uniqueStocksHeld: 1234,
      dataQuality: 'complete',
      category: category
    }
  };

  // Generate detailed data (each fund's most purchased stock vs previous quarter)
  const detailedData = {
    quarter,
    category: category,
    fundTopHoldings: investors.map((inv, i) => {
      const stock = mockStocks[i];
      const currentValue = 30e9 + Math.random() * 20e9;
      const currentShares = currentValue / stock.price;
      const currentPercent = 5 + Math.random() * 10;

      // Generate previous quarter data (simulate a position that was increased)
      // Previous position was 40-70% of current position size
      const previousSizeRatio = 0.4 + Math.random() * 0.3;
      const previousValue = currentValue * previousSizeRatio;
      const previousShares = currentShares * previousSizeRatio;
      const previousPercent = currentPercent * previousSizeRatio;

      // Calculate changes
      const valueChange = currentValue - previousValue;
      const sharesChange = currentShares - previousShares;
      const percentChange = ((currentValue - previousValue) / previousValue) * 100;

      return {
        fundName: inv.name,
        fundCik: inv.cik,
        category: inv.category,
        metadata: inv.metadata,
        mostPurchased: {
          ticker: stock.ticker,
          companyName: stock.name,
          cusip: stock.cusip,
          value: currentValue,
          shares: currentShares,
          percentOfPortfolio: currentPercent,
          positionChange: {
            previousQuarter: {
              value: previousValue,
              shares: previousShares,
              percentOfPortfolio: previousPercent
            },
            currentQuarter: {
              value: currentValue,
              shares: currentShares,
              percentOfPortfolio: currentPercent
            },
            change: {
              valueChange,
              sharesChange,
              percentChange
            }
          },
          priceHistory: generatePriceHistory(stock.price),
          valuationMetrics: {
            peRatio: 15 + Math.random() * 30,
            pbRatio: 3 + Math.random() * 10,
            psRatio: 2 + Math.random() * 8,
            evToEbitda: 10 + Math.random() * 15,
            marketCap: 500e9 + Math.random() * 2000e9,
            lastUpdated: new Date().toISOString()
          }
        }
      };
    })
  };

  // Write to files with category prefix
  const dataDir = path.join(__dirname, '..', 'public', 'data', 'quarters');
  await fs.mkdir(dataDir, { recursive: true });

  const summaryPath = path.join(dataDir, `${category}-${quarter}.json`);
  const detailedPath = path.join(dataDir, `${category}-${quarter}-detailed.json`);

  await fs.writeFile(summaryPath, JSON.stringify(summaryData, null, 2));
  await fs.writeFile(detailedPath, JSON.stringify(detailedData, null, 2));

  console.log(`✓ Generated mock data for ${category} - ${quarter}`);
  console.log(`  Summary: ${summaryPath}`);
  console.log(`  Detailed: ${detailedPath}`);
}

// Parse CLI arguments
const args = process.argv.slice(2);
let category = 'guru'; // default

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--category' && args[i + 1]) {
    category = args[i + 1];
  }
}

// Generate for the specified category
generateMockData(category)
  .then(() => {
    console.log('\nMock data generated successfully!');
    console.log(`\nTo generate for other category, run:`);
    console.log(`  node scripts/generateMockData.cjs --category ${category === 'guru' ? 'emerging' : 'guru'}`);
    console.log(`\nYou can now run: npm run dev`);
    process.exit(0);
  })
  .catch((err) => {
    console.error('Error:', err);
    process.exit(1);
  });

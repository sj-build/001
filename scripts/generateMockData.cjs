#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');

/**
 * Generate mock data for testing the UI
 */
async function generateMockData() {
  console.log('Generating mock data for testing...\n');

  const quarter = '2025-Q4';
  const quarterEnd = '2025-12-31';

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

  // Mock hedge funds
  const mockFunds = [
    'Bridgewater Associates, LP',
    'Citadel Advisors LLC',
    'Millennium Management LLC',
    'Two Sigma Investments, LP',
    'Renaissance Technologies LLC',
    'D.E. Shaw & Co., Inc.',
    'AQR Capital Management LLC',
    'Elliott Management Corp',
    'Point72 Asset Management',
    'Farallon Capital Management'
  ];

  // Generate summary data (top 10 aggregated stocks)
  const summaryData = {
    quarter,
    quarterEnd,
    filingDeadline: '2026-02-17',
    generatedAt: new Date().toISOString(),
    hedgeFunds: mockFunds.map((name, i) => ({
      name,
      cik: `000${1000000 + i}`,
      totalAUM: 50e9 + Math.random() * 50e9,
      filingDate: '2026-02-10'
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
      totalFundsAnalyzed: 10,
      totalAUMAggregated: 750e9,
      uniqueStocksHeld: 1234,
      dataQuality: 'complete'
    }
  };

  // Generate detailed data (each fund's top 1 holding)
  const detailedData = {
    quarter,
    fundTopHoldings: mockFunds.map((fundName, i) => {
      const stock = mockStocks[i];
      const value = 30e9 + Math.random() * 20e9;

      return {
        fundName,
        fundCik: `000${1000000 + i}`,
        topHolding: {
          ticker: stock.ticker,
          companyName: stock.name,
          cusip: stock.cusip,
          value,
          shares: value / stock.price,
          percentOfPortfolio: 5 + Math.random() * 10,
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

  // Write to files
  const dataDir = path.join(__dirname, '..', 'public', 'data', 'quarters');
  await fs.mkdir(dataDir, { recursive: true });

  const summaryPath = path.join(dataDir, `${quarter}.json`);
  const detailedPath = path.join(dataDir, `${quarter}-detailed.json`);

  await fs.writeFile(summaryPath, JSON.stringify(summaryData, null, 2));
  await fs.writeFile(detailedPath, JSON.stringify(detailedData, null, 2));

  console.log(`✓ Generated mock data for ${quarter}`);
  console.log(`  Summary: ${summaryPath}`);
  console.log(`  Detailed: ${detailedPath}`);
  console.log('\nYou can now run: npm run dev');
}

generateMockData()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error('Error:', err);
    process.exit(1);
  });

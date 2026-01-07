#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
const { fetchAll13Fs } = require('./fetch13F.cjs');
const { aggregateHoldings } = require('./aggregator.cjs');
const { identifyTopHoldings } = require('./identifyTopHoldings.cjs');
const config = require('./config.cjs');

/**
 * Run Python script to enrich stock data
 * @param {Array} fundTopHoldings - Array of fund top holdings
 * @returns {Promise<Array>} Enriched holdings
 */
function enrichStockData(fundTopHoldings) {
  return new Promise((resolve, reject) => {
    console.log('\n=== Calling Python script to fetch stock data ===\n');

    const pythonScript = path.join(__dirname, 'fetchStockData.py');
    const python = spawn('python3', [pythonScript]);

    let outputData = '';
    let errorData = '';

    // Send input data to Python script via stdin
    python.stdin.write(JSON.stringify(fundTopHoldings));
    python.stdin.end();

    python.stdout.on('data', (data) => {
      const text = data.toString();
      // Filter out log messages (lines not starting with [ or {)
      if (text.trim().startsWith('[') || text.trim().startsWith('{')) {
        outputData += text;
      } else {
        console.log(text.trim());
      }
    });

    python.stderr.on('data', (data) => {
      errorData += data.toString();
      console.error(data.toString());
    });

    python.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Python script exited with code ${code}: ${errorData}`));
      } else {
        try {
          const enrichedData = JSON.parse(outputData);
          resolve(enrichedData);
        } catch (err) {
          reject(new Error(`Failed to parse Python output: ${err.message}\nOutput: ${outputData}`));
        }
      }
    });
  });
}

/**
 * Build quarter data JSON files
 * @param {string} quarterEnd - Quarter end date (YYYY-MM-DD)
 * @param {string} quarter - Quarter label (e.g., '2025-Q4')
 * @param {string} category - Investor category ('guru' or 'emerging')
 */
async function buildQuarterData(quarterEnd, quarter, category = 'guru') {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Building data for quarter: ${quarter} (ending ${quarterEnd})`);
  console.log(`Category: ${category}`);
  console.log(`${'='.repeat(60)}\n`);

  // Get investors for the specified category
  const categoryConfig = config.investorCategories[category];
  if (!categoryConfig) {
    throw new Error(`Invalid category: ${category}. Must be 'guru' or 'emerging'`);
  }

  const investors = categoryConfig.investors;
  console.log(`Using ${investors.length} ${category} investors\n`);

  try {
    // Step 1: Fetch 13F filings for current quarter
    const fundsData = await fetchAll13Fs(quarterEnd, investors);

    if (fundsData.length === 0) {
      console.error('No fund data retrieved. Aborting.');
      process.exit(1);
    }

    // Step 1.5: Try to fetch previous quarter data for QoQ comparison
    let previousFundsData = null;
    const currentQuarterIndex = config.quarters.findIndex(q => q.quarter === quarter);

    if (currentQuarterIndex >= 0 && currentQuarterIndex < config.quarters.length - 1) {
      const previousQuarter = config.quarters[currentQuarterIndex + 1];
      console.log(`\nAttempting to fetch previous quarter data (${previousQuarter.quarter}) for QoQ comparison...\n`);

      try {
        previousFundsData = await fetchAll13Fs(previousQuarter.quarterEnd, investors);
        console.log(`Successfully loaded ${previousFundsData.length} funds from previous quarter\n`);
      } catch (err) {
        console.log(`Could not fetch previous quarter data: ${err.message}`);
        console.log('Will proceed without QoQ comparison\n');
      }
    }

    // Step 2: Aggregate holdings to find top 10 stocks
    const { topStocks, metadata } = aggregateHoldings(fundsData);

    // Step 3: Identify most purchased stock for each fund (vs previous quarter if available)
    const fundTopHoldings = identifyTopHoldings(fundsData, previousFundsData);

    // Step 4: Enrich top holdings with stock data (price history + valuation)
    let enrichedTopHoldings = fundTopHoldings;

    try {
      enrichedTopHoldings = await enrichStockData(fundTopHoldings);
      console.log('Stock data enrichment completed');
    } catch (err) {
      console.error('Failed to enrich stock data:', err.message);
      console.log('Continuing with unenriched data...');
    }

    // Step 5: Build summary data structure
    const summaryData = {
      quarter,
      quarterEnd,
      filingDeadline: config.quarters.find(q => q.quarter === quarter)?.filingDeadline || '',
      generatedAt: new Date().toISOString(),
      hedgeFunds: fundsData.map(fd => {
        const investor = investors.find(inv => inv.cik === fd.fundCik);
        return {
          name: fd.fundName,
          cik: fd.fundCik,
          totalAUM: fd.holdings.reduce((sum, h) => sum + h.value, 0),
          filingDate: fd.filingDate,
          category: category,
          metadata: investor?.metadata || {}
        };
      }),
      topStocks,
      metadata: {
        ...metadata,
        category: category
      }
    };

    // Step 6: Build detailed data structure
    const detailedData = {
      quarter,
      category: category,
      fundTopHoldings: enrichedTopHoldings.map(fth => {
        const investor = investors.find(inv => inv.cik === fth.fundCik);
        return {
          ...fth,
          category: category,
          metadata: investor?.metadata || {}
        };
      })
    };

    // Step 7: Write JSON files
    const dataDir = path.join(__dirname, '..', 'public', 'data', 'quarters');

    // Ensure directory exists
    await fs.mkdir(dataDir, { recursive: true });

    const summaryPath = path.join(dataDir, `${category}-${quarter}.json`);
    const detailedPath = path.join(dataDir, `${category}-${quarter}-detailed.json`);

    await fs.writeFile(summaryPath, JSON.stringify(summaryData, null, 2));
    await fs.writeFile(detailedPath, JSON.stringify(detailedData, null, 2));

    console.log(`\n${'='.repeat(60)}`);
    console.log(`✓ Successfully built quarter data for ${quarter}`);
    console.log(`  Summary: ${summaryPath}`);
    console.log(`  Detailed: ${detailedPath}`);
    console.log(`${'='.repeat(60)}\n`);

  } catch (error) {
    console.error('Error building quarter data:', error);
    throw error;
  }
}

// CLI usage
if (require.main === module) {
  const args = process.argv.slice(2);

  // Parse arguments
  let quarter = null;
  let category = 'guru'; // default

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--quarter' && args[i + 1]) {
      quarter = args[i + 1];
      i++;
    } else if (args[i] === '--category' && args[i + 1]) {
      category = args[i + 1];
      i++;
    }
  }

  if (!quarter) {
    console.log('Usage: node buildQuarterData.js --quarter <YYYY-QX> [--category <guru|emerging>]');
    console.log('Example: node buildQuarterData.js --quarter 2025-Q3 --category guru');
    console.log('\nAvailable quarters:');
    config.quarters.forEach(q => {
      console.log(`  ${q.quarter} (ends ${q.quarterEnd}, deadline ${q.filingDeadline})`);
    });
    console.log('\nAvailable categories: guru, emerging (default: guru)');
    process.exit(1);
  }

  const quarterInfo = config.quarters.find(q => q.quarter === quarter);

  if (!quarterInfo) {
    console.error(`Invalid quarter: ${quarter}`);
    console.log('Available quarters:');
    config.quarters.forEach(q => {
      console.log(`  ${q.quarter}`);
    });
    process.exit(1);
  }

  if (!['guru', 'emerging'].includes(category)) {
    console.error(`Invalid category: ${category}. Must be 'guru' or 'emerging'`);
    process.exit(1);
  }

  buildQuarterData(quarterInfo.quarterEnd, quarterInfo.quarter, category)
    .then(() => {
      console.log('Build completed successfully!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('Build failed:', error);
      process.exit(1);
    });
}

module.exports = {
  buildQuarterData
};

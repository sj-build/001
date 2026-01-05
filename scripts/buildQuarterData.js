#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
const { fetchAll13Fs } = require('./fetch13F');
const { aggregateHoldings } = require('./aggregator');
const { identifyTopHoldings } = require('./identifyTopHoldings');
const config = require('./config');

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
 */
async function buildQuarterData(quarterEnd, quarter) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Building data for quarter: ${quarter} (ending ${quarterEnd})`);
  console.log(`${'='.repeat(60)}\n`);

  try {
    // Step 1: Fetch 13F filings
    const fundsData = await fetchAll13Fs(quarterEnd);

    if (fundsData.length === 0) {
      console.error('No fund data retrieved. Aborting.');
      process.exit(1);
    }

    // Step 2: Aggregate holdings to find top 10 stocks
    const { topStocks, metadata } = aggregateHoldings(fundsData);

    // Step 3: Identify top 1 holding for each fund
    const fundTopHoldings = identifyTopHoldings(fundsData);

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
      hedgeFunds: fundsData.map(fd => ({
        name: fd.fundName,
        cik: fd.fundCik,
        totalAUM: fd.holdings.reduce((sum, h) => sum + h.value, 0),
        filingDate: fd.filingDate
      })),
      topStocks,
      metadata
    };

    // Step 6: Build detailed data structure
    const detailedData = {
      quarter,
      fundTopHoldings: enrichedTopHoldings
    };

    // Step 7: Write JSON files
    const dataDir = path.join(__dirname, '..', 'public', 'data', 'quarters');

    // Ensure directory exists
    await fs.mkdir(dataDir, { recursive: true });

    const summaryPath = path.join(dataDir, `${quarter}.json`);
    const detailedPath = path.join(dataDir, `${quarter}-detailed.json`);

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

  if (args.length < 2 || args[0] !== '--quarter') {
    console.log('Usage: node buildQuarterData.js --quarter <YYYY-QX>');
    console.log('Example: node buildQuarterData.js --quarter 2025-Q4');
    console.log('\nAvailable quarters:');
    config.quarters.forEach(q => {
      console.log(`  ${q.quarter} (ends ${q.quarterEnd}, deadline ${q.filingDeadline})`);
    });
    process.exit(1);
  }

  const quarter = args[1];
  const quarterInfo = config.quarters.find(q => q.quarter === quarter);

  if (!quarterInfo) {
    console.error(`Invalid quarter: ${quarter}`);
    console.log('Available quarters:');
    config.quarters.forEach(q => {
      console.log(`  ${q.quarter}`);
    });
    process.exit(1);
  }

  buildQuarterData(quarterInfo.quarterEnd, quarterInfo.quarter)
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

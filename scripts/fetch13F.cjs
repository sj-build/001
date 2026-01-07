const axios = require('axios');
const { parse13FXML } = require('./parsers/xml13FParser.cjs');
const config = require('./config.cjs');

/**
 * Sleep utility for rate limiting
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Fetch 13F filing for a specific hedge fund and quarter
 * @param {Object} fund - Hedge fund object with name and CIK
 * @param {string} quarterEnd - Quarter end date (YYYY-MM-DD)
 * @returns {Object} Fund holdings data
 */
async function fetch13FForFund(fund, quarterEnd) {
  console.log(`\nFetching 13F for ${fund.name} (CIK: ${fund.cik})...`);

  try {
    // Step 1: Get submissions index for the fund
    const submissionsUrl = `${config.sec.baseUrl}/submissions/CIK${fund.cik}.json`;
    const submissionsResponse = await axios.get(submissionsUrl, {
      headers: {
        'User-Agent': config.sec.userAgent
      }
    });

    await sleep(config.sec.rateLimit);

    const submissions = submissionsResponse.data;
    const recentFilings = submissions.filings?.recent;

    if (!recentFilings) {
      console.warn(`No recent filings found for ${fund.name}`);
      return null;
    }

    // Step 2: Find 13F-HR filing for the target quarter
    const quarterEndDate = new Date(quarterEnd);

    // 13F filings are due 45 days after quarter end
    // Look for filings between quarter end and 75 days after (to account for amendments)
    const minFilingDate = new Date(quarterEndDate);
    minFilingDate.setDate(minFilingDate.getDate() + 1); // Day after quarter end

    const maxFilingDate = new Date(quarterEndDate);
    maxFilingDate.setDate(maxFilingDate.getDate() + 75); // 75 days buffer

    let filing13F = null;

    for (let i = 0; i < recentFilings.form.length; i++) {
      const form = recentFilings.form[i];
      const filingDate = recentFilings.filingDate[i];
      const accessionNumber = recentFilings.accessionNumber[i];
      const primaryDocument = recentFilings.primaryDocument[i];

      // Look for 13F-HR forms
      if (form === '13F-HR' || form === '13F-HR/A') {
        const filingDateObj = new Date(filingDate);

        // Check if filing is within the date range for this quarter
        if (filingDateObj >= minFilingDate && filingDateObj <= maxFilingDate) {
          filing13F = {
            accessionNumber: accessionNumber.replace(/-/g, ''),
            primaryDocument,
            filingDate
          };
          console.log(`Found 13F filing: ${filingDate} (for quarter ending ${quarterEnd})`);
          break;
        }
      }
    }

    if (!filing13F) {
      console.warn(`No 13F filing found for ${fund.name} in target quarter`);
      return null;
    }

    // Step 3: Fetch the filing index to find actual files
    const cikNumber = fund.cik.replace(/^0+/, ''); // Remove leading zeros
    const accessionNumberFormatted = filing13F.accessionNumber.replace(/(\d{10})(\d{2})(\d{6})/, '$1-$2-$3');

    // Build the index.htm URL
    const indexUrl = `https://www.sec.gov/Archives/edgar/data/${cikNumber}/${filing13F.accessionNumber}/${accessionNumberFormatted}-index.htm`;

    console.log(`Fetching filing index for ${fund.name}...`);

    let xmlContent = '';

    try {
      const indexResponse = await axios.get(indexUrl, {
        headers: {
          'User-Agent': config.sec.userAgent
        }
      });

      await sleep(config.sec.rateLimit);

      const indexHtml = typeof indexResponse.data === 'string' ? indexResponse.data : indexResponse.data.toString();

      // Look for XML file links in the index page
      const xmlFileMatches = indexHtml.match(/href="([^"]*\.xml)"/gi) || [];
      const xmlFiles = xmlFileMatches.map(match => match.match(/href="([^"]*)"/i)[1]);

      console.log(`  Found ${xmlFiles.length} XML files in index`);

      // Try each unique XML file
      const uniqueXmlFiles = [...new Set(xmlFiles)];

      for (const xmlFile of uniqueXmlFiles) {
        try {
          const xmlUrl = xmlFile.startsWith('http') || xmlFile.startsWith('/')
            ? (xmlFile.startsWith('http') ? xmlFile : `https://www.sec.gov${xmlFile}`)
            : `https://www.sec.gov/Archives/edgar/data/${cikNumber}/${filing13F.accessionNumber}/${xmlFile}`;

          console.log(`  Trying: ${xmlFile}`);

          const xmlResponse = await axios.get(xmlUrl, {
            headers: {
              'User-Agent': config.sec.userAgent
            }
          });

          await sleep(config.sec.rateLimit);

          const content = typeof xmlResponse.data === 'string' ? xmlResponse.data : xmlResponse.data.toString();

          if (content.includes('<informationTable') || content.includes('infoTable')) {
            xmlContent = content;
            console.log(`  ✓ Found information table in ${xmlFile}`);
            break;
          } else {
            console.log(`    (no info table found)`);
          }
        } catch (err) {
          console.log(`    (error: ${err.message.substring(0, 50)})`);
          continue;
        }
      }
    } catch (indexErr) {
      console.log(`  Could not fetch index page: ${indexErr.message}`);
    }

    if (!xmlContent) {
      console.warn(`Could not find valid XML file for ${fund.name}`);
      return null;
    }

    // Step 4: Parse the XML
    console.log(`Parsing XML for ${fund.name} (${xmlContent.length} bytes)...`);
    const holdings = parse13FXML(xmlContent);

    if (holdings.length === 0) {
      console.warn(`No holdings parsed for ${fund.name}`);
      return null;
    }

    console.log(`Parsed ${holdings.length} holdings for ${fund.name}`);

    return {
      fundName: fund.name,
      fundCik: fund.cik,
      filingDate: filing13F.filingDate,
      holdings
    };

  } catch (error) {
    console.error(`Error fetching 13F for ${fund.name}:`, error.message);
    return null;
  }
}

/**
 * Fetch 13F filings for all hedge funds for a specific quarter
 * @param {string} quarterEnd - Quarter end date (YYYY-MM-DD)
 * @param {Array} investors - Optional custom list of investors (defaults to config.hedgeFunds)
 * @returns {Array} Array of fund holdings data
 */
async function fetchAll13Fs(quarterEnd, investors = null) {
  console.log(`\n=== Fetching 13F filings for quarter ending ${quarterEnd} ===\n`);

  const fundsList = investors || config.hedgeFunds;
  const results = [];

  for (const fund of fundsList) {
    const fundData = await fetch13FForFund(fund, quarterEnd);

    if (fundData) {
      results.push(fundData);
    }

    // Extra delay between funds to be respectful to SEC servers
    await sleep(config.sec.rateLimit * 2);
  }

  console.log(`\n=== Completed: Fetched data for ${results.length}/${config.hedgeFunds.length} funds ===\n`);

  return results;
}

module.exports = {
  fetch13FForFund,
  fetchAll13Fs
};

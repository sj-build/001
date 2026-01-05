const axios = require('axios');
const { parse13FXML } = require('./parsers/xml13FParser');
const config = require('./config');

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
    const targetYear = new Date(quarterEnd).getFullYear();
    const targetMonth = new Date(quarterEnd).getMonth();
    const targetQuarter = Math.floor(targetMonth / 3) + 1;

    let filing13F = null;

    for (let i = 0; i < recentFilings.form.length; i++) {
      const form = recentFilings.form[i];
      const filingDate = recentFilings.filingDate[i];
      const accessionNumber = recentFilings.accessionNumber[i];
      const primaryDocument = recentFilings.primaryDocument[i];

      // Look for 13F-HR forms
      if (form === '13F-HR' || form === '13F-HR/A') {
        const filingYear = new Date(filingDate).getFullYear();

        // Check if filing is for the target quarter (filings are typically 45 days after quarter end)
        if (filingYear === targetYear || filingYear === targetYear + 1) {
          filing13F = {
            accessionNumber: accessionNumber.replace(/-/g, ''),
            primaryDocument,
            filingDate
          };
          console.log(`Found 13F filing: ${filingDate}`);
          break;
        }
      }
    }

    if (!filing13F) {
      console.warn(`No 13F filing found for ${fund.name} in target quarter`);
      return null;
    }

    // Step 3: Fetch the primary document (information table XML)
    // URL format: /Archives/edgar/data/{cik}/{accession}/{filename}
    const cikNumber = fund.cik.replace(/^0+/, ''); // Remove leading zeros
    const docUrl = `${config.sec.baseUrl}/Archives/edgar/data/${cikNumber}/${filing13F.accessionNumber}/${filing13F.primaryDocument}`;

    console.log(`Fetching document: ${docUrl}`);

    const documentResponse = await axios.get(docUrl, {
      headers: {
        'User-Agent': config.sec.userAgent
      }
    });

    await sleep(config.sec.rateLimit);

    // Step 4: Check if we got an XML document
    const content = documentResponse.data;
    let xmlContent = '';

    if (typeof content === 'string') {
      xmlContent = content;
    } else if (content) {
      xmlContent = content.toString();
    }

    // Step 5: Try to find the information table XML
    // Sometimes the primary document is an HTML wrapper, and the XML is in a separate file
    if (!xmlContent.includes('<informationTable') && !xmlContent.includes('infoTable')) {
      console.log('Primary document is not XML, looking for info table XML...');

      // Common information table filename patterns
      const possibleFilenames = [
        'primary_doc.xml',
        'form13fInfoTable.xml',
        'infotable.xml',
        filing13F.primaryDocument.replace('.txt', '.xml')
      ];

      for (const filename of possibleFilenames) {
        try {
          const xmlUrl = `${config.sec.baseUrl}/Archives/edgar/data/${cikNumber}/${filing13F.accessionNumber}/${filename}`;
          const xmlResponse = await axios.get(xmlUrl, {
            headers: {
              'User-Agent': config.sec.userAgent
            }
          });

          await sleep(config.sec.rateLimit);

          xmlContent = typeof xmlResponse.data === 'string' ? xmlResponse.data : xmlResponse.data.toString();

          if (xmlContent.includes('<informationTable') || xmlContent.includes('infoTable')) {
            console.log(`Found XML in ${filename}`);
            break;
          }
        } catch (err) {
          // File not found, continue
          continue;
        }
      }
    }

    // Step 6: Parse the XML
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
 * @returns {Array} Array of fund holdings data
 */
async function fetchAll13Fs(quarterEnd) {
  console.log(`\n=== Fetching 13F filings for quarter ending ${quarterEnd} ===\n`);

  const results = [];

  for (const fund of config.hedgeFunds) {
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

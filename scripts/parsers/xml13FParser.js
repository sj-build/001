const { XMLParser } = require('fast-xml-parser');

/**
 * Parse 13F XML filing and extract holdings information
 * @param {string} xmlContent - Raw XML content
 * @returns {Array} Array of holdings with cusip, shares, value, company name
 */
function parse13FXML(xmlContent) {
  const parser = new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: '@_'
  });

  try {
    const result = parser.parse(xmlContent);

    // 13F filings can have different XML structures
    // Most common: <edgarSubmission> or <informationTable>
    let holdings = [];

    // Try to find information table
    let infoTable = null;

    if (result.edgarSubmission && result.edgarSubmission.formData) {
      infoTable = result.edgarSubmission.formData.informationTable ||
                  result.edgarSubmission.informationTable;
    } else if (result.informationTable) {
      infoTable = result.informationTable;
    } else if (result.XML) {
      // Some filings have different root
      infoTable = result.XML.informationTable;
    }

    if (!infoTable) {
      console.warn('Could not find information table in XML');
      return [];
    }

    // infoTable can be an object with infoTable array, or direct array
    let infoTableEntries = infoTable.infoTable || infoTable;

    // Ensure it's an array
    if (!Array.isArray(infoTableEntries)) {
      infoTableEntries = [infoTableEntries];
    }

    // Parse each entry
    for (const entry of infoTableEntries) {
      try {
        const holding = {
          cusip: entry.cusip || '',
          companyName: entry.nameOfIssuer || '',
          titleOfClass: entry.titleOfClass || 'COM',
          value: parseFloat(entry.value || 0) * 1000, // SEC reports in thousands
          shares: 0
        };

        // Extract shares
        if (entry.shrsOrPrnAmt) {
          const shareData = entry.shrsOrPrnAmt;
          holding.shares = parseFloat(shareData.sshPrnamt || shareData.shrsOrPrnAmt || 0);
          holding.shareType = shareData.sshPrnamtType || 'SH';
        }

        // Only include if we have CUSIP and value
        if (holding.cusip && holding.value > 0) {
          holdings.push(holding);
        }
      } catch (err) {
        console.warn('Error parsing holding entry:', err.message);
        continue;
      }
    }

    return holdings;
  } catch (error) {
    console.error('Error parsing 13F XML:', error.message);
    return [];
  }
}

/**
 * Clean and normalize company name
 * @param {string} name - Raw company name
 * @returns {string} Cleaned company name
 */
function cleanCompanyName(name) {
  if (!name) return '';

  return name
    .replace(/\s+/g, ' ')
    .replace(/\s+(INC|CORP|LTD|LLC|LP|CO|COMPANY)\.?$/i, '')
    .trim();
}

module.exports = {
  parse13FXML,
  cleanCompanyName
};

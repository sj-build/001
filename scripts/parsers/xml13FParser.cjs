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

    // Try to find information table - check multiple possible paths
    let infoTable = null;

    // Common structures:
    // 1. <edgarSubmission><formData><informationTable>
    if (result.edgarSubmission && result.edgarSubmission.formData) {
      infoTable = result.edgarSubmission.formData.informationTable ||
                  result.edgarSubmission.informationTable;
    }
    // 2. <informationTable> (direct)
    else if (result.informationTable) {
      infoTable = result.informationTable;
    }
    // 3. <XML><informationTable>
    else if (result.XML) {
      infoTable = result.XML.informationTable;
    }
    // 4. <ns1:informationTable> or similar namespace
    else if (result['ns1:informationTable']) {
      infoTable = result['ns1:informationTable'];
    }
    // 5. Try to find any key containing 'informationTable'
    else {
      const keys = Object.keys(result);
      for (const key of keys) {
        if (key.toLowerCase().includes('informationtable')) {
          infoTable = result[key];
          break;
        }
      }
    }

    if (!infoTable) {
      console.warn('Could not find information table in XML');
      console.warn('Available root keys:', Object.keys(result).join(', '));
      return [];
    }

    // infoTable can be an object with infoTable array, or direct array
    // Also check for namespace prefixes like ns1:infoTable
    let infoTableEntries = infoTable.infoTable || infoTable['ns1:infoTable'] || infoTable;

    // If still not an array, check all keys for namespace variations
    if (!Array.isArray(infoTableEntries)) {
      const keys = Object.keys(infoTable);
      for (const key of keys) {
        if (key.includes(':infoTable') || key.toLowerCase().includes('infotable')) {
          infoTableEntries = infoTable[key];
          break;
        }
      }
    }

    // Ensure it's an array
    if (!Array.isArray(infoTableEntries)) {
      infoTableEntries = [infoTableEntries];
    }


    // Parse each entry
    for (const entry of infoTableEntries) {
      try {
        // Helper function to get field value with or without namespace prefix
        const getField = (obj, fieldName) => {
          // Try without namespace
          if (obj[fieldName] !== undefined) return obj[fieldName];
          // Try common namespace prefixes
          const prefixes = ['ns1:', 'ns2:', 'n1:'];
          for (const prefix of prefixes) {
            if (obj[prefix + fieldName] !== undefined) return obj[prefix + fieldName];
          }
          // Try to find any key ending with the field name
          const keys = Object.keys(obj);
          for (const key of keys) {
            if (key.endsWith(':' + fieldName)) return obj[key];
          }
          return undefined;
        };

        // Keep CUSIP as string to preserve leading zeros
        const cusip = String(getField(entry, 'cusip') || '').padStart(9, '0');

        const holding = {
          cusip: cusip,
          companyName: getField(entry, 'nameOfIssuer') || '',
          titleOfClass: getField(entry, 'titleOfClass') || 'COM',
          value: parseFloat(getField(entry, 'value') || 0), // Already in dollars (not thousands)
          shares: 0
        };

        // Extract shares
        const shrsOrPrnAmt = getField(entry, 'shrsOrPrnAmt');
        if (shrsOrPrnAmt) {
          holding.shares = parseFloat(getField(shrsOrPrnAmt, 'sshPrnamt') || getField(shrsOrPrnAmt, 'shrsOrPrnAmt') || 0);
          holding.shareType = getField(shrsOrPrnAmt, 'sshPrnamtType') || 'SH';
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

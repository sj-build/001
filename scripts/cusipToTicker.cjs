/**
 * CUSIP to Ticker mapping
 * Synchronized with fetchStockData.py
 */
const CUSIP_TO_TICKER = {
  '037833100': 'AAPL',  // Apple Inc.
  '02079K107': 'GOOGL', // Alphabet Inc. Class A
  '02079K305': 'GOOG',  // Alphabet Inc. Class C
  '594918104': 'MSFT',  // Microsoft Corp.
  '17275R102': 'CSCO',  // Cisco Systems Inc.
  '30303M102': 'META',  // Meta Platforms Inc.
  '88160R101': 'TSLA',  // Tesla Inc.
  '01609W102': 'BABA',  // Alibaba Group
  '91324P102': 'UNH',   // UnitedHealth Group
  '67066G104': 'NVDA',  // NVIDIA Corp.
  '46625H100': 'JPM',   // JPMorgan Chase & Co.
  '025816109': 'AXP',   // American Express Co.
  '023135106': 'AMZN',  // Amazon.com Inc.
  '060505104': 'BAC',   // Bank of America Corp.
  '191216100': 'KO',    // Coca-Cola Co.
  '166764100': 'CVX',   // Chevron Corp.
  '11135F101': 'AVGO',  // Broadcom Inc.
  '084670702': 'BRK.B', // Berkshire Hathaway Inc. Class B
  '68389X105': 'ORCL',  // Oracle Corp.
  '093712107': 'BE',    // Bloom Energy Corp.
  '722304102': 'PDD',   // PDD Holdings Inc.
  '02376R102': 'AMGN',  // Amgen Inc.
  '084664107': 'BK',    // Bank of New York Mellon Corp.
  '464287200': 'IEP',   // Icahn Enterprises L.P.
  '464287812': 'IEP',   // Icahn Enterprises L.P.
  '902494103': 'UBER',  // Uber Technologies Inc.
  '45780R107': 'IWM',   // iShares Russell 2000 ETF
  '464287838': 'IVV',   // iShares Core S&P 500 ETF
  '464287655': 'IWF',   // iShares Russell 1000 Growth ETF
  '78462F103': 'SPY',   // SPDR S&P 500 ETF Trust
};

function cusipToTicker(cusip) {
  return CUSIP_TO_TICKER[cusip] || '';
}

module.exports = {
  cusipToTicker,
  CUSIP_TO_TICKER
};

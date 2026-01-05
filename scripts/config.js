// Top 10 Hedge Funds by AUM with their SEC CIK numbers
module.exports = {
  hedgeFunds: [
    {
      name: 'Bridgewater Associates, LP',
      cik: '0001350694',
      description: 'World\'s largest hedge fund'
    },
    {
      name: 'Citadel Advisors LLC',
      cik: '0001423053',
      description: 'Ken Griffin\'s multi-strategy fund'
    },
    {
      name: 'Millennium Management LLC',
      cik: '0001273087',
      description: 'Multi-strategy hedge fund'
    },
    {
      name: 'Two Sigma Investments, LP',
      cik: '0001179392',
      description: 'Quantitative investment firm'
    },
    {
      name: 'Renaissance Technologies LLC',
      cik: '0001037389',
      description: 'Pioneering quantitative hedge fund'
    },
    {
      name: 'D.E. Shaw & Co., Inc.',
      cik: '0001009207',
      description: 'Quantitative and systematic trading'
    },
    {
      name: 'AQR Capital Management LLC',
      cik: '0001167557',
      description: 'Factor-based investment strategies'
    },
    {
      name: 'Elliott Management Corp',
      cik: '0001067983',
      description: 'Activist hedge fund'
    },
    {
      name: 'Point72 Asset Management',
      cik: '0001603466',
      description: 'Steve Cohen\'s family office'
    },
    {
      name: 'Farallon Capital Management',
      cik: '0001080891',
      description: 'Multi-strategy institutional investor'
    }
  ],

  // Available quarters (to be updated)
  quarters: [
    { quarter: '2025-Q4', quarterEnd: '2025-12-31', filingDeadline: '2026-02-17' },
    { quarter: '2025-Q3', quarterEnd: '2025-09-30', filingDeadline: '2025-11-14' },
    { quarter: '2025-Q2', quarterEnd: '2025-06-30', filingDeadline: '2025-08-14' },
    { quarter: '2025-Q1', quarterEnd: '2025-03-31', filingDeadline: '2025-05-15' }
  ],

  // SEC EDGAR API settings
  sec: {
    baseUrl: 'https://data.sec.gov',
    userAgent: 'HedgeFundTracker/1.0 (educational-project@example.com)',
    rateLimit: 150 // milliseconds between requests
  }
};

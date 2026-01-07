// Investor Categories Configuration
module.exports = {
  investorCategories: {
    guru: {
      label: 'Top-tier Guru Investors',
      description: 'Legendary investors and institutional giants',
      investors: [
        {
          name: 'Berkshire Hathaway Inc.',
          cik: '0001067983',
          leader: 'Warren Buffett',
          category: 'guru',
          metadata: {
            knownFor: 'Value investing',
            since: 1965,
            type: 'conglomerate'
          }
        },
        {
          name: 'Pershing Square Capital Management',
          cik: '0001336528',
          leader: 'Bill Ackman',
          category: 'guru',
          metadata: {
            knownFor: 'Activist investing',
            since: 2003,
            type: 'hedge fund'
          }
        },
        {
          name: 'Icahn Enterprises L.P.',
          cik: '0000914208',
          leader: 'Carl Icahn',
          category: 'guru',
          metadata: {
            knownFor: 'Corporate raider',
            since: 1968,
            type: 'holding company'
          }
        },
        {
          name: 'Appaloosa Management L.P.',
          cik: '0001022748',
          leader: 'David Tepper',
          category: 'guru',
          metadata: {
            knownFor: 'Distressed debt specialist',
            since: 1993,
            type: 'hedge fund'
          }
        },
        {
          name: 'Bridgewater Associates, LP',
          cik: '0001350694',
          leader: 'Ray Dalio',
          category: 'guru',
          metadata: {
            knownFor: 'Macro hedge fund pioneer',
            since: 1975,
            type: 'hedge fund'
          }
        },
        {
          name: 'Soros Fund Management LLC',
          cik: '0001029160',
          leader: 'George Soros',
          category: 'guru',
          metadata: {
            knownFor: 'Legendary macro trader',
            since: 1970,
            type: 'hedge fund'
          }
        },
        {
          name: 'Duquesne Family Office LLC',
          cik: '0001091431',
          leader: 'Stanley Druckenmiller',
          category: 'guru',
          metadata: {
            knownFor: 'Macro investing genius',
            since: 1981,
            type: 'family office'
          }
        },
        {
          name: 'Baupost Group LLC',
          cik: '0001061768',
          leader: 'Seth Klarman',
          category: 'guru',
          metadata: {
            knownFor: 'Value investing',
            since: 1982,
            type: 'hedge fund'
          }
        },
        {
          name: 'Third Point LLC',
          cik: '0001040273',
          leader: 'Dan Loeb',
          category: 'guru',
          metadata: {
            knownFor: 'Activist investor',
            since: 1995,
            type: 'hedge fund'
          }
        },
        {
          name: 'Greenlight Capital Inc.',
          cik: '0001079114',
          leader: 'David Einhorn',
          category: 'guru',
          metadata: {
            knownFor: 'Value investor & short seller',
            since: 1996,
            type: 'hedge fund'
          }
        }
      ]
    },
    emerging: {
      label: 'Tech-Focused Emerging Funds',
      description: 'High-growth technology and AI-focused hedge funds',
      investors: [
        {
          name: 'Situational Awareness LP',
          cik: '0002045724',
          leader: 'Leopold Aschenbrenner',
          category: 'emerging',
          metadata: {
            knownFor: 'AI/AGI focused, 47% H1 2025 return',
            estimatedAUM: 4100000000,
            type: 'hedge fund',
            since: 2024,
            performance2025: '47%'
          }
        },
        {
          name: 'Aspex Management (HK) Ltd',
          cik: '0001768375',
          category: 'emerging',
          metadata: {
            knownFor: 'Pan-Asian tech focus, 40.2% tech portfolio',
            estimatedAUM: 4700000000,
            type: 'hedge fund',
            since: 2018
          }
        },
        {
          name: 'Altimeter Capital Management',
          cik: '0001541617',
          leader: 'Brad Gerstner',
          category: 'emerging',
          metadata: {
            knownFor: 'Tech growth, software, semiconductors',
            estimatedAUM: 12700000000,
            type: 'hedge fund',
            since: 2008,
            performance: '29.5% annualized since 2011'
          }
        },
        {
          name: 'Durable Capital Partners LP',
          cik: '0001798849',
          leader: 'Henry Ellenbogen',
          category: 'emerging',
          metadata: {
            knownFor: 'Quality tech growth, compounders',
            estimatedAUM: 18200000000,
            type: 'hedge fund',
            since: 2019
          }
        },
        {
          name: 'D1 Capital Partners L.P.',
          cik: '0001747057',
          leader: 'Daniel Sundheim',
          category: 'emerging',
          metadata: {
            knownFor: 'Tech-focused long/short equity',
            estimatedAUM: 27750000000,
            type: 'hedge fund',
            since: 2018
          }
        }
      ]
    }
  },

  // Available quarters (to be updated)
  quarters: [
    { quarter: '2025-Q3', quarterEnd: '2025-09-30', filingDeadline: '2025-11-14' },
    { quarter: '2025-Q2', quarterEnd: '2025-06-30', filingDeadline: '2025-08-14' },
    { quarter: '2024-Q3', quarterEnd: '2024-09-30', filingDeadline: '2024-11-14' },
    { quarter: '2024-Q2', quarterEnd: '2024-06-30', filingDeadline: '2024-08-14' }
  ],

  // SEC EDGAR API settings
  sec: {
    baseUrl: 'https://data.sec.gov',
    userAgent: 'HedgeFundTracker/1.0 (educational-project@example.com)',
    rateLimit: 150 // milliseconds between requests
  },

  // Backward compatibility - default to guru investors
  get hedgeFunds() {
    return this.investorCategories.guru.investors;
  }
};

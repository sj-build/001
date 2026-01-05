import { useState, useEffect } from 'react';
import QuarterSelector from './components/QuarterSelector';
import TopStocksTable from './components/TopStocksTable';
import FundTopHoldings from './components/FundTopHoldings';
import { loadQuarterData, getAvailableQuarters } from './utils/dataLoader';
import type { QuarterData } from './types';

function App() {
  const availableQuarters = getAvailableQuarters();
  const [selectedQuarter, setSelectedQuarter] = useState(availableQuarters[0]);
  const [data, setData] = useState<QuarterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    loadQuarterData(selectedQuarter)
      .then((quarterData) => {
        setData(quarterData);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
        console.error('Failed to load quarter data:', err);
      });
  }, [selectedQuarter]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">
            Hedge Fund Investment Tracker
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Tracking top 10 hedge funds' quarterly holdings and investment patterns
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Quarter Selector */}
        <div className="mb-8">
          <QuarterSelector
            quarters={availableQuarters}
            selected={selectedQuarter}
            onChange={setSelectedQuarter}
          />
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading data for {selectedQuarter}...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-8">
            <h3 className="text-red-800 font-semibold mb-2">Error Loading Data</h3>
            <p className="text-red-600 text-sm">{error}</p>
            <p className="text-red-600 text-sm mt-2">
              Please make sure you have generated data for {selectedQuarter} by running:
              <code className="block mt-1 bg-red-100 p-2 rounded">
                node scripts/buildQuarterData.js --quarter {selectedQuarter}
              </code>
            </p>
          </div>
        )}

        {/* Data Display */}
        {!loading && !error && data && (
          <div className="space-y-12">
            {/* Section 1: Aggregated Top 10 Stocks */}
            <section>
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Top 10 Most Invested Stocks
                </h2>
                <p className="text-gray-600">
                  Aggregated holdings across {data.summary.metadata.totalFundsAnalyzed} hedge funds
                  with ${(data.summary.metadata.totalAUMAggregated / 1e9).toFixed(2)}B total AUM
                </p>
              </div>

              <div className="bg-white rounded-lg shadow-md overflow-hidden">
                <TopStocksTable stocks={data.summary.topStocks} />
              </div>
            </section>

            {/* Section 2: Individual Fund Top Holdings */}
            <section>
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Top Holdings by Fund
                </h2>
                <p className="text-gray-600">
                  Each hedge fund's largest position with detailed analysis
                </p>
              </div>

              <FundTopHoldings data={data.detailed.fundTopHoldings} />
            </section>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            Data sourced from SEC EDGAR 13F filings and Yahoo Finance |
            Educational project for tracking institutional investment trends
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;

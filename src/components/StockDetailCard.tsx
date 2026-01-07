import type { DetailedHolding } from '../types';
import StockChart from './StockChart';
import ValuationMetrics from './ValuationMetrics';
import { formatCurrency, formatShares, formatPercent } from '../utils/formatters';

interface StockDetailCardProps {
  holding: DetailedHolding;
}

export default function StockDetailCard({ holding }: StockDetailCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-6 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl font-bold text-blue-600 font-mono">
            {holding.ticker || 'N/A'}
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-lg text-gray-700">{holding.companyName}</span>
        </div>

        {/* Quarterly Change Summary */}
        {holding.positionChange && (
          <div className="mt-4 p-4 bg-green-50 border-l-4 border-green-500 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-green-800">Position Increased</span>
              <span className="text-2xl font-bold text-green-700">
                {holding.positionChange.change.percentChange === null
                  ? 'NEW'
                  : `+${formatPercent(holding.positionChange.change.percentChange)}`}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-gray-600">Value Added</div>
                <div className="font-semibold text-green-700">
                  +{formatCurrency(holding.positionChange.change.valueChange)}
                </div>
              </div>
              <div>
                <div className="text-gray-600">Shares Added</div>
                <div className="font-semibold text-green-700">
                  +{formatShares(holding.positionChange.change.sharesChange)}
                </div>
              </div>
              <div>
                <div className="text-gray-600">Previous Value</div>
                <div className="font-semibold text-gray-700">
                  {formatCurrency(holding.positionChange.previousQuarter?.value || 0)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Current Portfolio Info */}
        <div className="grid grid-cols-3 gap-4 mt-4 p-4 bg-blue-50 rounded-lg">
          <div>
            <div className="text-xs text-gray-600 mb-1">Current Position Value</div>
            <div className="text-lg font-semibold text-gray-900">
              {formatCurrency(holding.value)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-600 mb-1">Current Shares</div>
            <div className="text-lg font-semibold text-gray-900">
              {formatShares(holding.shares)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-600 mb-1">Portfolio %</div>
            <div className="text-lg font-semibold text-blue-600">
              {formatPercent(holding.percentOfPortfolio)}
            </div>
          </div>
        </div>
      </div>

      {/* Price Chart */}
      <div>
        <StockChart data={holding.priceHistory} ticker={holding.ticker} />
      </div>

      {/* Valuation Metrics */}
      <div>
        <ValuationMetrics metrics={holding.valuationMetrics} />
      </div>
    </div>
  );
}

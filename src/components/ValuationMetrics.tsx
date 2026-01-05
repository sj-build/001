import type { ValuationMetrics as ValuationMetricsType } from '../types';
import { formatMultiple, formatCurrency } from '../utils/formatters';

interface ValuationMetricsProps {
  metrics: ValuationMetricsType;
}

interface MetricCardProps {
  label: string;
  value: string;
  description: string;
}

function MetricCard({ label, value, description }: MetricCardProps) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-gray-900 mb-1">{value}</div>
      <div className="text-xs text-gray-400">{description}</div>
    </div>
  );
}

export default function ValuationMetrics({ metrics }: ValuationMetricsProps) {
  return (
    <div>
      <h4 className="text-sm font-medium text-gray-600 mb-3">Valuation Multiples</h4>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="P/E Ratio"
          value={formatMultiple(metrics.peRatio)}
          description="Price to Earnings"
        />
        <MetricCard
          label="P/B Ratio"
          value={formatMultiple(metrics.pbRatio)}
          description="Price to Book"
        />
        <MetricCard
          label="P/S Ratio"
          value={formatMultiple(metrics.psRatio)}
          description="Price to Sales"
        />
        <MetricCard
          label="EV/EBITDA"
          value={formatMultiple(metrics.evToEbitda)}
          description="Enterprise Value to EBITDA"
        />
      </div>
      <div className="mt-4 text-xs text-gray-500">
        Market Cap: {formatCurrency(metrics.marketCap)} | Last Updated: {new Date(metrics.lastUpdated).toLocaleDateString()}
      </div>
    </div>
  );
}

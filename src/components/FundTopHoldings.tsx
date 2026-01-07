import type { FundTopHolding } from '../types';
import StockDetailCard from './StockDetailCard';

interface FundTopHoldingsProps {
  data: FundTopHolding[];
}

export default function FundTopHoldings({ data }: FundTopHoldingsProps) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No fund holdings data available
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {data.map((fundHolding, index) => (
        <div key={fundHolding.fundCik} className="space-y-4">
          {/* Fund Header */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
              {index + 1}
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900">
                {fundHolding.fundName}
              </h3>
              <p className="text-sm text-gray-500">
                Most Purchased vs Previous Quarter
              </p>
            </div>
          </div>

          {/* Stock Detail Card */}
          <StockDetailCard holding={fundHolding.mostPurchased} />
        </div>
      ))}
    </div>
  );
}

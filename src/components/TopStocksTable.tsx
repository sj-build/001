import type { TopStock } from '../types';
import { formatCurrency, formatShares } from '../utils/formatters';

interface TopStocksTableProps {
  stocks: TopStock[];
}

export default function TopStocksTable({ stocks }: TopStocksTableProps) {
  if (!stocks || stocks.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No data available
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-100">
            <th className="px-4 py-3 text-left text-sm font-semibold">Rank</th>
            <th className="px-4 py-3 text-left text-sm font-semibold">Ticker</th>
            <th className="px-4 py-3 text-left text-sm font-semibold">Company</th>
            <th className="px-4 py-3 text-right text-sm font-semibold">Total Value</th>
            <th className="px-4 py-3 text-right text-sm font-semibold">Shares</th>
            <th className="px-4 py-3 text-center text-sm font-semibold"># of Funds</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map((stock) => (
            <tr
              key={stock.cusip}
              className="border-b border-gray-200 hover:bg-gray-50 transition-colors"
            >
              <td className="px-4 py-3 text-sm font-medium">{stock.rank}</td>
              <td className="px-4 py-3 text-sm font-mono font-semibold text-blue-600">
                {stock.ticker || 'N/A'}
              </td>
              <td className="px-4 py-3 text-sm">{stock.companyName}</td>
              <td className="px-4 py-3 text-sm text-right font-medium">
                {formatCurrency(stock.totalValue)}
              </td>
              <td className="px-4 py-3 text-sm text-right">
                {formatShares(stock.totalShares)}
              </td>
              <td className="px-4 py-3 text-sm text-center">
                <span className="inline-block bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                  {stock.numberOfFundsHolding}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

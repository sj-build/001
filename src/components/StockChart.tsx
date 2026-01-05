import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import type { PricePoint } from '../types';

interface StockChartProps {
  data: PricePoint[];
  ticker: string;
}

export default function StockChart({ data, ticker }: StockChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 bg-gray-50 rounded">
        No price data available
      </div>
    );
  }

  // Format date for display (show only month/day for cleaner axis)
  const formattedData = data.map(point => ({
    ...point,
    displayDate: new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }));

  // Sample data points for cleaner X-axis (show every Nth point)
  const tickInterval = Math.ceil(formattedData.length / 6);

  return (
    <div className="w-full">
      <div className="mb-2">
        <h4 className="text-sm font-medium text-gray-600">1 Year Price Chart - {ticker}</h4>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={formattedData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="displayDate"
            tick={{ fontSize: 12 }}
            interval={tickInterval}
            stroke="#9ca3af"
          />
          <YAxis
            tick={{ fontSize: 12 }}
            stroke="#9ca3af"
            domain={['dataMin - 5', 'dataMax + 5']}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '8px'
            }}
            formatter={(value: number | undefined) => value !== undefined ? [`$${value.toFixed(2)}`, 'Close'] : ['N/A', 'Close']}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface QuarterSelectorProps {
  quarters: string[];
  selected: string;
  onChange: (quarter: string) => void;
}

export default function QuarterSelector({ quarters, selected, onChange }: QuarterSelectorProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {quarters.map((quarter) => (
        <button
          key={quarter}
          onClick={() => onChange(quarter)}
          className={`px-6 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
            selected === quarter
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          {quarter}
        </button>
      ))}
    </div>
  );
}

import type { InvestorCategory } from '../types';
import { getAvailableCategories } from '../utils/dataLoader';

interface CategoryTabsProps {
  activeCategory: InvestorCategory;
  onCategoryChange: (category: InvestorCategory) => void;
}

export default function CategoryTabs({ activeCategory, onCategoryChange }: CategoryTabsProps) {
  const categories = getAvailableCategories();

  return (
    <div className="mb-8">
      <div className="flex gap-4 border-b border-gray-200">
        {categories.map((category) => {
          const isActive = activeCategory === category.value;
          const colorClasses = {
            guru: {
              active: 'border-blue-500 text-blue-600',
              hover: 'hover:border-blue-300 hover:text-blue-500'
            },
            emerging: {
              active: 'border-green-500 text-green-600',
              hover: 'hover:border-green-300 hover:text-green-500'
            }
          }[category.value];

          return (
            <button
              key={category.value}
              onClick={() => onCategoryChange(category.value)}
              className={`
                pb-4 px-4 border-b-2 font-medium transition-colors
                ${isActive
                  ? `${colorClasses.active} border-b-2`
                  : `border-transparent text-gray-500 ${colorClasses.hover}`
                }
              `}
            >
              <div className="flex flex-col items-start">
                <span className="text-lg">{category.label}</span>
                <span className="text-xs font-normal text-gray-400 mt-1">
                  {category.description}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Active category indicator */}
      <div className="mt-4">
        {categories.map((category) => {
          if (activeCategory !== category.value) return null;

          const badgeColor = category.value === 'guru' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800';

          return (
            <div key={category.value} className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${badgeColor}`}>
                {category.value === 'guru' ? '🏆 Legendary' : '🚀 Rising Star'}
              </span>
              <span className="text-gray-600 text-sm">
                {category.description}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

import { formatPrice, calcPercent } from '../../utils/formatPrice';
import { MonitorSmartphone } from 'lucide-react';

export default function SetCard({ set, index, onClick }) {
  const products = set.products || [];
  const activeProducts = products.filter(p => p.is_active);
  const totalCost = activeProducts.reduce((sum, p) => sum + (p.current_price || p.locked_price || 0), 0);
  const budgetPercent = calcPercent(totalCost, set.target_budget);

  const staggerDelay = `${index * 60}ms`;

  return (
    <button
      className="sp-set-card animate-fade-in-up"
      style={{ animationDelay: staggerDelay }}
      onClick={onClick}
    >
      <div className="sp-set-card__header">
        <div className="sp-set-card__icon">
          <MonitorSmartphone size={18} />
        </div>
        <div className="sp-set-card__meta">
          <h3 className="sp-set-card__name truncate">{set.name}</h3>
          <span className="sp-set-card__count">{products.length} parça</span>
        </div>
      </div>

      <div className="sp-set-card__price font-mono">
        {formatPrice(totalCost)}
      </div>

      {set.target_budget > 0 && (
        <div className="sp-set-card__budget">
          <div className="sp-set-card__budget-bar">
            <div
              className="sp-set-card__budget-fill"
              style={{
                width: `${Math.min(budgetPercent, 100)}%`,
                background: budgetPercent > 100
                  ? 'var(--color-danger)'
                  : budgetPercent > 80
                  ? 'var(--color-warning)'
                  : 'var(--gradient-primary)',
              }}
            />
          </div>
          <span className="sp-set-card__budget-text">
            {budgetPercent > 0 ? `%${budgetPercent.toFixed(0)}` : '—'} / {formatPrice(set.target_budget, false)} ₺
          </span>
        </div>
      )}
    </button>
  );
}

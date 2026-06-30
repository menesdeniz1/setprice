import './BudgetBar.css';
import { formatPrice } from '../../utils/formatPrice';

export default function BudgetBar({ current, target, percent }) {
  const isOver = percent > 100;
  const isWarning = percent > 80 && percent <= 100;

  return (
    <div className={`sp-budget ${isOver ? 'sp-budget--over' : ''}`}>
      <div className="sp-budget__header">
        <span className="sp-budget__label">Hedef Bütçe</span>
        <span className="sp-budget__values font-mono">
          <span className={isOver ? 'sp-budget__current--over' : ''}>
            {formatPrice(current, false)}
          </span>
          <span className="sp-budget__separator"> / </span>
          <span className="sp-budget__target">{formatPrice(target, false)} ₺</span>
        </span>
      </div>
      <div className="sp-budget__track">
        <div
          className={`sp-budget__fill ${isOver ? 'sp-budget__fill--over' : isWarning ? 'sp-budget__fill--warning' : ''}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <div className="sp-budget__footer">
        <span className="sp-budget__percent" style={{
          color: isOver ? 'var(--color-danger)' : isWarning ? 'var(--color-warning)' : 'var(--color-text-muted)'
        }}>
          %{percent.toFixed(1)}
          {isOver && ' — Bütçe aşıldı!'}
        </span>
        {!isOver && (
          <span className="sp-budget__remaining" style={{ color: 'var(--color-success)' }}>
            {formatPrice(target - current)} kaldı
          </span>
        )}
      </div>
    </div>
  );
}

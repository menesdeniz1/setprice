import './ProductCard.css';
import { useState } from 'react';
import { Lock, Unlock, Trash2, ExternalLink } from 'lucide-react';
import { formatPrice } from '../../utils/formatPrice';
import { STATUS_CONFIG } from '../../utils/constants';
import SignalBadge from '../products/SignalBadge';

export default function ProductCard({ product, onToggleActive, onToggleLock, onUpdateLockedPrice, onDelete, onClick }) {
  const price = product.current_price || product.locked_price;
  const statusCfg = STATUS_CONFIG[product.status] || STATUS_CONFIG.BEKLEMEDE;
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editPrice, setEditPrice] = useState('');

  // Handle local state when locked price changes
  useState(() => {
    if (product.is_locked && product.locked_price) {
      setEditPrice(product.locked_price.toString());
    }
  }, [product.locked_price, product.is_locked]);

  const handlePriceBlur = () => {
    const val = parseFloat(editPrice);
    if (!isNaN(val) && val >= 0) {
      onUpdateLockedPrice(val);
    }
  };

  const handlePriceKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur();
    }
  };

  return (
    <div className={`sp-prodcard ${!product.is_active ? 'sp-prodcard--inactive' : ''}`}>
      {/* Active checkbox */}
      <label className="sp-prodcard__check">
        <input
          type="checkbox"
          checked={product.is_active}
          onChange={(e) => {
            e.stopPropagation();
            onToggleActive();
          }}
        />
        <span className="sp-prodcard__checkmark" />
      </label>

      {/* Info area — clickable */}
      <div className="sp-prodcard__info" onClick={onClick}>
        <div className="sp-prodcard__name-row">
          <span className="sp-prodcard__name truncate">{product.name}</span>
          <a
            href={product.original_link}
            target="_blank"
            rel="noopener noreferrer"
            className="sp-prodcard__link"
            onClick={e => e.stopPropagation()}
            title="Mağazaya git"
          >
            <ExternalLink size={12} />
          </a>
        </div>
        <div className="sp-prodcard__meta" style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '6px' }}>
          <span className="sp-prodcard__seller">{product.current_seller || 'Bilinmiyor'}</span>
          <span
            className="sp-prodcard__status"
            style={{ color: statusCfg.color, background: statusCfg.bg }}
          >
            {statusCfg.label}
          </span>
          {product.decision_signal && (
            <SignalBadge signal={product.decision_signal} valueScore={product.value_score} />
          )}
          {product.performance_score != null && (
            <span
              title={product.benchmark_match_name ? `Referans: ${product.benchmark_match_name} (PassMark tahmini)` : undefined}
              style={{
                fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: 'var(--radius-full)',
                background: 'var(--color-secondary-muted)', color: 'var(--color-secondary)', cursor: 'help',
              }}
            >
              Performans: {Math.round(product.performance_score)}/100
            </span>
          )}
        </div>
        {product.decision_reasoning && (
          <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '6px', fontStyle: 'italic', lineHeight: '1.3' }}>
            {product.decision_reasoning}
          </div>
        )}
      </div>

      {/* Price */}
      <div className="sp-prodcard__price-area">
        {product.is_locked ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <input
              type="number"
              value={editPrice}
              onChange={e => setEditPrice(e.target.value)}
              onBlur={handlePriceBlur}
              onKeyDown={handlePriceKeyDown}
              onClick={e => e.stopPropagation()}
              className="font-mono"
              style={{
                width: '80px',
                padding: '2px 4px',
                borderRadius: '4px',
                border: '1px solid var(--color-primary)',
                background: 'var(--color-bg-elevated)',
                color: 'var(--color-text-primary)',
                textAlign: 'right'
              }}
              step="any"
              min="0"
            />
            <span className="font-mono" style={{ fontSize: '13px' }}>₺</span>
          </div>
        ) : (
          <span className="sp-prodcard__price font-mono">
            {price ? formatPrice(price) : 'Taranmadı'}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="sp-prodcard__actions">
        <button
          className={`sp-prodcard__action ${product.is_locked ? 'sp-prodcard__action--locked' : ''}`}
          onClick={(e) => { e.stopPropagation(); onToggleLock(); }}
          title={product.is_locked ? 'Kilidi Aç' : 'Fiyatı Kilitle'}
        >
          {product.is_locked ? <Lock size={14} /> : <Unlock size={14} />}
        </button>
        <button
          className={`sp-prodcard__action sp-prodcard__action--delete ${confirmDelete ? 'sp-prodcard__action--confirm' : ''}`}
          onClick={(e) => { 
            e.stopPropagation(); 
            if (confirmDelete) {
              onDelete();
            } else {
              setConfirmDelete(true);
              setTimeout(() => setConfirmDelete(false), 3000);
            }
          }}
          title={confirmDelete ? 'Silmeyi Onayla' : 'Setten Kaldır'}
          style={confirmDelete ? { color: 'white', backgroundColor: 'var(--color-danger)' } : {}}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

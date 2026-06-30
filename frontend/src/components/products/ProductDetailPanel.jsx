import './ProductDetailPanel.css';
import { useState, useEffect } from 'react';
import { X, ExternalLink, TrendingDown, BarChart3, ArrowRightLeft } from 'lucide-react';
import { getProductHistory, getProductAlternatives } from '../../api/client';
import { formatPrice, formatDate, formatRelativeTime } from '../../utils/formatPrice';
import { STATUS_CONFIG } from '../../utils/constants';
import { useToast } from '../../context/ToastContext';
import React, { Suspense } from 'react';

const PriceChart = React.lazy(() => import('./PriceChart'));

export default function ProductDetailPanel({ product, onClose }) {
  const [tab, setTab] = useState('history');
  const [history, setHistory] = useState([]);
  const [alternatives, setAlternatives] = useState([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const loadData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [hist, alts] = await Promise.all([
        getProductHistory(product.id),
        getProductAlternatives(product.id),
      ]);
      setHistory(hist);
      setAlternatives(alts);
    } catch (err) {
      console.error(err);
      toast.error('Detay verileri yüklenirken bir hata oluştu.');
    } finally {
      setLoading(false);
    }
  }, [product.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const price = product.current_price || product.locked_price || 0;
  const statusCfg = STATUS_CONFIG[product.status] || STATUS_CONFIG.BEKLEMEDE;

  // Find cheapest alternative
  const cheapestAlt = alternatives.length > 0
    ? alternatives.reduce((min, a) => a.price < min.price ? a : min, alternatives[0])
    : null;
  const savings = cheapestAlt && cheapestAlt.price < price ? price - cheapestAlt.price : 0;

  return (
    <>
      <div className="sp-panel-overlay animate-fade-in" onClick={onClose} />
      <div className="sp-panel animate-slide-right">
        {/* Header */}
        <div className="sp-panel__header">
          <div className="sp-panel__header-info">
            <h2 className="sp-panel__title truncate">{product.name}</h2>
            <div className="sp-panel__meta">
              <span className="sp-panel__seller">{product.current_seller || 'Bilinmiyor'}</span>
              <span className="sp-panel__status" style={{ color: statusCfg.color, background: statusCfg.bg }}>
                {statusCfg.label}
              </span>
            </div>
          </div>
          <button className="sp-panel__close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Price display */}
        <div className="sp-panel__price-block">
          <div className="sp-panel__current-price">
            <span className="sp-panel__price-label">Güncel Fiyat</span>
            <span className="sp-panel__price-value font-mono">{formatPrice(price)}</span>
          </div>
          {savings > 0 && (
            <div className="sp-panel__savings">
              <TrendingDown size={14} />
              <span>{formatPrice(savings)} daha ucuz alternatif var!</span>
            </div>
          )}
          <a
            href={product.original_link}
            target="_blank"
            rel="noopener noreferrer"
            className="sp-panel__source-link"
          >
            <ExternalLink size={13} />
            Mağazaya Git
          </a>
        </div>

        {/* Tabs */}
        <div className="sp-panel__tabs">
          <button
            className={`sp-panel__tab ${tab === 'history' ? 'sp-panel__tab--active' : ''}`}
            onClick={() => setTab('history')}
          >
            <BarChart3 size={14} />
            Fiyat Geçmişi
          </button>
          <button
            className={`sp-panel__tab ${tab === 'alternatives' ? 'sp-panel__tab--active' : ''}`}
            onClick={() => setTab('alternatives')}
          >
            <ArrowRightLeft size={14} />
            Muadiller ({alternatives.length})
          </button>
        </div>

        {/* Tab Content */}
        <div className="sp-panel__content">
          {loading ? (
            <div style={{ padding: 'var(--space-6)' }}>
              <div className="skeleton" style={{ width: '100%', height: '200px' }} />
            </div>
          ) : tab === 'history' ? (
            <div className="sp-panel__history">
              {history.length === 0 ? (
                <div className="sp-panel__empty">
                  Henüz fiyat geçmişi kaydı yok. Tarama yapıldıkça burada fiyat değişimleri görünecek.
                </div>
              ) : (
                <>
                  <Suspense fallback={<div className="skeleton" style={{width: '100%', height: '220px'}} />}>
                    <PriceChart data={history} />
                  </Suspense>
                  <div className="sp-panel__history-list">
                    {history.slice().reverse().slice(0, 10).map((h, i) => (
                      <div key={h.id || i} className="sp-panel__history-item">
                        <span className="sp-panel__history-date">{formatDate(h.recorded_at)}</span>
                        <span className="sp-panel__history-seller">{h.seller || '—'}</span>
                        <span className="sp-panel__history-price font-mono">{formatPrice(h.price)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="sp-panel__alternatives">
              {alternatives.length === 0 ? (
                <div className="sp-panel__empty">
                  Bu ürün için alternatif bulunamadı. Tarama yapıldıktan sonra Akakçe üzerinden muadiller aranır.
                </div>
              ) : (
                <div className="sp-panel__alt-list">
                  {alternatives.map((alt, i) => {
                    const isCheaper = alt.price < price;
                    return (
                      <a
                        key={alt.id || i}
                        href={alt.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`sp-panel__alt-card ${isCheaper ? 'sp-panel__alt-card--cheaper' : ''}`}
                      >
                        <div className="sp-panel__alt-info">
                          <span className="sp-panel__alt-title truncate">{alt.title}</span>
                          <span className="sp-panel__alt-seller">{alt.seller || 'Bilinmiyor'}</span>
                        </div>
                        <div className="sp-panel__alt-price-area">
                          <span className={`sp-panel__alt-price font-mono ${isCheaper ? 'sp-panel__alt-price--green' : ''}`}>
                            {formatPrice(alt.price)}
                          </span>
                          {isCheaper && (
                            <span className="sp-panel__alt-saving">
                              -{formatPrice(price - alt.price, false)} ₺
                            </span>
                          )}
                        </div>
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

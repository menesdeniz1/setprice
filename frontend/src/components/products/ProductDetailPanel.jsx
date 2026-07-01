import './ProductDetailPanel.css';
import { useState, useEffect } from 'react';
import { X, ExternalLink, TrendingDown, BarChart3, ArrowRightLeft, Target } from 'lucide-react';
import { getProductHistory, getProductAlternatives, setPriceThreshold } from '../../api/client';
import { formatPrice, formatDate, formatRelativeTime } from '../../utils/formatPrice';
import { STATUS_CONFIG } from '../../utils/constants';
import { useToast } from '../../context/ToastContext';
import SegmentedToggle from '../ui/SegmentedToggle';
import ScoreRing from '../ui/ScoreRing';
import React, { Suspense } from 'react';

const PriceChart = React.lazy(() => import('./PriceChart'));

export default function ProductDetailPanel({ product, onClose }) {
  const [tab, setTab] = useState('history');
  const [history, setHistory] = useState([]);
  const [alternatives, setAlternatives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [threshold, setThreshold] = useState(product.price_alert_threshold || '');
  const [savingThreshold, setSavingThreshold] = useState(false);
  const [altMode, setAltMode] = useState('same_product'); // 'same_product' | 'similar'
  const [altSort, setAltSort] = useState('price'); // 'price' | 'smart'
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
      const hasSameProduct = alts.some(a => (a.match_type || 'similar') === 'same_product');
      setAltMode(hasSameProduct ? 'same_product' : 'similar');
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

  const sameProductAlts = alternatives.filter(a => (a.match_type || 'similar') === 'same_product');
  const similarAlts = alternatives.filter(a => (a.match_type || 'similar') === 'similar');

  // Tasarruf mesajı için önce "aynı ürün" eşleşmelerini tercih et (elma-elma kıyas),
  // hiç yoksa muadillere düş
  const savingsPool = sameProductAlts.length > 0 ? sameProductAlts : alternatives;
  const cheapestAlt = savingsPool.length > 0
    ? savingsPool.reduce((min, a) => a.price < min.price ? a : min, savingsPool[0])
    : null;
  const savings = cheapestAlt && cheapestAlt.price < price ? price - cheapestAlt.price : 0;

  const valueScore = (altPrice) => {
    if (!price) return 50;
    const ratio = altPrice / price;
    return Math.max(0, Math.min(100, 50 + (1 - ratio) * 100));
  };

  const activeAltList = altMode === 'same_product' ? sameProductAlts : similarAlts;
  const sortedAlts = [...activeAltList].sort((a, b) => {
    if (altSort === 'price') return a.price - b.price;
    // Akıllı sıralama: fiyat avantajı skoru, eşitlikte eşleşme güveni
    const scoreDiff = valueScore(b.price) - valueScore(a.price);
    if (scoreDiff !== 0) return scoreDiff;
    return (b.match_confidence || 0) - (a.match_confidence || 0);
  });

  const handleSaveThreshold = async () => {
    if (savingThreshold) return;
    setSavingThreshold(true);
    try {
      const val = threshold ? parseFloat(threshold) : null;
      await setPriceThreshold(product.library_product_id || product.id, val);
      toast.success('Fiyat alarmı kaydedildi');
    } catch (e) {
      toast.error('Alarm kaydedilemedi');
    } finally {
      setSavingThreshold(false);
    }
  };


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
        
        {/* Alert Threshold Block */}
        <div style={{ padding: '0 var(--space-6) var(--space-4)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Target size={14} color="var(--color-text-secondary)" />
          <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Hedef Fiyat:</span>
          <input 
            type="number" 
            value={threshold} 
            onChange={e => setThreshold(e.target.value)}
            onBlur={handleSaveThreshold}
            onKeyDown={e => e.key === 'Enter' && e.target.blur()}
            placeholder="₺0.00"
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              fontSize: '12px',
              width: '80px',
              background: 'var(--color-bg-elevated)',
              color: 'var(--color-text-primary)'
            }}
          />
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
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', padding: '0 var(--space-6) var(--space-4)' }}>
                    <SegmentedToggle
                      size="sm"
                      value={altMode}
                      onChange={setAltMode}
                      options={[
                        { value: 'same_product', label: `Başka Mağazada (${sameProductAlts.length})` },
                        { value: 'similar', label: `Muadil Ürünler (${similarAlts.length})` },
                      ]}
                    />
                    <SegmentedToggle
                      size="sm"
                      value={altSort}
                      onChange={setAltSort}
                      options={[
                        { value: 'price', label: 'Fiyata Göre' },
                        { value: 'smart', label: 'Akıllı Sıralama' },
                      ]}
                    />
                  </div>

                  {sortedAlts.length === 0 ? (
                    <div className="sp-panel__empty">
                      {altMode === 'same_product'
                        ? 'Bu üründen başka mağazada satan, başlığı yeterince benzer bir sonuç bulunamadı.'
                        : 'Bu ürün için spec bazlı bir muadil bulunamadı.'}
                    </div>
                  ) : (
                <div style={{ background: 'var(--color-bg-elevated)', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--color-border)' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 0.7fr 1fr auto', padding: '12px 16px', background: 'var(--color-bg-surface-hover)', borderBottom: '1px solid var(--color-border)', fontSize: '12px', fontWeight: '600', color: 'var(--color-text-secondary)' }}>
                    <div>Satıcı</div>
                    <div>Ürün</div>
                    <div>Eşleşme</div>
                    <div>Fiyat</div>
                    <div></div>
                  </div>
                  {sortedAlts.map((alt, i) => {
                    const isCheaper = alt.price < price;
                    return (
                      <div key={alt.id || i} style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 0.7fr 1fr auto', padding: '16px', alignItems: 'center', borderBottom: '1px solid var(--color-border)', background: isCheaper ? 'var(--color-success-muted)' : 'transparent', transition: 'background 0.2s' }}>
                        <div>
                          <div style={{ fontWeight: '500', color: 'var(--color-text-primary)', fontSize: '14px' }}>{alt.seller || 'Bilinmiyor'}</div>
                          {isCheaper && <div style={{ fontSize: '11px', color: 'var(--color-success)', fontWeight: '600', marginTop: '2px' }}>⭐ En Ucuz</div>}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                          <span title={alt.title} className="truncate" style={{ maxWidth: '120px', display: 'inline-block' }}>{alt.title}</span>
                        </div>
                        <div title="Başlık benzerlik oranına dayalı eşleşme güveni">
                          <ScoreRing
                            value={alt.match_confidence != null ? alt.match_confidence * 100 : null}
                            size={32}
                            strokeWidth={3}
                          />
                        </div>
                        <div style={{ fontWeight: '700', fontSize: '15px', color: isCheaper ? 'var(--color-success)' : 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>
                          {formatPrice(alt.price)}
                        </div>
                        <div>
                          <a href={alt.link} target="_blank" rel="noopener noreferrer" style={{ padding: '6px 12px', background: 'var(--color-brand-accent)', color: '#fff', borderRadius: '4px', fontSize: '12px', fontWeight: '500', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            Satıcıya Git <ExternalLink size={12} />
                          </a>
                        </div>
                      </div>
                    );
                  })}
                </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

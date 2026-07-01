import './DashboardPage.css';
import { MonitorSmartphone, TrendingDown, Package, Zap } from 'lucide-react';
import { formatPrice } from '../../utils/formatPrice';
import StatCard from '../ui/StatCard';
import SetCard from './SetCard';

export default function DashboardPage({ sets = [], onNavigateToSet, onCreateSet }) {
  // Calculate summary stats
  const totalProducts = sets.reduce((sum, s) => sum + (s.products?.length || 0), 0);
  const totalCost = sets.reduce((sum, s) => {
    const products = s.products || [];
    return sum + products.reduce((pSum, p) => pSum + (p.current_price || p.locked_price || 0), 0);
  }, 0);

  const allProducts = sets.flatMap(s => s.products || []);
  const buyProducts = allProducts.filter(p => p.decision_signal === 'BUY');
  const avoidProducts = allProducts.filter(p => p.decision_signal === 'AVOID');

  return (
    <div className="sp-dashboard animate-fade-in">
      {/* Page Header */}
      <div className="sp-dashboard__header">
        <div>
          <h1 className="sp-dashboard__title">Dashboard</h1>
          <p className="sp-dashboard__subtitle">Tüm setlerinizin genel durumu</p>
        </div>
      </div>

      {/* Portfolio Intelligence: Best Moves */}
      <div className="sp-dashboard__stats" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
        <StatCard
          icon={Zap}
          accentColor="var(--color-signal-buy)"
          value={buyProducts.length}
          label="Alım Fırsatı (BUY)"
          mono
        />

        <StatCard
          icon={TrendingDown}
          accentColor="var(--color-signal-wait)"
          mono
          value={formatPrice(allProducts.reduce((sum, p) => sum + (p.current_price && p.benchmark_price && p.current_price < p.benchmark_price ? p.benchmark_price - p.current_price : 0), 0))}
          label="Potansiyel Tasarruf"
        />

        <StatCard
          icon={MonitorSmartphone}
          accentColor="var(--color-signal-avoid)"
          value={avoidProducts.length}
          label="Şişkin Fiyat (AVOID)"
          mono
        />
      </div>

      {allProducts.length > 0 && (
        <div style={{ marginTop: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
            {/* BUY Panel */}
            <div style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-success)', borderRadius: 'var(--radius-lg)', padding: '16px', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: -20, right: -20, width: 80, height: 80, background: 'var(--color-success)', filter: 'blur(40px)', opacity: 0.15, borderRadius: '50%' }} />
              <h3 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--color-success)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-success)', boxShadow: '0 0 8px var(--color-success)' }} />
                Alınması Gerekenler ({buyProducts.length})
              </h3>
              {buyProducts.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {buyProducts.slice(0, 3).map(p => (
                    <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingBottom: '12px', borderBottom: '1px solid var(--color-border)' }}>
                      <div style={{ flex: 1, paddingRight: '12px' }}>
                        <div style={{ fontSize: '13px', fontWeight: '500', color: 'var(--color-text-primary)', marginBottom: '4px' }} className="truncate">{p.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', fontStyle: 'italic', lineHeight: '1.3' }}>{p.decision_reasoning || 'Fiyat/Performans oranı çok yüksek.'}</div>
                      </div>
                      <div style={{ fontWeight: '700', fontSize: '14px', color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>{formatPrice(p.current_price || p.locked_price || 0)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>Şu an için acil alım fırsatı görünmüyor. Beklemede kalın.</div>
              )}
            </div>

            {/* AVOID Panel */}
            <div style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-danger)', borderRadius: 'var(--radius-lg)', padding: '16px', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: -20, right: -20, width: 80, height: 80, background: 'var(--color-danger)', filter: 'blur(40px)', opacity: 0.15, borderRadius: '50%' }} />
              <h3 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--color-danger)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-danger)', boxShadow: '0 0 8px var(--color-danger)' }} />
                Uzak Durulması Gerekenler ({avoidProducts.length})
              </h3>
              {avoidProducts.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {avoidProducts.slice(0, 3).map(p => (
                    <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingBottom: '12px', borderBottom: '1px solid var(--color-border)' }}>
                      <div style={{ flex: 1, paddingRight: '12px' }}>
                        <div style={{ fontSize: '13px', fontWeight: '500', color: 'var(--color-text-primary)', marginBottom: '4px' }} className="truncate">{p.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', fontStyle: 'italic', lineHeight: '1.3' }}>{p.decision_reasoning || 'Şu an aşırı pahalı bölgede.'}</div>
                      </div>
                      <div style={{ fontWeight: '700', fontSize: '14px', color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>{formatPrice(p.current_price || p.locked_price || 0)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>Şişmiş fiyata sahip ürün tespit edilmedi.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sets Grid */}
      <div className="sp-dashboard__section-title">
        <Zap size={16} />
        <span>Setlerim</span>
      </div>

      {sets.length === 0 ? (
        <div className="sp-dashboard__empty">
          <div className="sp-dashboard__empty-icon">
            <MonitorSmartphone size={40} />
          </div>
          <h3>Henüz set oluşturmadınız</h3>
          <p>Bilgisayar parçalarınızı organize etmeye başlamak için ilk setinizi oluşturun.</p>
          <button className="sp-dashboard__empty-btn" onClick={onCreateSet}>
            <Zap size={16} />
            İlk Setimi Oluştur
          </button>
        </div>
      ) : (
        <div className="sp-dashboard__grid">
          {sets.map((set, i) => (
            <SetCard key={set.id} set={set} index={i} onClick={() => onNavigateToSet(set.id)} />
          ))}

          {/* Add new set card */}
          <button className="sp-set-card sp-set-card--add" onClick={onCreateSet}>
            <span className="sp-set-card--add-icon">+</span>
            <span className="sp-set-card--add-text">Yeni Set Oluştur</span>
          </button>
        </div>
      )}
    </div>
  );
}

import './DashboardPage.css';
import { MonitorSmartphone, TrendingDown, Package, Zap } from 'lucide-react';
import { formatPrice } from '../../utils/formatPrice';
import SetCard from './SetCard';

export default function DashboardPage({ sets = [], onNavigateToSet, onCreateSet }) {
  // Calculate summary stats
  const totalProducts = sets.reduce((sum, s) => sum + (s.products?.length || 0), 0);
  const totalCost = sets.reduce((sum, s) => {
    const products = s.products || [];
    return sum + products.reduce((pSum, p) => pSum + (p.current_price || p.locked_price || 0), 0);
  }, 0);

  return (
    <div className="sp-dashboard animate-fade-in">
      {/* Page Header */}
      <div className="sp-dashboard__header">
        <div>
          <h1 className="sp-dashboard__title">Dashboard</h1>
          <p className="sp-dashboard__subtitle">Tüm setlerinizin genel durumu</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="sp-dashboard__stats">
        <div className="sp-stat-card">
          <div className="sp-stat-card__icon" style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary-hover)' }}>
            <MonitorSmartphone size={20} />
          </div>
          <div className="sp-stat-card__info">
            <span className="sp-stat-card__value">{sets.length}</span>
            <span className="sp-stat-card__label">Aktif Set</span>
          </div>
        </div>

        <div className="sp-stat-card">
          <div className="sp-stat-card__icon" style={{ background: 'var(--color-secondary-muted)', color: 'var(--color-secondary)' }}>
            <Package size={20} />
          </div>
          <div className="sp-stat-card__info">
            <span className="sp-stat-card__value">{totalProducts}</span>
            <span className="sp-stat-card__label">Takip Edilen Ürün</span>
          </div>
        </div>

        <div className="sp-stat-card">
          <div className="sp-stat-card__icon" style={{ background: 'var(--color-success-muted)', color: 'var(--color-success)' }}>
            <TrendingDown size={20} />
          </div>
          <div className="sp-stat-card__info">
            <span className="sp-stat-card__value font-mono">{formatPrice(totalCost)}</span>
            <span className="sp-stat-card__label">Toplam Maliyet</span>
          </div>
        </div>
      </div>

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

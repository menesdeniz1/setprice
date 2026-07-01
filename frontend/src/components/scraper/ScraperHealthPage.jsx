import './ScraperHealthPage.css';
import { useState, useEffect, useCallback } from 'react';
import { Activity, RefreshCw } from 'lucide-react';
import { getScraperHealth } from '../../api/client';
import { formatRelativeTime } from '../../utils/formatPrice';
import { STATUS_CONFIG } from '../../utils/constants';
import Button from '../ui/Button';

export default function ScraperHealthPage() {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getScraperHealth();
      setDomains(Array.isArray(data) ? data : []);
      setLoadError(false);
    } catch (err) {
      console.error(err);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="sp-scraperhealth animate-fade-in">
      <div className="sp-scraperhealth__header">
        <div>
          <h1 className="sp-scraperhealth__title">Scraper Sağlığı</h1>
          <p className="sp-scraperhealth__subtitle">Domain bazlı tarama başarı/hata istatistikleri</p>
        </div>
        <Button variant="secondary" icon={RefreshCw} onClick={load} loading={loading}>
          Yenile
        </Button>
      </div>

      {loading ? (
        <div className="sp-scraperhealth__grid">
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ width: '100%', height: '128px' }} />
          ))}
        </div>
      ) : loadError ? (
        <div className="sp-scraperhealth__empty sp-scraperhealth__empty--error">
          <p>Scraper sağlık verileri yüklenirken bir sorun oluştu.</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={load}>
            Tekrar Dene
          </Button>
        </div>
      ) : domains.length === 0 ? (
        <div className="sp-scraperhealth__empty">
          <div className="sp-scraperhealth__empty-icon">
            <Activity size={32} />
          </div>
          <h3>Henüz veri yok</h3>
          <p>İlk tarama yapıldığında domain bazlı istatistikler burada görünecek.</p>
        </div>
      ) : (
        <div className="sp-scraperhealth__grid">
          {domains.map(d => {
            const total = d.success_count + d.failure_count;
            const rate = total > 0 ? Math.round((d.success_count / total) * 100) : 0;
            const statusCfg = STATUS_CONFIG[d.last_status] || STATUS_CONFIG.BEKLEMEDE;
            const barColor = rate >= 80 ? 'var(--color-success)' : rate >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
            return (
              <div key={d.domain} className="sp-scraperhealth__card">
                <div className="sp-scraperhealth__card-header">
                  <span className="sp-scraperhealth__domain truncate">{d.domain}</span>
                  <span className="sp-scraperhealth__status" style={{ color: statusCfg.color, background: statusCfg.bg }}>
                    {statusCfg.label}
                  </span>
                </div>
                <div className="sp-scraperhealth__bar">
                  <div className="sp-scraperhealth__bar-fill" style={{ width: `${rate}%`, background: barColor }} />
                </div>
                <div className="sp-scraperhealth__stats">
                  <span className="font-mono">%{rate} başarı</span>
                  <span className="sp-scraperhealth__stats-detail font-mono">
                    {d.success_count} başarılı · {d.failure_count} hatalı
                  </span>
                </div>
                <div className="sp-scraperhealth__updated">
                  Son kontrol: {formatRelativeTime(d.last_checked_at)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

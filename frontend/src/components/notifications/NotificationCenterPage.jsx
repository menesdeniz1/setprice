import './NotificationCenterPage.css';
import { useState, useEffect, useCallback } from 'react';
import { Bell, CheckCheck, RefreshCw } from 'lucide-react';
import { getAlerts, markAlertRead, markAllAlertsRead } from '../../api/client';
import { formatRelativeTime } from '../../utils/formatPrice';
import { ALERT_TYPE_CONFIG } from '../../utils/constants';
import Button from '../ui/Button';
import SegmentedToggle from '../ui/SegmentedToggle';

export default function NotificationCenterPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [filter, setFilter] = useState('all'); // 'all' | 'unread'

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAlerts();
      setAlerts(Array.isArray(data) ? data : []);
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

  const unreadCount = alerts.filter(a => !a.is_read).length;
  const visibleAlerts = filter === 'unread' ? alerts.filter(a => !a.is_read) : alerts;

  const handleMarkRead = async (id) => {
    await markAlertRead(id);
    setAlerts(prev => prev.map(a => (a.id === id ? { ...a, is_read: true } : a)));
  };

  const handleMarkAllRead = async () => {
    await markAllAlertsRead();
    setAlerts(prev => prev.map(a => ({ ...a, is_read: true })));
  };

  return (
    <div className="sp-notifcenter animate-fade-in">
      <div className="sp-notifcenter__header">
        <div>
          <h1 className="sp-notifcenter__title">Bildirim Merkezi</h1>
          <p className="sp-notifcenter__subtitle">Fiyat uyarıları ve sinyal değişiklikleri</p>
        </div>
        {unreadCount > 0 && (
          <Button variant="secondary" icon={CheckCheck} onClick={handleMarkAllRead}>
            Tümünü Okundu İşaretle
          </Button>
        )}
      </div>

      <div className="sp-notifcenter__controls">
        <SegmentedToggle
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: `Tümü (${alerts.length})` },
            { value: 'unread', label: `Okunmamış (${unreadCount})` },
          ]}
        />
      </div>

      {loading ? (
        <div className="sp-notifcenter__list">
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ width: '100%', height: '64px', marginBottom: '8px' }} />
          ))}
        </div>
      ) : loadError ? (
        <div className="sp-notifcenter__empty sp-notifcenter__empty--error">
          <p>Bildirimler yüklenirken bir sorun oluştu.</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={load}>
            Tekrar Dene
          </Button>
        </div>
      ) : visibleAlerts.length === 0 ? (
        <div className="sp-notifcenter__empty">
          <div className="sp-notifcenter__empty-icon">
            <Bell size={32} />
          </div>
          <h3>{filter === 'unread' ? 'Okunmamış bildirim yok' : 'Henüz bildirim yok'}</h3>
          <p>Fiyat sinyalleri değiştiğinde veya hedeflerinize ulaşıldığında burada görünecek.</p>
        </div>
      ) : (
        <div className="sp-notifcenter__list">
          {visibleAlerts.map(alert => {
            const cfg = ALERT_TYPE_CONFIG[alert.alert_type] || ALERT_TYPE_CONFIG.SIGNAL_CHANGE;
            const Icon = cfg.icon;
            return (
              <div
                key={alert.id}
                className={`sp-notifcenter__row ${!alert.is_read ? 'sp-notifcenter__row--unread' : ''}`}
                onClick={() => !alert.is_read && handleMarkRead(alert.id)}
              >
                <div className="sp-notifcenter__row-icon" style={{ background: cfg.bg }}>
                  <Icon size={18} style={{ color: cfg.color }} />
                </div>
                <div className="sp-notifcenter__row-body">
                  <div className="sp-notifcenter__row-title">{alert.title}</div>
                  <div className="sp-notifcenter__row-message">{alert.message}</div>
                </div>
                <div className="sp-notifcenter__row-meta">
                  <span className="sp-notifcenter__row-time">{formatRelativeTime(alert.created_at)}</span>
                  {!alert.is_read && <span className="sp-notifcenter__row-dot" />}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

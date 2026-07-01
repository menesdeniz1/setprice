import { useState, useEffect, useRef } from 'react';
import { Bell, CheckCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getAlerts, getUnreadAlertCount, markAlertRead, markAllAlertsRead } from '../../api/client';
import { ALERT_TYPE_CONFIG } from '../../utils/constants';

const DROPDOWN_WIDTH = 360;

export default function AlertBell() {
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const panelRef = useRef(null);
  const buttonRef = useRef(null);

  // Polling for unread count
  useEffect(() => {
    const fetchCount = async () => {
      try {
        const data = await getUnreadAlertCount();
        setUnreadCount(data.count || 0);
      } catch (e) { /* silent */ }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30000); // 30 saniyede bir
    return () => clearInterval(interval);
  }, []);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen]);

  const handleOpen = async () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + 8,
        left: Math.max(8, Math.min(rect.right - DROPDOWN_WIDTH, window.innerWidth - DROPDOWN_WIDTH - 8)),
      });
    }
    if (next) {
      setLoading(true);
      try {
        const data = await getAlerts();
        setAlerts(Array.isArray(data) ? data : []);
      } catch (e) { setAlerts([]); }
      finally { setLoading(false); }
    }
  };

  const handleMarkRead = async (id) => {
    await markAlertRead(id);
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_read: true } : a));
    setUnreadCount(prev => Math.max(0, prev - 1));
  };

  const handleMarkAllRead = async () => {
    await markAllAlertsRead();
    setAlerts(prev => prev.map(a => ({ ...a, is_read: true })));
    setUnreadCount(0);
  };

  const formatTime = (dateStr) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now - d;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${mins}dk önce`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}sa önce`;
    return `${Math.floor(hours / 24)}g önce`;
  };

  return (
    <div ref={panelRef} style={{ position: 'relative' }}>
      {/* Bell Button */}
      <button
        ref={buttonRef}
        onClick={handleOpen}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          position: 'relative',
          padding: '6px',
          color: 'rgba(255, 255, 255, 0.7)',
        }}
        title="Bildirimler"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute',
            top: 0,
            right: 0,
            background: 'var(--color-danger)',
            color: 'white',
            fontSize: '10px',
            fontWeight: '700',
            borderRadius: '50%',
            width: '16px',
            height: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
          }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel — position:fixed + coordinates from the button's
          actual screen position, so it always renders fully on-screen
          instead of being clipped by the sidebar's overflow:hidden. */}
      {isOpen && (
        <div style={{
          position: 'fixed',
          top: dropdownPos.top,
          left: dropdownPos.left,
          width: `${DROPDOWN_WIDTH}px`,
          maxHeight: '480px',
          background: 'var(--color-bg-primary)',
          border: '1px solid var(--color-border)',
          borderRadius: '8px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
          zIndex: 1000,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
          {/* Header */}
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--color-border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span style={{ fontWeight: '700', fontSize: '14px', color: 'var(--color-ink)' }}>
              Bildirimler {unreadCount > 0 && `(${unreadCount})`}
            </span>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px',
                  color: 'var(--color-brand-accent)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <CheckCheck size={14} />
                Tümünü Oku
              </button>
            )}
          </div>

          {/* Alert List */}
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {loading ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)' }}>Yükleniyor...</div>
            ) : alerts.length === 0 ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '13px' }}>
                Henüz bildirim yok
              </div>
            ) : (
              alerts.map(alert => {
                const cfg = ALERT_TYPE_CONFIG[alert.alert_type] || ALERT_TYPE_CONFIG.SIGNAL_CHANGE;
                const Icon = cfg.icon;
                return (
                  <div
                    key={alert.id}
                    onClick={() => !alert.is_read && handleMarkRead(alert.id)}
                    style={{
                      padding: '12px 16px',
                      borderBottom: '1px solid var(--color-border-subtle)',
                      cursor: alert.is_read ? 'default' : 'pointer',
                      background: alert.is_read ? 'var(--color-bg-primary)' : 'var(--color-brand-accent-muted)',
                      display: 'flex',
                      gap: '12px',
                      alignItems: 'flex-start',
                      transition: 'background 0.2s',
                    }}
                  >
                    <div style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      background: cfg.bg,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <Icon size={16} style={{ color: cfg.color }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: '13px',
                        fontWeight: alert.is_read ? '400' : '600',
                        color: 'var(--color-ink)',
                        marginBottom: '2px',
                      }}>
                        {alert.title}
                      </div>
                      <div style={{
                        fontSize: '12px',
                        color: 'var(--color-text-secondary)',
                        lineHeight: '1.4',
                      }}>
                        {alert.message}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                        {formatTime(alert.created_at)}
                      </div>
                    </div>
                    {!alert.is_read && (
                      <div style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        background: 'var(--color-brand-accent)',
                        flexShrink: 0,
                        marginTop: '6px',
                      }} />
                    )}
                  </div>
                );
              })
            )}
          </div>
          <Link
            to="/notifications"
            onClick={() => setIsOpen(false)}
            style={{
              display: 'block',
              textAlign: 'center',
              padding: '10px',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--color-brand-accent)',
              borderTop: '1px solid var(--color-border-subtle)',
              textDecoration: 'none',
            }}
          >
            Tüm Bildirimleri Gör
          </Link>
        </div>
      )}
    </div>
  );
}

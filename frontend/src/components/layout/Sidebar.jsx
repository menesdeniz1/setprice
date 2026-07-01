import './Sidebar.css';
import { useState } from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import { LayoutDashboard, MonitorSmartphone, Library, LogOut, Plus, Zap, PanelLeftClose, Send, Activity, Bell } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import AlertBell from '../ui/AlertBell';
import NotificationSettingsModal from '../ui/NotificationSettingsModal';

export default function Sidebar({ sets = [], onCreateSet, isOpen, onClose }) {
  const { user, logout, setUser } = useAuth();
  const navigate = useNavigate();

  const [confirmLogout, setConfirmLogout] = useState(false);
  const [showNotifSettings, setShowNotifSettings] = useState(false);

  const handleLogout = () => {
    if (!confirmLogout) {
      setConfirmLogout(true);
      setTimeout(() => setConfirmLogout(false), 3000);
      return;
    }
    logout();
    navigate('/login');
  };

  return (
    <>
      <aside className={`sp-sidebar ${isOpen ? 'sp-sidebar--open' : ''}`}>
      {/* Logo */}
      <div className="sp-sidebar__logo">
        <Link to="/" className="sp-sidebar__logo-link">
          <div className="sp-sidebar__logo-icon">
            <Zap size={20} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span className="sp-sidebar__logo-text" style={{ color: '#FFFFFF' }}>SetPrice</span>
            <span className="sp-sidebar__logo-badge" style={{ background: 'rgba(8, 145, 178, 0.25)', color: 'var(--color-brand-accent)' }}>Beta</span>
          </div>
        </Link>
        <AlertBell />
        <button className="sp-sidebar__collapse-btn" onClick={onClose} title="Menüyü Kapat">
          <PanelLeftClose size={18} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="sp-sidebar__nav">
        <div className="sp-sidebar__section-label">Ana Sayfa</div>

        <NavLink to="/" end className={({ isActive }) => `sp-sidebar__link ${isActive ? 'sp-sidebar__link--active' : ''}`}>
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>

        <div className="sp-sidebar__section-label" style={{ marginTop: 'var(--space-5)' }}>
          Setlerim
        </div>

        {sets.map((set) => (
          <NavLink
            key={set.id}
            to={`/sets/${set.id}`}
            className={({ isActive }) => `sp-sidebar__link ${isActive ? 'sp-sidebar__link--active' : ''}`}
          >
            <MonitorSmartphone size={16} />
            <span className="truncate">{set.name}</span>
          </NavLink>
        ))}

        <button className="sp-sidebar__link sp-sidebar__link--add" onClick={onCreateSet}>
          <Plus size={16} />
          <span>Yeni Set Ekle</span>
        </button>

        <div className="sp-sidebar__section-label" style={{ marginTop: 'var(--space-5)' }}>
          İzleme Listesi
        </div>

        <NavLink to="/library" className={({ isActive }) => `sp-sidebar__link ${isActive ? 'sp-sidebar__link--active' : ''}`}>
          <Library size={18} />
          <span>Watchlist (Kütüphane)</span>
        </NavLink>

        <div className="sp-sidebar__section-label" style={{ marginTop: 'var(--space-5)' }}>
          Sistem
        </div>

        <NavLink to="/scraper-health" className={({ isActive }) => `sp-sidebar__link ${isActive ? 'sp-sidebar__link--active' : ''}`}>
          <Activity size={18} />
          <span>Scraper Sağlığı</span>
        </NavLink>

        <NavLink to="/notifications" className={({ isActive }) => `sp-sidebar__link ${isActive ? 'sp-sidebar__link--active' : ''}`}>
          <Bell size={18} />
          <span>Bildirim Merkezi</span>
        </NavLink>
      </nav>

      {/* Footer */}
      <div className="sp-sidebar__footer">
        <div className="sp-sidebar__user">
          <div className="sp-sidebar__avatar">
            {user?.email?.charAt(0).toUpperCase() || '?'}
          </div>
          <div className="sp-sidebar__user-info">
            <span className="sp-sidebar__user-email truncate">{user?.email || 'Kullanıcı'}</span>
          </div>
          <button className="sp-sidebar__logout" onClick={() => setShowNotifSettings(true)} title="Bildirim Ayarları (Telegram)">
            <Send size={16} />
          </button>
          <button className="sp-sidebar__logout" onClick={handleLogout} title="Çıkış Yap">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>

    <NotificationSettingsModal
      isOpen={showNotifSettings}
      onClose={() => setShowNotifSettings(false)}
      user={user}
      onUserUpdate={setUser}
    />
    </>
  );
}

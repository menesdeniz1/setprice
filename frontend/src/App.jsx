import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from './context/AuthContext';
import { useToast } from './context/ToastContext';
import { getSets, createSet, getSetTemplates } from './api/client';

import Layout from './components/layout/Layout';
import LoginPage from './components/auth/LoginPage';
import DashboardPage from './components/dashboard/DashboardPage';
import SetDetailPage from './components/sets/SetDetailPage';
import LibraryPage from './components/library/LibraryPage';
import ScraperHealthPage from './components/scraper/ScraperHealthPage';
import NotificationCenterPage from './components/notifications/NotificationCenterPage';
import Modal from './components/ui/Modal';
import Button from './components/ui/Button';

function App() {
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [sets, setSets] = useState([]);
  const [setsLoading, setSetsLoading] = useState(false);
  const [showCreateSet, setShowCreateSet] = useState(false);
  const [newSetName, setNewSetName] = useState('');
  const [newSetBudget, setNewSetBudget] = useState('');
  const [creating, setCreating] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateKey, setSelectedTemplateKey] = useState(null);

  useEffect(() => {
    getSetTemplates()
      .then(data => {
        setTemplates(Array.isArray(data) ? data : []);
        if (Array.isArray(data) && data.length > 0) setSelectedTemplateKey(data[0].key);
      })
      .catch(() => {});
  }, []);

  const loadSets = useCallback(async () => {
    if (!user) return;
    setSetsLoading(true);
    try {
      const data = await getSets();
      setSets(data);
    } catch (err) {
      console.error(err);
      toast.error('Setler yüklenemedi');
    } finally {
      setSetsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadSets();
  }, [loadSets]);

  const handleCreateSet = async (e) => {
    e.preventDefault();
    if (!newSetName.trim()) {
      toast.error('Lütfen bir set adı girin');
      return;
    }
    if (newSetName.trim().length < 3) {
      toast.error('Set adı en az 3 karakter olmalıdır');
      return;
    }
    const parsedBudget = parseFloat(newSetBudget) || 0;
    if (parsedBudget < 0) {
      toast.error('Bütçe negatif olamaz');
      return;
    }
    setCreating(true);
    try {
      const newSet = await createSet(newSetName.trim(), parseFloat(newSetBudget) || 0, selectedTemplateKey);
      setSets(prev => [...prev, newSet]);
      setShowCreateSet(false);
      setNewSetName('');
      setNewSetBudget('');
      toast.success(`"${newSet.name}" oluşturuldu!`);
      navigate(`/sets/${newSet.id}`);
    } catch (err) {
      toast.error('Set oluşturulamadı: ' + err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleSetDeleted = () => {
    loadSets();
    navigate('/');
  };

  // Auth loading state
  if (authLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div className="skeleton" style={{ width: '200px', height: '40px' }} />
      </div>
    );
  }

  // Not logged in
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <>
      <Routes>
        <Route element={<Layout sets={sets} onCreateSet={() => setShowCreateSet(true)} />}>
          <Route
            index
            element={
              <DashboardPage
                sets={sets}
                onNavigateToSet={(id) => navigate(`/sets/${id}`)}
                onCreateSet={() => setShowCreateSet(true)}
              />
            }
          />
          <Route
            path="/sets/:setId"
            element={<SetDetailPage onSetDeleted={handleSetDeleted} />}
          />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/scraper-health" element={<ScraperHealthPage />} />
          <Route path="/notifications" element={<NotificationCenterPage />} />
        </Route>
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Create Set Modal */}
      <Modal
        isOpen={showCreateSet}
        onClose={() => setShowCreateSet(false)}
        title="Yeni Set Oluştur"
      >
        <form onSubmit={handleCreateSet} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>
          {templates.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                Şablon
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 'var(--space-2)' }}>
                {templates.map(t => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setSelectedTemplateKey(t.key)}
                    style={{
                      padding: 'var(--space-3)',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid ${selectedTemplateKey === t.key ? 'var(--color-primary)' : 'var(--color-border)'}`,
                      background: selectedTemplateKey === t.key ? 'var(--color-primary-muted)' : 'var(--color-bg-elevated)',
                      color: 'var(--color-text-primary)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 'var(--text-sm)',
                      transition: 'all var(--transition-fast)',
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: '4px' }}>{t.name}</div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                      {t.categories.length > 0 ? t.categories.slice(0, 3).join(', ') + (t.categories.length > 3 ? '...' : '') : 'Kategorileri kendin belirle'}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
              Set Adı
            </label>
            <input
              type="text"
              className="sp-login__input"
              placeholder="Örn: AMD Gaming Seti"
              value={newSetName}
              onChange={e => setNewSetName(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
              Hedef Bütçe (₺) <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>— opsiyonel</span>
            </label>
            <input
              type="number"
              className="sp-login__input"
              placeholder="Örn: 150000"
              value={newSetBudget}
              onChange={e => setNewSetBudget(e.target.value)}
              min="0"
              step="1000"
            />
          </div>
          <Button type="submit" fullWidth loading={creating}>
            Set Oluştur
          </Button>
        </form>
      </Modal>
    </>
  );
}

export default App;

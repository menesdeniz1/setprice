import './SetDetailPage.css';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { RefreshCw, Settings, Trash2, X, AlertTriangle } from 'lucide-react';
import { getSetById, scanSet, deleteProduct, updateProduct, addProductToSet, deleteSet, updateSet, addSetCategory, renameSetCategory, deleteSetCategory } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { formatPrice, calcPercent } from '../../utils/formatPrice';
import Button from '../ui/Button';
import Modal from '../ui/Modal';
import SegmentedToggle from '../ui/SegmentedToggle';
import StatCard from '../ui/StatCard';
import ScoreRing from '../ui/ScoreRing';
import BudgetBar from './BudgetBar';
import CategoryGroup from './CategoryGroup';
import AddProductWidget from './AddProductWidget';
import ProductDetailPanel from '../products/ProductDetailPanel';

export default function SetDetailPage({ onSetDeleted }) {
  const { setId } = useParams();
  const toast = useToast();

  const [setData, setSetData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [editName, setEditName] = useState('');
  const [editBudget, setEditBudget] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [groupBy, setGroupBy] = useState('category'); // 'category' | 'signal'
  const [newCategoryName, setNewCategoryName] = useState('');
  const [editingCategoryId, setEditingCategoryId] = useState(null);
  const [editingCategoryName, setEditingCategoryName] = useState('');

  const loadSet = useCallback(async () => {
    try {
      const data = await getSetById(setId);
      setSetData(prev => {
        if (prev && prev.products && data.products) {
          const prevMap = new Map(prev.products.map(p => [p.library_product_id, p]));
          const buyTransitions = [];
          for (const np of data.products) {
            const op = prevMap.get(np.library_product_id);
            if (op && op.decision_signal !== 'BUY' && np.decision_signal === 'BUY') {
              buyTransitions.push(np);
            }
          }
          if (buyTransitions.length > 0) {
            toast.success(`Akıllı Uyarı: Setinizdeki ${buyTransitions.length} ürün BUY seviyesine girdi! 🚀`);
          }
        }
        return data;
      });
    } catch (err) {
      console.error(err);
      toast.error('Set yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [setId]);

  useEffect(() => {
    setLoading(true);
    loadSet();
  }, [loadSet]);

  // Polling for set scan
  useEffect(() => {
    if (!scanning) return;
    const interval = setInterval(() => {
      loadSet();
    }, 3000);

    const timeout = setTimeout(() => {
      clearInterval(interval);
      setScanning(false);
      toast.success('Fiyat güncelleme işlemi tamamlandı');
      loadSet();
    }, 20000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [scanning, loadSet]);

  const handleScan = async () => {
    setScanning(true);
    toast.info('Fiyat taraması arkaplanda başlatıldı...');
    try {
      await scanSet(setId);
    } catch (err) {
      console.error(err);
      toast.error('Tarama başlatılamadı');
      setScanning(false);
    }
  };

  const handleToggleActive = async (product) => {
    try {
      await updateProduct(product.id, { is_active: !product.is_active });
      await loadSet();
    } catch (err) {
      console.error(err);
      toast.error('Ürün durumu güncellenemedi');
    }
  };

  const handleToggleLock = async (product) => {
    try {
      const isLocking = !product.is_locked;
      await updateProduct(product.id, { 
        is_locked: isLocking,
        locked_price: isLocking ? product.current_price : null
      });
      await loadSet();
    } catch (err) {
      console.error(err);
      toast.error('Kilit durumu güncellenemedi');
    }
  };

  const handleUpdateLockedPrice = async (product, newPrice) => {
    try {
      await updateProduct(product.id, { locked_price: newPrice });
      await loadSet();
      toast.success('Fiyat kilitlendi');
    } catch (err) {
      console.error(err);
      toast.error('Fiyat güncellenemedi');
    }
  };

  const handleDeleteProduct = async (productId) => {
    try {
      await deleteProduct(productId);
      await loadSet();
      toast.success('Ürün setten kaldırıldı');
    } catch (err) {
      console.error(err);
      toast.error('Ürün silinemedi');
    }
  };

  const handleAddProduct = async ({ originalLink, libraryProductId, category }) => {
    try {
      await addProductToSet(setId, { originalLink, libraryProductId, category });
      await loadSet();
      toast.success('Ürün eklendi!');
    } catch (err) {
      toast.error('Ürün eklenirken hata: ' + err.message);
      throw err;
    }
  };

  const handleUpdateSet = async () => {
    try {
      const updates = {};
      if (editName.trim()) updates.name = editName.trim();
      if (editBudget !== '') updates.target_budget = parseFloat(editBudget) || 0;
      await updateSet(setId, updates);
      await loadSet();
      setShowSettings(false);
      setConfirmDelete(false);
      toast.success('Set güncellendi');
    } catch (err) {
      console.error(err);
      toast.error('Set güncellenemedi');
    }
  };

  const handleDeleteSet = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    try {
      await deleteSet(setId);
      toast.success('Set silindi');
      if (onSetDeleted) onSetDeleted();
    } catch (err) {
      console.error(err);
      toast.error('Set silinemedi');
    }
  };

  const handleAddCategory = async (e) => {
    e.preventDefault();
    if (!newCategoryName.trim()) return;
    try {
      await addSetCategory(setId, newCategoryName.trim());
      setNewCategoryName('');
      await loadSet();
    } catch (err) {
      toast.error('Kategori eklenemedi');
    }
  };

  const handleRenameCategory = async (categoryId, currentName) => {
    setEditingCategoryId(null);
    const trimmed = editingCategoryName.trim();
    if (!trimmed || trimmed === currentName) return;
    try {
      await renameSetCategory(setId, categoryId, trimmed);
      await loadSet();
    } catch (err) {
      toast.error('Kategori güncellenemedi');
    }
  };

  const handleDeleteCategory = async (categoryId) => {
    try {
      await deleteSetCategory(setId, categoryId);
      await loadSet();
    } catch (err) {
      toast.error('Kategori silinemedi');
    }
  };

  if (loading) {
    return (
      <div className="sp-setdetail__loading">
        <div className="skeleton" style={{ width: '300px', height: '32px', marginBottom: '16px' }} />
        <div className="skeleton" style={{ width: '100%', height: '80px', marginBottom: '16px' }} />
        <div className="skeleton" style={{ width: '100%', height: '200px' }} />
      </div>
    );
  }

  if (!setData) {
    return (
      <div className="sp-setdetail__error">
        <div className="sp-setdetail__error-icon">
          <AlertTriangle size={32} />
        </div>
        <h3>Set yüklenemedi</h3>
        <p>Bağlantı sorunu olabilir veya set artık mevcut değil.</p>
        <Button variant="secondary" icon={RefreshCw} onClick={loadSet}>
          Tekrar Dene
        </Button>
      </div>
    );
  }

  const products = setData.products || [];
  const activeProducts = products.filter(p => p.is_active);
  const totalCost = activeProducts.reduce((sum, p) => sum + (p.current_price || p.locked_price || 0), 0);
  const budgetPercent = calcPercent(totalCost, setData.target_budget);

  // Calculate Health Score
  const scoredProducts = activeProducts.filter(p => p.value_score !== undefined && p.value_score !== null);
  const healthScore = scoredProducts.length > 0 
    ? Math.round(scoredProducts.reduce((acc, p) => acc + p.value_score, 0) / scoredProducts.length)
    : 0;

  // Grouping logic
  const grouped = {};
  products.forEach(p => {
    let key;
    if (groupBy === 'signal') {
      const sig = p.decision_signal || 'WAIT';
      key = sig === 'BUY' ? '🟢 Alım Fırsatı (BUY)' : sig === 'AVOID' ? '🔴 Uzak Dur (AVOID)' : '🟡 Bekle (WAIT)';
    } else {
      key = p.category || 'Diğer';
    }
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(p);
  });

  // Sort groups if by signal
  const sortedGroupKeys = Object.keys(grouped).sort((a, b) => {
    if (groupBy === 'signal') {
      if (a.includes('BUY')) return -1;
      if (b.includes('BUY')) return 1;
      if (a.includes('AVOID')) return 1;
      if (b.includes('AVOID')) return -1;
      return 0;
    }
    return a.localeCompare(b);
  });

  return (
    <div className="sp-setdetail animate-fade-in">
      {/* Header */}
      <div className="sp-setdetail__header">
        <div>
          <h1 className="sp-setdetail__title">{setData.name}</h1>
          <p className="sp-setdetail__subtitle">
            {activeProducts.length} aktif ürün · Toplam{' '}
            <span className="font-mono" style={{ color: 'var(--color-secondary)', fontWeight: 700 }}>
              {formatPrice(totalCost)}
            </span>
          </p>
        </div>
        <div className="sp-setdetail__actions">
          <Button variant="secondary" size="sm" icon={Settings} onClick={() => {
            setEditName(setData.name);
            setEditBudget(setData.target_budget?.toString() || '0');
            setShowSettings(true);
          }}>
            Ayarlar
          </Button>
          <Button icon={RefreshCw} loading={scanning} onClick={handleScan}>
            Fiyatları Güncelle
          </Button>
        </div>
      </div>

      {/* Budget Bar */}
      {setData.target_budget > 0 && (
        <BudgetBar current={totalCost} target={setData.target_budget} percent={budgetPercent} />
      )}

      {/* Summary Cards */}
      <div className="sp-setdetail__stats">
        <StatCard label="Toplam Parça" value={products.length} mono />
        <StatCard
          label="Set Sağlığı"
          value={
            scoredProducts.length > 0
              ? <ScoreRing value={healthScore} size={44} strokeWidth={4} />
              : <ScoreRing value={null} size={44} strokeWidth={4} />
          }
        />
        <StatCard label="Aktif" value={activeProducts.length} valueColor="var(--color-success)" mono />
        <StatCard
          label="Taranmadı"
          value={products.filter(p => p.status === 'BEKLEMEDE').length}
          valueColor="var(--color-warning)"
          mono
        />
        <StatCard
          label="Hatalı"
          value={products.filter(p => p.status === 'FAILED').length}
          valueColor="var(--color-danger)"
          mono
        />
      </div>

      {/* Add Product Widget */}
      <AddProductWidget onAdd={handleAddProduct} categories={setData.categories || []} />

      {/* Group By Toggle */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
        <SegmentedToggle
          value={groupBy}
          onChange={setGroupBy}
          options={[
            { value: 'category', label: 'Kategoriye Göre' },
            { value: 'signal', label: 'Sinyale Göre' },
          ]}
        />
      </div>

      {/* Product Groups */}
      <div className="sp-setdetail__products">
        {Object.keys(grouped).length === 0 ? (
          <div className="sp-setdetail__empty">
            Sette henüz ürün yok. Aşağıdan link yapıştırarak veya kütüphaneden seçerek ürün ekleyin.
          </div>
        ) : (
          sortedGroupKeys.map((cat) => (
            <CategoryGroup
              key={cat}
              category={cat}
              products={grouped[cat]}
              onToggleActive={handleToggleActive}
              onToggleLock={handleToggleLock}
              onUpdateLockedPrice={handleUpdateLockedPrice}
              onDelete={handleDeleteProduct}
              onSelectProduct={setSelectedProduct}
            />
          ))
        )}
      </div>

      {/* Product Detail Side Panel */}
      {selectedProduct && (
        <ProductDetailPanel
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}

      {/* Set Settings Modal */}
      <Modal 
        isOpen={showSettings} 
        onClose={() => {
          setShowSettings(false);
          setConfirmDelete(false);
        }} 
        title="Set Ayarları"
      >
        <div className="sp-setdetail__settings-form">
          <div className="sp-setdetail__settings-field">
            <label>Set Adı</label>
            <input
              type="text"
              value={editName}
              onChange={e => setEditName(e.target.value)}
              className="sp-login__input"
            />
          </div>
          <div className="sp-setdetail__settings-field">
            <label>Hedef Bütçe (₺)</label>
            <input
              type="number"
              value={editBudget}
              onChange={e => setEditBudget(e.target.value)}
              className="sp-login__input"
              min="0"
              step="1000"
            />
          </div>
          <div className="sp-setdetail__settings-field">
            <label>Kategoriler</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
              {(setData.categories || []).length === 0 && (
                <span style={{ fontSize: '13px', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                  Henüz kategori yok — aşağıdan ekleyebilirsin.
                </span>
              )}
              {(setData.categories || []).map(cat => (
                <div
                  key={cat.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '4px 10px', borderRadius: 'var(--radius-full)',
                    border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
                    fontSize: '13px',
                  }}
                >
                  {editingCategoryId === cat.id ? (
                    <input
                      autoFocus
                      value={editingCategoryName}
                      onChange={e => setEditingCategoryName(e.target.value)}
                      onBlur={() => handleRenameCategory(cat.id, cat.name)}
                      onKeyDown={e => e.key === 'Enter' && e.target.blur()}
                      style={{ width: '80px', border: 'none', outline: 'none', background: 'transparent', fontSize: '13px', color: 'var(--color-text-primary)' }}
                    />
                  ) : (
                    <span
                      onClick={() => { setEditingCategoryId(cat.id); setEditingCategoryName(cat.name); }}
                      style={{ cursor: 'pointer', color: 'var(--color-text-primary)' }}
                      title="Yeniden adlandırmak için tıkla"
                    >
                      {cat.name}
                    </span>
                  )}
                  <button
                    onClick={() => handleDeleteCategory(cat.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', padding: 0, display: 'flex' }}
                    title="Kategoriyi sil"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
            <form onSubmit={handleAddCategory} style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                value={newCategoryName}
                onChange={e => setNewCategoryName(e.target.value)}
                placeholder="Yeni kategori adı..."
                className="sp-login__input"
                style={{ flex: 1 }}
              />
              <Button type="submit" size="sm" variant="secondary">Ekle</Button>
            </form>
          </div>
          <div className="sp-setdetail__settings-actions">
            <Button onClick={handleUpdateSet}>Kaydet</Button>
            <Button 
              variant={confirmDelete ? "primary" : "danger"} 
              icon={confirmDelete ? null : Trash2} 
              onClick={handleDeleteSet}
            >
              {confirmDelete ? "Emin misiniz? Silmek için tekrar basın" : "Seti Sil"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

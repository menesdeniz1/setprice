import './SetDetailPage.css';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { RefreshCw, Settings, Trash2 } from 'lucide-react';
import { getSetById, scanSet, deleteProduct, updateProduct, addProductToSet, deleteSet, updateSet } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { formatPrice, calcPercent } from '../../utils/formatPrice';
import Button from '../ui/Button';
import Modal from '../ui/Modal';
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

  const loadSet = useCallback(async () => {
    try {
      const data = await getSetById(setId);
      setSetData(data);
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

  const handleAddProduct = async ({ originalLink, libraryProductId }) => {
    try {
      await addProductToSet(setId, { originalLink, libraryProductId });
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

  if (loading) {
    return (
      <div className="sp-setdetail__loading">
        <div className="skeleton" style={{ width: '300px', height: '32px', marginBottom: '16px' }} />
        <div className="skeleton" style={{ width: '100%', height: '80px', marginBottom: '16px' }} />
        <div className="skeleton" style={{ width: '100%', height: '200px' }} />
      </div>
    );
  }

  if (!setData) return null;

  const products = setData.products || [];
  const activeProducts = products.filter(p => p.is_active);
  const totalCost = activeProducts.reduce((sum, p) => sum + (p.current_price || p.locked_price || 0), 0);
  const budgetPercent = calcPercent(totalCost, setData.target_budget);

  // Group by category
  const grouped = {};
  products.forEach(p => {
    const cat = p.category || 'Diğer';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(p);
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
        <div className="sp-mini-stat">
          <span className="sp-mini-stat__label">Toplam Parça</span>
          <span className="sp-mini-stat__value">{products.length}</span>
        </div>
        <div className="sp-mini-stat">
          <span className="sp-mini-stat__label">Aktif</span>
          <span className="sp-mini-stat__value" style={{ color: 'var(--color-success)' }}>{activeProducts.length}</span>
        </div>
        <div className="sp-mini-stat">
          <span className="sp-mini-stat__label">Taranmadı</span>
          <span className="sp-mini-stat__value" style={{ color: 'var(--color-warning)' }}>
            {products.filter(p => p.status === 'BEKLEMEDE').length}
          </span>
        </div>
        <div className="sp-mini-stat">
          <span className="sp-mini-stat__label">Hatalı</span>
          <span className="sp-mini-stat__value" style={{ color: 'var(--color-danger)' }}>
            {products.filter(p => p.status === 'FAILED').length}
          </span>
        </div>
      </div>

      {/* Add Product Widget */}
      <AddProductWidget onAdd={handleAddProduct} />

      {/* Product Groups */}
      <div className="sp-setdetail__products">
        {Object.keys(grouped).length === 0 ? (
          <div className="sp-setdetail__empty">
            Sette henüz ürün yok. Aşağıdan link yapıştırarak veya kütüphaneden seçerek ürün ekleyin.
          </div>
        ) : (
          Object.entries(grouped).map(([cat, catProducts]) => (
            <CategoryGroup
              key={cat}
              category={cat}
              products={catProducts}
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

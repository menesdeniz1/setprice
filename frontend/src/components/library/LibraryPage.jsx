import './LibraryPage.css';
import { useState, useEffect } from 'react';
import { getLibraryProducts, getLibraryCategories, scanAllLibraryProducts, scanLibraryProduct, deleteLibraryProduct, addLibraryProduct } from '../../api/client';
import { formatPrice, formatRelativeTime } from '../../utils/formatPrice';
import { STATUS_CONFIG } from '../../utils/constants';
import { ExternalLink, RefreshCw, Loader2, Search, ArrowUp, ArrowDown, Trash2, Plus } from 'lucide-react';
import Button from '../ui/Button';
import { useToast } from '../../context/ToastContext';

export default function LibraryPage() {
  const [category, setCategory] = useState('');
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [isScanningAll, setIsScanningAll] = useState(false);
  const [scanningIds, setScanningIds] = useState(new Set());
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState('updated_at');
  const [sortDir, setSortDir] = useState('desc');
  const [newProductLink, setNewProductLink] = useState('');
  const [isAddingProduct, setIsAddingProduct] = useState(false);
  const [groupDuplicates, setGroupDuplicates] = useState(() => {
    return localStorage.getItem('sp_group_dupes') !== 'false';
  });

  const toast = useToast();

  useEffect(() => {
    localStorage.setItem('sp_group_dupes', groupDuplicates);
  }, [groupDuplicates]);

  useEffect(() => {
    getLibraryCategories().then(data => {
      setCategories(Array.isArray(data) ? data : []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    loadProducts();
  }, [category]);

  // Global background scan polling
  useEffect(() => {
    if (!isScanningAll) return;
    const interval = setInterval(() => {
      loadProducts(false); // background fetch
    }, 5000);

    const timeout = setTimeout(() => {
      clearInterval(interval);
      setIsScanningAll(false);
      loadProducts(false);
    }, 30000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [isScanningAll]);

  // Single scan background polling
  useEffect(() => {
    if (scanningIds.size === 0) return;
    const interval = setInterval(() => {
      loadProducts(false);
    }, 3000);

    return () => clearInterval(interval);
  }, [scanningIds.size]);

  const loadProducts = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const data = await getLibraryProducts(category || undefined);
      setProducts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Kütüphane ürünleri yüklenemedi:', err);
      setProducts([]);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const handleScanAll = async () => {
    setIsScanningAll(true);
    toast.info("Kütüphane taraması arkaplanda başlatıldı. Ürün sayısına göre birkaç dakika sürebilir.");
    try {
      await scanAllLibraryProducts();
    } catch (err) {
      toast.error("Tarama başlatılamadı");
      console.error(err);
      setIsScanningAll(false);
    }
  };

  const handleScanSingle = async (id) => {
    setScanningIds(prev => new Set(prev).add(id));
    try {
      await scanLibraryProduct(id);
    } catch (err) {
      toast.error("Tarama başlatılamadı");
      console.error(err);
      setScanningIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      return;
    }
    
    // Stop single scan polling after 21s
    setTimeout(() => {
      setScanningIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 21000);
  };

  const handleDelete = async (id) => {
    if (confirmDeleteId === id) {
      try {
        await deleteLibraryProduct(id);
        toast.success("Ürün kütüphaneden ve tüm setlerden silindi");
        setConfirmDeleteId(null);
        loadProducts(); // reload
      } catch (err) {
        console.error(err);
        toast.error("Ürün silinemedi");
      }
    } else {
      setConfirmDeleteId(id);
      setTimeout(() => {
        setConfirmDeleteId(null);
      }, 3000);
    }
  };

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const handleAddProduct = async (e) => {
    e.preventDefault();
    if (!newProductLink.trim()) return;
    
    setIsAddingProduct(true);
    try {
      await addLibraryProduct(newProductLink.trim());
      toast.success("Ürün kütüphaneye başarıyla eklendi");
      setNewProductLink('');
      loadProducts();
      getLibraryCategories().then(data => {
        setCategories(Array.isArray(data) ? data : []);
      }).catch(() => {});
    } catch (err) {
      toast.error(err.message || "Ürün eklenemedi, linki kontrol edin");
    } finally {
      setIsAddingProduct(false);
    }
  };

  const renderSortIcon = (field) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? <ArrowUp size={12} style={{marginLeft: 4}}/> : <ArrowDown size={12} style={{marginLeft: 4}}/>;
  };

  return (
    <div className="sp-library animate-fade-in">
      <div className="sp-library__header">
        <div>
          <h1 className="sp-library__title">Ürün Kütüphanesi</h1>
          <p className="sp-library__subtitle">Daha önce eklediğiniz tüm ürünler burada listelenir</p>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          <form onSubmit={handleAddProduct} style={{ display: 'flex', gap: '8px' }}>
            <input
              type="url"
              placeholder="Ürün linki yapıştır..."
              value={newProductLink}
              onChange={e => setNewProductLink(e.target.value)}
              required
              disabled={isAddingProduct}
              style={{ padding: '8px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: '13px', width: '200px' }}
            />
            <Button type="submit" loading={isAddingProduct} icon={Plus}>
              Ekle
            </Button>
          </form>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Ürün ara..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ padding: '8px 12px 8px 36px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: '13px', width: '180px' }}
            />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-secondary)' }}>
            <input 
              type="checkbox" 
              checked={groupDuplicates} 
              onChange={e => setGroupDuplicates(e.target.checked)} 
              style={{ accentColor: 'var(--primary)' }}
            />
            Tekilleştir
          </label>
          <Button variant="primary" onClick={handleScanAll} loading={isScanningAll} icon={RefreshCw}>
            Güncelle
          </Button>
        </div>
      </div>

      {/* Category filters */}
      <div className="sp-library__filters">
        <button
          className={`sp-library__filter-btn ${category === '' ? 'sp-library__filter-btn--active' : ''}`}
          onClick={() => setCategory('')}
        >
          Tümü
        </button>
        {Array.isArray(categories) && categories.map(cat => {
          const catName = typeof cat === 'string' ? cat : cat.name;
          const catCount = typeof cat === 'string' ? null : cat.count;
          return (
            <button
              key={catName}
              className={`sp-library__filter-btn ${category === catName ? 'sp-library__filter-btn--active' : ''}`}
              onClick={() => setCategory(catName)}
            >
              {catName} {catCount != null ? <span style={{ opacity: 0.7, fontSize: '0.9em', marginLeft: '4px' }}>({catCount})</span> : ''}
            </button>
          );
        })}
      </div>

      {/* Products table */}
      {(() => {
        let displayProducts = Array.isArray(products) ? products : [];
        if (groupDuplicates) {
          const grouped = {};
          for (const p of displayProducts) {
            const key = (p.name || '').trim().toLowerCase();
            if (!grouped[key]) {
              grouped[key] = p;
            } else {
              const currentPrice = grouped[key].current_price || Infinity;
              const newPrice = p.current_price || Infinity;
              if (newPrice < currentPrice) {
                grouped[key] = p;
              }
            }
          }
          displayProducts = Object.values(grouped);
        }

        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          displayProducts = displayProducts.filter(p => 
            p.name?.toLowerCase().includes(q) || 
            p.category?.toLowerCase().includes(q) ||
            p.current_seller?.toLowerCase().includes(q)
          );
        }

        displayProducts.sort((a, b) => {
          let aVal = a[sortField];
          let bVal = b[sortField];
          
          if (sortField === 'current_price') {
            aVal = aVal || 0;
            bVal = bVal || 0;
          } else if (sortField === 'name' || sortField === 'category') {
            aVal = (aVal || '').toLowerCase();
            bVal = (bVal || '').toLowerCase();
          } else if (sortField === 'updated_at') {
            aVal = new Date(aVal || 0).getTime();
            bVal = new Date(bVal || 0).getTime();
          }

          if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
          if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
          return 0;
        });

        if (loading) {
          return (
            <div>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="skeleton" style={{ width: '100%', height: '56px', marginBottom: '8px' }} />
              ))}
            </div>
          );
        }

        if (displayProducts.length === 0) {
          return (
            <div className="sp-library__empty">
              {category ? `"${category}" kategorisinde ürün bulunamadı.` : 'Kütüphanede henüz ürün yok.'}
            </div>
          );
        }

        return (
          <div className="sp-library__table">
            <div className="sp-library__table-header">
            <span className="sp-library__col sp-library__col--name" style={{cursor: 'pointer'}} onClick={() => handleSort('name')}>
              Ürün {renderSortIcon('name')}
            </span>
            <span className="sp-library__col sp-library__col--cat" style={{cursor: 'pointer'}} onClick={() => handleSort('category')}>
              Kategori {renderSortIcon('category')}
            </span>
            <span className="sp-library__col sp-library__col--price" style={{cursor: 'pointer'}} onClick={() => handleSort('current_price')}>
              Fiyat {renderSortIcon('current_price')}
            </span>
            <span className="sp-library__col sp-library__col--seller">Satıcı</span>
            <span className="sp-library__col sp-library__col--status">Durum</span>
            <span className="sp-library__col sp-library__col--updated" style={{cursor: 'pointer'}} onClick={() => handleSort('updated_at')}>
              Güncelleme {renderSortIcon('updated_at')}
            </span>
            <span className="sp-library__col" style={{ flex: '0 0 40px', textAlign: 'right' }}></span>
          </div>
          {displayProducts.map(p => {
            const statusCfg = STATUS_CONFIG[p.status] || STATUS_CONFIG.BEKLEMEDE;
            return (
              <div key={p.id} className="sp-library__row">
                <span className="sp-library__col sp-library__col--name" data-label="Ürün">
                  <a href={p.original_link} target="_blank" rel="noopener noreferrer" className="sp-library__product-link">
                    <span className="truncate">{p.name}</span>
                    <ExternalLink size={11} />
                  </a>
                </span>
                <span className="sp-library__col sp-library__col--cat" data-label="Kategori">{p.category}</span>
                <span className="sp-library__col sp-library__col--price font-mono" data-label="Fiyat">
                  {p.current_price ? formatPrice(p.current_price) : '—'}
                </span>
                <span className="sp-library__col sp-library__col--seller" data-label="Satıcı">{p.current_seller || '—'}</span>
                <span className="sp-library__col sp-library__col--status" data-label="Durum">
                  <span style={{ color: statusCfg.color, background: statusCfg.bg, fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: 'var(--radius-full)' }}>
                    {statusCfg.label}
                  </span>
                </span>
                <span className="sp-library__col sp-library__col--updated" data-label="Güncelleme">
                  {formatRelativeTime(p.updated_at)}
                </span>
                <span className="sp-library__col" style={{ flex: '0 0 70px', textAlign: 'right', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  <button 
                    onClick={() => handleScanSingle(p.id)}
                    className="sp-library__scan-btn"
                    title="Güncelle"
                  >
                    {scanningIds.has(p.id) ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                  </button>
                  <button
                    className={`sp-library__scan-btn ${confirmDeleteId === p.id ? 'sp-library__scan-btn--confirm' : ''}`}
                    style={confirmDeleteId === p.id ? { color: 'var(--color-danger)' } : {}}
                    onClick={() => handleDelete(p.id)}
                    title={confirmDeleteId === p.id ? 'Silmeyi Onayla' : 'Kütüphaneden Sil'}
                  >
                    <Trash2 size={14} />
                  </button>
                </span>
              </div>
            );
          })}
        </div>
        );
      })()}
    </div>
  );
}

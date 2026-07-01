import './LibraryPage.css';
import { useState, useEffect } from 'react';
import { getLibraryProducts, getLibraryCategories, scanAllLibraryProducts, scanLibraryProduct, deleteLibraryProduct, addLibraryProduct } from '../../api/client';
import { formatPrice, formatRelativeTime } from '../../utils/formatPrice';
import { STATUS_CONFIG } from '../../utils/constants';
import { ExternalLink, RefreshCw, Loader2, Search, ArrowUp, ArrowDown, Trash2, Plus } from 'lucide-react';
import Button from '../ui/Button';
import { useToast } from '../../context/ToastContext';
import SignalBadge from '../products/SignalBadge';

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
      const newProducts = Array.isArray(data) ? data : [];
      
      setProducts(prev => {
        // Push Intelligence: Compare prev and new for BUY signals
        if (prev.length > 0) {
          const prevMap = new Map(prev.map(p => [p.id, p]));
          const buyTransitions = [];
          
          for (const np of newProducts) {
            const op = prevMap.get(np.id);
            if (op && op.decision_signal !== 'BUY' && np.decision_signal === 'BUY') {
              buyTransitions.push(np);
            }
          }
          
          if (buyTransitions.length > 0) {
            toast.success(`Akıllı Uyarı: Portföyünüzdeki ${buyTransitions.length} ürün BUY (AL) seviyesine girdi! 🚀`);
          }
        }
        return newProducts;
      });
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
              style={{ padding: '8px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)', color: 'var(--color-text-primary)', fontSize: '13px', width: '200px' }}
            />
            <Button type="submit" loading={isAddingProduct} icon={Plus}>
              Ekle
            </Button>
          </form>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              placeholder="Ürün ara..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ padding: '8px 12px 8px 36px', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)', color: 'var(--color-text-primary)', fontSize: '13px', width: '180px' }}
            />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            <input 
              type="checkbox" 
              checked={groupDuplicates} 
              onChange={e => setGroupDuplicates(e.target.checked)} 
              style={{ accentColor: 'var(--color-primary)' }}
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
          <div className="sp-library__asset-grid" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '16px',
            marginTop: '16px'
          }}>
            {displayProducts.map(p => {
              const statusCfg = STATUS_CONFIG[p.status] || STATUS_CONFIG.BEKLEMEDE;
              return (
                <div key={p.id} className="sp-library__asset-card" style={{
                  background: 'var(--color-bg-surface)',
                  borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--color-border)',
                  boxShadow: 'var(--shadow-sm)',
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  height: '100%',
                  gap: '16px',
                  position: 'relative',
                  overflow: 'hidden',
                  transition: 'all var(--transition-base)'
                }}>
                  {/* Decorative background glow based on signal */}
                  {p.decision_signal === 'BUY' && <div style={{ position: 'absolute', top: -20, right: -20, width: 80, height: 80, background: 'var(--color-success)', filter: 'blur(40px)', opacity: 0.15, borderRadius: '50%' }} />}
                  {p.decision_signal === 'AVOID' && <div style={{ position: 'absolute', top: -20, right: -20, width: 80, height: 80, background: 'var(--color-danger)', filter: 'blur(40px)', opacity: 0.15, borderRadius: '50%' }} />}

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--color-text-muted)', letterSpacing: '0.05em', marginBottom: '4px' }}>
                        {p.ticker || 'UNK-000'}
                      </div>
                      <a href={p.original_link} target="_blank" rel="noopener noreferrer" style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--color-text-primary)', textDecoration: 'none', lineHeight: '1.4' }}>
                        <span className="truncate" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', whiteSpace: 'normal' }}>{p.name}</span>
                      </a>
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 'auto' }}>
                    <div>
                      <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>
                        {p.current_price ? formatPrice(p.current_price) : '—'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                        {p.current_seller || 'Bilinmiyor'} • {formatRelativeTime(p.updated_at)}
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', maxWidth: '60%' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <SignalBadge signal={p.decision_signal} valueScore={p.value_score} />
                        {p.performance_score != null && (
                          <span
                            title={p.benchmark_match_name ? `Referans: ${p.benchmark_match_name} (PassMark tahmini)` : undefined}
                            style={{
                              fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: 'var(--radius-full)',
                              background: 'var(--color-secondary-muted)', color: 'var(--color-secondary)', cursor: 'help',
                            }}
                          >
                            {Math.round(p.performance_score)}/100
                          </span>
                        )}
                        <div style={{ display: 'flex', gap: '4px' }}>
                          <button 
                            onClick={() => handleScanSingle(p.id)}
                            style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', padding: '4px' }}
                            title="Güncelle"
                          >
                            {scanningIds.has(p.id) ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                          </button>
                          <button
                            style={{ background: 'none', border: 'none', color: confirmDeleteId === p.id ? 'var(--color-danger)' : 'var(--color-text-muted)', cursor: 'pointer', padding: '4px' }}
                            onClick={() => handleDelete(p.id)}
                            title={confirmDeleteId === p.id ? 'Silmeyi Onayla' : 'Sil'}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      {p.decision_reasoning && (
                        <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', textAlign: 'right', lineHeight: '1.3', fontStyle: 'italic' }}>
                          {p.decision_reasoning}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
}

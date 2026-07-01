import './LibraryPage.css';
import { useState, useEffect, useMemo } from 'react';
import { getLibraryProducts, scanAllLibraryProducts, scanLibraryProduct, deleteLibraryProduct, addLibraryProduct } from '../../api/client';
import { formatPrice, formatRelativeTime } from '../../utils/formatPrice';
import { stringSimilarity } from '../../utils/similarity';
import { RefreshCw, Loader2, Search, ArrowUp, ArrowDown, Trash2, Plus } from 'lucide-react';
import Button from '../ui/Button';
import { useToast } from '../../context/ToastContext';
import SignalBadge from '../products/SignalBadge';
import ScoreRing from '../ui/ScoreRing';

const DEDUP_SIMILARITY_THRESHOLD = 0.93;

// Tam string eşleşmesi yerine bulanık (fuzzy) benzerlik: "bir harf farklı"
// gibi küçük yazım farkları da aynı ürün olarak gruplanır. Aynı satıcıdan
// birden fazla eşleşmede en ucuz varyant tutulur.
function dedupeProducts(list) {
  const groups = [];
  for (const p of list) {
    const name = (p.name || '').trim();
    const existing = groups.find(g => stringSimilarity(name, g.name) >= DEDUP_SIMILARITY_THRESHOLD);
    if (!existing) {
      groups.push({ name, product: p });
    } else {
      const currentPrice = existing.product.current_price || Infinity;
      const newPrice = p.current_price || Infinity;
      if (newPrice < currentPrice) {
        existing.product = p;
      }
    }
  }
  return groups.map(g => g.product);
}

export default function LibraryPage() {
  const [category, setCategory] = useState('');
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
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
    loadProducts();
  }, []);

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
      const data = await getLibraryProducts();
      const newProducts = Array.isArray(data) ? data : [];
      setLoadError(false);

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
            toast.success(`Akıllı Uyarı: Setlerinizdeki ${buyTransitions.length} ürün BUY (AL) seviyesine girdi! 🚀`);
          }
        }
        return newProducts;
      });
    } catch (err) {
      console.error('Kütüphane ürünleri yüklenemedi:', err);
      setProducts([]);
      setLoadError(true);
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

  // Kategori pillerinin sayıları — "Tekilleştir" açıkken tekilleştirilmiş
  // sayıyı gösterir, kapalıyken ham sayıyı.
  const { categoryList, totalCount } = useMemo(() => {
    const list = Array.isArray(products) ? products : [];
    const base = groupDuplicates ? dedupeProducts(list) : list;
    const counts = {};
    for (const p of base) {
      const cat = p.category || 'Diğer';
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return {
      categoryList: Object.keys(counts).sort().map(name => ({ name, count: counts[name] })),
      totalCount: base.length,
    };
  }, [products, groupDuplicates]);

  return (
    <div className="sp-library animate-fade-in">
      <div className="sp-library__header">
        <div>
          <h1 className="sp-library__title">Ürün Kütüphanesi</h1>
          <p className="sp-library__subtitle">Daha önce eklediğiniz tüm ürünler burada listelenir</p>
        </div>
        <div className="sp-library__controls">
          <form onSubmit={handleAddProduct} className="sp-library__add-form">
            <input
              type="url"
              placeholder="Ürün linki yapıştır..."
              value={newProductLink}
              onChange={e => setNewProductLink(e.target.value)}
              required
              disabled={isAddingProduct}
              className="sp-login__input sp-library__add-input"
            />
            <Button type="submit" loading={isAddingProduct} icon={Plus}>
              Ekle
            </Button>
          </form>
          <div className="sp-library__search">
            <Search size={16} className="sp-library__search-icon" />
            <input
              type="text"
              placeholder="Ürün ara..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="sp-login__input sp-library__search-input"
            />
          </div>
          <label className="sp-library__dedupe">
            <input
              type="checkbox"
              checked={groupDuplicates}
              onChange={e => setGroupDuplicates(e.target.checked)}
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
          Tümü <span className="sp-library__filter-count">({totalCount})</span>
        </button>
        {categoryList.map(cat => (
          <button
            key={cat.name}
            className={`sp-library__filter-btn ${category === cat.name ? 'sp-library__filter-btn--active' : ''}`}
            onClick={() => setCategory(prev => prev === cat.name ? '' : cat.name)}
          >
            {cat.name} <span className="sp-library__filter-count">({cat.count})</span>
          </button>
        ))}
      </div>

      {/* Products table */}
      {(() => {
        let displayProducts = Array.isArray(products) ? products : [];
        if (category) {
          displayProducts = displayProducts.filter(p => (p.category || 'Diğer') === category);
        }
        if (groupDuplicates) {
          displayProducts = dedupeProducts(displayProducts);
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

        if (loadError) {
          return (
            <div className="sp-library__empty sp-library__empty--error">
              Ürünler yüklenirken bir sorun oluştu.
              <Button variant="secondary" size="sm" icon={RefreshCw} onClick={() => loadProducts()}>
                Tekrar Dene
              </Button>
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
          <div className="sp-library__asset-grid">
            {displayProducts.map(p => {
              return (
                <div key={p.id} className="sp-library__asset-card">
                  {p.decision_signal === 'BUY' && <div className="sp-library__asset-glow sp-library__asset-glow--buy" />}
                  {p.decision_signal === 'AVOID' && <div className="sp-library__asset-glow sp-library__asset-glow--avoid" />}

                  <div className="sp-library__asset-top">
                    <div className="sp-library__asset-ticker">
                      {p.ticker || 'UNK-000'}
                    </div>
                    <a href={p.original_link} target="_blank" rel="noopener noreferrer" className="sp-library__asset-name">
                      <span className="truncate sp-library__asset-name-clamp">{p.name}</span>
                    </a>
                  </div>

                  <div className="sp-library__asset-bottom">
                    <div>
                      <div className="sp-library__asset-price font-mono">
                        {p.current_price ? formatPrice(p.current_price) : '—'}
                      </div>
                      <div className="sp-library__asset-meta">
                        {p.current_seller || 'Bilinmiyor'} • {formatRelativeTime(p.updated_at)}
                      </div>
                    </div>

                    <div className="sp-library__asset-side">
                      <div className="sp-library__asset-badges">
                        <SignalBadge signal={p.decision_signal} valueScore={p.value_score} />
                        <ScoreRing
                          value={p.value_score}
                          size={26}
                          strokeWidth={3}
                          showValue={false}
                          title={`Değer Skoru: ${p.value_score != null ? Math.round(p.value_score) : 'N/A'}/100`}
                        />
                        {p.performance_score != null && (
                          <span
                            className="sp-library__perf-badge font-mono"
                            title={p.benchmark_match_name ? `Referans: ${p.benchmark_match_name} (PassMark tahmini)` : undefined}
                          >
                            {Math.round(p.performance_score)}/100
                          </span>
                        )}
                        <div className="sp-library__asset-actions">
                          <button
                            onClick={() => handleScanSingle(p.id)}
                            className="sp-library__icon-btn"
                            title="Güncelle"
                          >
                            {scanningIds.has(p.id) ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                          </button>
                          <button
                            className={`sp-library__icon-btn ${confirmDeleteId === p.id ? 'sp-library__icon-btn--danger' : ''}`}
                            onClick={() => handleDelete(p.id)}
                            title={confirmDeleteId === p.id ? 'Silmeyi Onayla' : 'Sil'}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      {p.decision_reasoning && (
                        <div className="sp-library__asset-reasoning">
                          {p.decision_reasoning}
                          {p.ai_decision_updated_at && (
                            <span className="sp-library__asset-reasoning-time"> · {formatRelativeTime(p.ai_decision_updated_at)}</span>
                          )}
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

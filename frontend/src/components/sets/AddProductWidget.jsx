import './AddProductWidget.css';
import { useState, useEffect } from 'react';
import { Link2, Library, Loader2 } from 'lucide-react';
import { getLibraryProducts, getLibraryCategories } from '../../api/client';
import Button from '../ui/Button';

export default function AddProductWidget({ onAdd, categories: setCategoryOptions = [] }) {
  const [mode, setMode] = useState('link'); // 'link' | 'library'
  const [link, setLink] = useState('');
  const [loading, setLoading] = useState(false);
  const [linkCategory, setLinkCategory] = useState('');
  const [category, setCategory] = useState('İşlemci');
  const [libraryProductsRaw, setLibraryProductsRaw] = useState([]);
  const [libraryProducts, setLibraryProducts] = useState([]);
  const [selectedLibId, setSelectedLibId] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [libLoading, setLibLoading] = useState(false);
  const [categories, setCategories] = useState(['İşlemci']);

  useEffect(() => {
    getLibraryCategories().then(data => {
      if (data && data.length > 0) {
        setCategories(data);
        setCategory(typeof data[0] === 'string' ? data[0] : data[0].name);
      }
    }).catch(err => {
      console.error('Kategoriler yüklenirken hata:', err);
    });
  }, []);

  const loadLibrary = async (cat) => {
    setLibLoading(true);
    try {
      const data = await getLibraryProducts(cat);
      setLibraryProductsRaw(data);
      
      const groupDuplicates = localStorage.getItem('sp_group_dupes') !== 'false';
      let displayProducts = Array.isArray(data) ? data : [];
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
      setLibraryProducts(displayProducts);
      
      if (displayProducts.length > 0) setSelectedLibId(displayProducts[0].id.toString());
      else setSelectedLibId('');
    } catch (err) {
      console.error(err);
      setLibraryProductsRaw([]);
      setLibraryProducts([]);
    } finally {
      setLibLoading(false);
    }
  };

  const handleCategoryChange = (cat) => {
    setCategory(cat);
    if (mode === 'library') loadLibrary(cat);
  };

  const handleModeChange = (newMode) => {
    setMode(newMode);
    if (newMode === 'library') loadLibrary(category);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === 'link') {
        if (!link.trim()) return;
        await onAdd({ originalLink: link.trim(), category: linkCategory || undefined });
        setLink('');
        setLinkCategory('');
      } else {
        if (!selectedLibId) return;
        await onAdd({ libraryProductId: parseInt(selectedLibId) });
        setSearchTerm('');
        setSelectedLibId('');
      }
    } catch (err) {
      console.error('Ürün eklenirken hata:', err);
      // Error handled by parent
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sp-addwidget">
      <div className="sp-addwidget__header">
        <h4 className="sp-addwidget__title">Ürün Ekle</h4>
        <div className="sp-addwidget__mode-toggle">
          <button
            className={`sp-addwidget__mode-btn ${mode === 'link' ? 'sp-addwidget__mode-btn--active' : ''}`}
            onClick={() => handleModeChange('link')}
          >
            <Link2 size={14} />
            Link ile Ekle
          </button>
          <button
            className={`sp-addwidget__mode-btn ${mode === 'library' ? 'sp-addwidget__mode-btn--active' : ''}`}
            onClick={() => handleModeChange('library')}
          >
            <Library size={14} />
            Kütüphaneden
          </button>
        </div>
      </div>

      <form className="sp-addwidget__form" onSubmit={handleSubmit}>
        {mode === 'library' && (
          <div className="sp-addwidget__categories">
            {Array.isArray(categories) && categories.slice(0, 15).map(cat => {
              const catName = typeof cat === 'string' ? cat : cat.name;
              return (
                <button
                  key={catName}
                  type="button"
                  className={`sp-addwidget__cat-btn ${category === catName ? 'sp-addwidget__cat-btn--active' : ''}`}
                  onClick={() => handleCategoryChange(catName)}
                >
                  {catName}
                </button>
              );
            })}
          </div>
        )}

        <div className="sp-addwidget__input-row">
          {mode === 'link' ? (
            <>
              <input
                type="url"
                className="sp-addwidget__input"
                placeholder="Ürün linkini yapıştırın (Amazon, Hepsiburada, Trendyol, n11...)"
                value={link}
                onChange={e => setLink(e.target.value)}
                disabled={loading}
                required
              />
              {setCategoryOptions.length > 0 && (
                <select
                  value={linkCategory}
                  onChange={e => setLinkCategory(e.target.value)}
                  disabled={loading}
                  title="Kategori (boş bırakılırsa otomatik tahmin edilir)"
                  style={{
                    padding: '8px 10px', borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)', background: 'var(--color-bg-elevated)',
                    color: 'var(--color-text-primary)', fontSize: '13px', maxWidth: '160px',
                  }}
                >
                  <option value="">Kategori (otomatik)</option>
                  {setCategoryOptions.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              )}
            </>
          ) : (
            <div className="sp-addwidget__combo-wrapper" style={{ position: 'relative', flex: 1 }}>
              <input
                type="text"
                className="sp-addwidget__input"
                placeholder={libLoading ? 'Yükleniyor...' : libraryProducts.length === 0 ? 'Bu kategoride ürün yok' : 'Ürün ara veya seç...'}
                value={searchTerm}
                onChange={e => {
                  setSearchTerm(e.target.value);
                  setIsDropdownOpen(true);
                  if (selectedLibId) setSelectedLibId(''); // Reset selection when typing
                }}
                onFocus={() => setIsDropdownOpen(true)}
                onBlur={() => setTimeout(() => setIsDropdownOpen(false), 200)}
                disabled={loading || libLoading || libraryProducts.length === 0}
              />
              {isDropdownOpen && libraryProducts.length > 0 && (
                <div className="sp-addwidget__dropdown" style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, 
                  background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', 
                  borderRadius: 'var(--radius-md)', marginTop: '4px', maxHeight: '200px', 
                  overflowY: 'auto', zIndex: 10, boxShadow: 'var(--shadow-md)'
                }}>
                  {libraryProducts
                    .filter(p => (p.name || '').toLowerCase().includes(searchTerm.toLowerCase()))
                    .map(lp => (
                      <div 
                        key={lp.id}
                        className="sp-addwidget__dropdown-item"
                        style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--color-border)', fontSize: '13px' }}
                        onMouseDown={() => {
                          setSelectedLibId(lp.id.toString());
                          setSearchTerm(`${lp.name} ${lp.current_price ? `(${lp.current_price.toLocaleString('tr-TR')} ₺)` : ''}`);
                          setIsDropdownOpen(false);
                        }}
                      >
                        <div style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{lp.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                          {lp.current_seller || 'Bilinmiyor'} • {lp.current_price ? `${lp.current_price.toLocaleString('tr-TR')} ₺` : 'Fiyat Yok'}
                        </div>
                      </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <Button type="submit" loading={loading} disabled={loading || (mode === 'library' && !selectedLibId)}>
            {loading ? 'Ekleniyor...' : 'Ekle'}
          </Button>
        </div>
      </form>
    </div>
  );
}

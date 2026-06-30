import './CategoryGroup.css';
import ProductCard from './ProductCard';
import { formatPrice } from '../../utils/formatPrice';

export default function CategoryGroup({ category, products, onToggleActive, onToggleLock, onUpdateLockedPrice, onDelete, onSelectProduct }) {
  const subtotal = products.filter(p => p.is_active).reduce((sum, p) => sum + (p.current_price || p.locked_price || 0), 0);

  return (
    <div className="sp-catgroup">
      <div className="sp-catgroup__header">
        <div className="sp-catgroup__title-area">
          <h3 className="sp-catgroup__title">{category}</h3>
          <span className="sp-catgroup__count">{products.length}</span>
        </div>
        <span className="sp-catgroup__subtotal font-mono">{formatPrice(subtotal)}</span>
      </div>
      <div className="sp-catgroup__list">
        {products.map(product => (
          <ProductCard
            key={product.id}
            product={product}
            onToggleActive={() => onToggleActive(product)}
            onToggleLock={() => onToggleLock(product)}
            onUpdateLockedPrice={(newPrice) => onUpdateLockedPrice(product, newPrice)}
            onDelete={() => onDelete(product.id)}
            onClick={() => onSelectProduct(product)}
          />
        ))}
      </div>
    </div>
  );
}

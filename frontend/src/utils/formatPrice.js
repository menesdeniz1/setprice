/**
 * Format a price number to Turkish locale string
 */
export function formatPrice(price, showCurrency = true) {
  if (price == null || isNaN(price)) return '—';
  const formatted = price.toLocaleString('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return showCurrency ? `${formatted} ₺` : formatted;
}

/**
 * Format a compact price (no decimals for large numbers)
 */
export function formatPriceCompact(price) {
  if (price == null || isNaN(price)) return '—';
  if (price >= 1000) {
    return `${(price / 1000).toFixed(price % 1000 === 0 ? 0 : 1)}K ₺`;
  }
  return formatPrice(price);
}

/**
 * Calculate percentage
 */
export function calcPercent(value, total) {
  if (!total || total === 0) return 0;
  return (value / total) * 100;
}

/**
 * Format a date to Turkish locale
 */
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format relative time (e.g., "2 saat önce")
 */
export function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMin < 1) return 'Az önce';
  if (diffMin < 60) return `${diffMin} dk önce`;
  if (diffHour < 24) return `${diffHour} saat önce`;
  if (diffDay < 30) return `${diffDay} gün önce`;
  return formatDate(dateStr);
}

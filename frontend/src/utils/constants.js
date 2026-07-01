import { Target, ArrowRightLeft, AlertTriangle, TrendingDown } from 'lucide-react';

export const CATEGORIES = [
  'İşlemci',
  'Anakart',
  'Ekran Kartı',
  'RAM',
  'SSD',
  'Güç Kaynağı',
  'Kasa',
  'Soğutma',
  'Monitör',
  'Kulaklık',
  'Mouse',
  'Klavye',
  'Diğer',
];

export const CATEGORY_ICONS = {
  'İşlemci': 'Cpu',
  'Anakart': 'CircuitBoard',
  'Ekran Kartı': 'Monitor',
  'RAM': 'MemoryStick',
  'SSD': 'HardDrive',
  'Güç Kaynağı': 'Zap',
  'Kasa': 'Box',
  'Soğutma': 'Fan',
  'Monitör': 'MonitorSmartphone',
  'Kulaklık': 'Headphones',
  'Mouse': 'Mouse',
  'Klavye': 'Keyboard',
  'Diğer': 'Package',
};

export const STATUS_CONFIG = {
  OK: { label: 'OK', color: 'var(--color-success)', bg: 'var(--color-success-muted)' },
  FAILED: { label: 'HATA', color: 'var(--color-danger)', bg: 'var(--color-danger-muted)' },
  FLAGGED: { label: 'DİKKAT', color: 'var(--color-warning)', bg: 'var(--color-warning-muted)' },
  STALE: { label: 'ESKİ', color: 'var(--color-text-muted)', bg: 'var(--color-bg-elevated)' },
  BEKLEMEDE: { label: 'BEKLEMEDE', color: 'var(--color-text-muted)', bg: 'var(--color-bg-elevated)' },
};

export const ALERT_TYPE_CONFIG = {
  THRESHOLD: { icon: Target, label: 'Hedef Fiyat', color: 'var(--color-signal-wait)', bg: 'var(--color-signal-wait-muted)' },
  SIGNAL_CHANGE: { icon: ArrowRightLeft, label: 'Sinyal Değişimi', color: 'var(--color-brand-accent)', bg: 'var(--color-brand-accent-muted)' },
  BULL_TRAP: { icon: AlertTriangle, label: 'Yanıltıcı Düşüş', color: 'var(--color-signal-avoid)', bg: 'var(--color-signal-avoid-muted)' },
  TREND_DIP: { icon: TrendingDown, label: 'Fiyat Düşüşü', color: 'var(--color-signal-buy)', bg: 'var(--color-signal-buy-muted)' },
};

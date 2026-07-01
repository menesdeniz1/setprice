import React from 'react';
import { Zap, AlertTriangle, TrendingDown, Clock } from 'lucide-react';

const SignalBadge = ({ signal, valueScore }) => {
  let config = {
    color: 'var(--color-text-secondary)',
    bg: 'var(--color-bg-surface-hover)',
    border: 'var(--color-border-subtle)',
    shadow: 'none',
    text: 'YENİ ÜRÜN',
    Icon: Clock
  };

  if (signal === 'BUY') {
    config = {
      color: 'var(--color-success)',
      bg: 'var(--color-success-muted)',
      border: 'var(--color-success)',
      shadow: 'var(--shadow-glow-success)',
      text: 'ALIM FIRSATI',
      Icon: Zap
    };
  } else if (signal === 'AVOID') {
    config = {
      color: 'var(--color-danger)',
      bg: 'var(--color-danger-muted)',
      border: 'var(--color-danger)',
      shadow: 'var(--shadow-glow-danger)',
      text: 'UZAK DUR',
      Icon: AlertTriangle
    };
  } else if (signal === 'WAIT') {
    config = {
      color: 'var(--color-warning)',
      bg: 'var(--color-warning-muted)',
      border: 'var(--color-warning)',
      shadow: 'none',
      text: 'BEKLE',
      Icon: TrendingDown
    };
  }

  return (
    <div 
      className="signal-badge" 
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 12px',
        borderRadius: 'var(--radius-full)',
        backgroundColor: config.bg,
        color: config.color,
        border: `1px solid ${config.border}40`, /* 25% opacity border */
        boxShadow: config.shadow,
        fontWeight: '700',
        fontSize: '0.75rem',
        letterSpacing: '0.05em',
        cursor: 'help',
        transition: 'all var(--transition-fast)'
      }}
      title={`Değer Skoru: ${valueScore ? valueScore.toFixed(0) : 'N/A'}/100`}
    >
      <config.Icon size={14} strokeWidth={2.5} />
      <span>{config.text}</span>
    </div>
  );
};

export default SignalBadge;

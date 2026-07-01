import React from 'react';
import { Zap, AlertTriangle, TrendingDown, Clock } from 'lucide-react';
import './SignalBadge.css';

const SIGNAL_CONFIG = {
  BUY: { modifier: 'buy', text: 'ALIM FIRSATI', Icon: Zap },
  AVOID: { modifier: 'avoid', text: 'UZAK DUR', Icon: AlertTriangle },
  WAIT: { modifier: 'wait', text: 'BEKLE', Icon: TrendingDown },
};

const SignalBadge = ({ signal, valueScore }) => {
  const { modifier, text, Icon } = SIGNAL_CONFIG[signal] || { modifier: 'new', text: 'YENİ ÜRÜN', Icon: Clock };

  return (
    <div
      className={`sp-signal-badge sp-signal-badge--${modifier}`}
      title={`Değer Skoru: ${valueScore ? valueScore.toFixed(0) : 'N/A'}/100`}
    >
      <Icon size={14} strokeWidth={2.5} />
      <span>{text}</span>
    </div>
  );
};

export default SignalBadge;

import './ScoreRing.css';

function scoreColor(value) {
  if (value >= 70) return 'var(--color-signal-buy)';
  if (value >= 40) return 'var(--color-signal-wait)';
  return 'var(--color-signal-avoid)';
}

export default function ScoreRing({ value, size = 56, strokeWidth = 5, showValue = true, title }) {
  const hasValue = value !== null && value !== undefined;
  const clamped = hasValue ? Math.max(0, Math.min(100, value)) : 0;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);
  const color = hasValue ? scoreColor(clamped) : 'var(--color-text-muted)';

  return (
    <div
      className="sp-score-ring"
      style={{ width: size, height: size }}
      title={title ?? (hasValue ? `Skor: ${Math.round(clamped)}/100` : 'Skor yok')}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={strokeWidth}
        />
        {hasValue && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            className="sp-score-ring__arc"
          />
        )}
      </svg>
      {showValue && (
        <span className="sp-score-ring__value font-mono" style={{ color, fontSize: size / 3.2 }}>
          {hasValue ? Math.round(clamped) : '—'}
        </span>
      )}
    </div>
  );
}

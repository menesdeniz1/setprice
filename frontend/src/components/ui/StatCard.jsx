import './StatCard.css';

export default function StatCard({ icon: Icon, label, value, accentColor, valueColor, mono = false }) {
  return (
    <div className={`sp-stat-card ${Icon ? 'sp-stat-card--icon' : ''}`} style={accentColor ? { borderLeft: `4px solid ${accentColor}` } : undefined}>
      {Icon && (
        <div className="sp-stat-card__icon" style={{ background: accentColor, color: 'white' }}>
          <Icon size={20} />
        </div>
      )}
      <div className="sp-stat-card__info">
        <span className={`sp-stat-card__value ${mono ? 'font-mono' : ''}`} style={valueColor ? { color: valueColor } : undefined}>
          {value}
        </span>
        <span className="sp-stat-card__label">{label}</span>
      </div>
    </div>
  );
}

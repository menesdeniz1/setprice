import './SegmentedToggle.css';

export default function SegmentedToggle({ options, value, onChange, size = 'md' }) {
  return (
    <div className={`sp-segmented sp-segmented--${size}`} role="tablist">
      {options.map(opt => (
        <button
          key={opt.value}
          type="button"
          role="tab"
          aria-selected={value === opt.value}
          className={`sp-segmented__option ${value === opt.value ? 'sp-segmented__option--active' : ''}`}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

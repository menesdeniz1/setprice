import './Button.css';

/**
 * Reusable button component with multiple variants
 * @param {'primary'|'secondary'|'ghost'|'danger'|'success'} variant
 * @param {'sm'|'md'|'lg'} size
 */
export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  loading = false,
  disabled = false,
  fullWidth = false,
  className = '',
  ...props
}) {
  return (
    <button
      className={`sp-btn sp-btn--${variant} sp-btn--${size} ${fullWidth ? 'sp-btn--full' : ''} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="sp-btn__spinner" />
      ) : Icon ? (
        <Icon size={size === 'sm' ? 14 : 16} />
      ) : null}
      {children && <span>{children}</span>}
    </button>
  );
}

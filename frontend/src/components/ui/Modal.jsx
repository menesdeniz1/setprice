import './Modal.css';
import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

/**
 * Accessible modal dialog with backdrop blur
 */
export default function Modal({ isOpen, onClose, title, children, maxWidth = '520px' }) {
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="sp-modal-overlay animate-fade-in"
      ref={overlayRef}
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div className="sp-modal animate-scale-in" style={{ maxWidth }}>
        <div className="sp-modal__header">
          <h2 className="sp-modal__title">{title}</h2>
          <button className="sp-modal__close" onClick={onClose} aria-label="Kapat">
            <X size={18} />
          </button>
        </div>
        <div className="sp-modal__body">
          {children}
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Zap, ArrowRight, Eye, EyeOff } from 'lucide-react';
import Button from '../ui/Button';
import './LoginPage.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const { login, register } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    if (password.length < 6) {
      toast.error('Şifre en az 6 karakter olmalıdır');
      setLoading(false);
      return;
    }
    
    try {
      if (isRegister) {
        await register(email, password);
        toast.success('Hesap oluşturuldu! Hoş geldiniz.');
      } else {
        await login(email, password);
        toast.success('Giriş başarılı!');
      }
      navigate('/');
    } catch (err) {
      toast.error(err.message || 'Giriş başarısız');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sp-login">
      {/* Background decoration */}
      <div className="sp-login__bg">
        <div className="sp-login__orb sp-login__orb--1" />
        <div className="sp-login__orb sp-login__orb--2" />
        <div className="sp-login__orb sp-login__orb--3" />
      </div>

      <div className="sp-login__container animate-fade-in-up">
        {/* Header */}
        <div className="sp-login__header">
          <div className="sp-login__logo-icon">
            <Zap size={28} />
          </div>
          <h1 className="sp-login__title">
            <span className="text-gradient">SetPrice</span>
          </h1>
          <p className="sp-login__subtitle">
            Bilgisayar parçaları için akıllı fiyat takip & bütçe yönetim platformu
          </p>
        </div>

        {/* Form */}
        <form className="sp-login__form" onSubmit={handleSubmit}>
          <div className="sp-login__field">
            <label className="sp-login__label" htmlFor="login-email">E-Posta Adresi</label>
            <input
              id="login-email"
              type="email"
              className="sp-login__input"
              placeholder="ornek@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="sp-login__field">
            <label className="sp-login__label" htmlFor="login-password">Şifre</label>
            <div style={{ position: 'relative' }}>
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                className="sp-login__input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                style={{ paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '4px'
                }}
                title={showPassword ? 'Şifreyi Gizle' : 'Şifreyi Göster'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <Button type="submit" fullWidth loading={loading} icon={ArrowRight}>
            {isRegister ? 'Hesap Oluştur' : 'Giriş Yap'}
          </Button>
        </form>

        {/* Toggle */}
        <div className="sp-login__toggle">
          <span className="sp-login__toggle-text">
            {isRegister ? 'Zaten hesabın var mı?' : 'Hesabın yok mu?'}
          </span>
          <button
            type="button"
            className="sp-login__toggle-btn"
            onClick={() => setIsRegister(!isRegister)}
          >
            {isRegister ? 'Giriş Yap' : 'Kayıt Ol'}
          </button>
        </div>

        {/* Demo hint */}
        <div className="sp-login__demo">
          Demo için önce Kayıt Ol'a tıklayıp yeni bir hesap oluşturun.
        </div>
      </div>
    </div>
  );
}

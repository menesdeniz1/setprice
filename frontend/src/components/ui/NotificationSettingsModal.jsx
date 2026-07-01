import { useState } from 'react';
import { Send } from 'lucide-react';
import { updateTelegramSettings, sendTelegramTest } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import Modal from './Modal';
import Button from './Button';

export default function NotificationSettingsModal({ isOpen, onClose, user, onUserUpdate }) {
  const [chatId, setChatId] = useState(user?.telegram_chat_id || '');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const toast = useToast();

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateTelegramSettings(chatId.trim() || null);
      onUserUpdate?.(updated);
      toast.success('Telegram ayarları kaydedildi');
    } catch (err) {
      toast.error('Kaydedilemedi: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      await sendTelegramTest();
      toast.success('Test mesajı gönderildi, Telegram\'ı kontrol edin!');
    } catch (err) {
      toast.error(err.message || 'Test mesajı gönderilemedi');
    } finally {
      setTesting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Bildirim Ayarları (Telegram)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
          <strong style={{ color: 'var(--color-text-primary)' }}>Kurulum:</strong>
          <ol style={{ margin: '8px 0 0', paddingLeft: '20px' }}>
            <li>Telegram'da <strong>@BotFather</strong>'a mesaj at, <code>/newbot</code> ile bir bot oluştur.</li>
            <li>Oluşturduğun bota Telegram'dan bir mesaj gönder (ör. "Merhaba").</li>
            <li>Chat ID'ni öğrenmek için <strong>@userinfobot</strong>'a mesaj at, sana ID'ni gösterecek.</li>
            <li>Aşağıya o Chat ID'yi gir ve kaydet.</li>
          </ol>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <label style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
            Telegram Chat ID
          </label>
          <input
            type="text"
            className="sp-login__input"
            placeholder="Örn: 123456789"
            value={chatId}
            onChange={e => setChatId(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button onClick={handleSave} loading={saving} fullWidth>Kaydet</Button>
          <Button onClick={handleTest} loading={testing} variant="secondary" icon={Send} disabled={!user?.telegram_chat_id}>
            Test Gönder
          </Button>
        </div>
      </div>
    </Modal>
  );
}

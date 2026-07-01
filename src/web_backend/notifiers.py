# -*- coding: utf-8 -*-
"""
Pluggable bildirim kanalları. Her kanal aynı arayüzü uygular (Notifier),
böylece ileride e-posta/başka kanal eklemek crud.py'de tek satır değişikliği
gerektirir. Şu an sadece Telegram var (kullanıcı tercihi — bkz. ROADMAP.md Faz 4).

Telegram Bot API basit bir REST çağrısıdır (dokümante, kararlı), bu yüzden
diğer scraping-bazlı entegrasyonların aksine (PassMark vb.) canlı doğrulama
gerektirmeden güvenle yazılabilir: https://core.telegram.org/bots/api#sendmessage
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

logger = logging.getLogger("setprice.notifiers")

TELEGRAM_API_BASE = "https://api.telegram.org"


class Notifier(ABC):
    @abstractmethod
    def send(self, user, title: str, message: str) -> bool:
        """Bildirimi gönderir. Kullanıcı bu kanalı yapılandırmamışsa ya da
        gönderim başarısızsa False döner — çağıran taraf bunu asla exception
        olarak beklememeli (bildirim gönderimi ana akışı bloklamamalı)."""
        raise NotImplementedError


class TelegramNotifier(Notifier):
    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    def is_configured(self) -> bool:
        return bool(self.bot_token)

    def send(self, user, title: str, message: str) -> bool:
        if not self.bot_token:
            return False
        chat_id = getattr(user, "telegram_chat_id", None)
        if not chat_id:
            return False
        try:
            text = f"*{title}*\n{message}"
            resp = requests.post(
                f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"[Telegram] Gönderim başarısız ({resp.status_code}): {resp.text[:200]}")
                return False
            return True
        except Exception as e:
            logger.warning(f"[Telegram] Gönderim hatası: {e}")
            return False


def get_active_notifiers():
    """Ortam değişkeni ile aktif edilmiş kanalları döner."""
    notifiers = []
    telegram = TelegramNotifier()
    if telegram.is_configured():
        notifiers.append(telegram)
    return notifiers


def notify_user(user, title: str, message: str) -> None:
    """Kullanıcının yapılandırdığı tüm aktif kanallardan bildirim gönderir.
    Sessizce başarısız olur — alert zaten DB'de var, bildirim ekstra bir kanal."""
    for notifier in get_active_notifiers():
        try:
            notifier.send(user, title, message)
        except Exception as e:
            logger.warning(f"Bildirim gönderiminde beklenmeyen hata: {e}")

# -*- coding: utf-8 -*-
"""
SetPrice Core — Birleşik Tarama Orchestrator'ı (Best-of-Best)

CLI ve Web'in ikisinin de en iyi özelliklerini tek motorda birleştirir:
  ✅ Paralel static tarama (ThreadPool)          — CLI'dan
  ✅ Round-robin domain serpiştime                — CLI'dan
  ✅ Sanity check (0.2x-5.0x fiyat değişimi)     — CLI'dan
  ✅ Taksit çıkarma (tüm siteler)                — CLI'dan
  ✅ Rating/review çıkarma                        — Web'den
  ✅ AI karar motoru entegrasyonu                 — Web'den
  ✅ Domain sağlık kaydı                          — Web'den
  ✅ Checkpoint (kaldığı yerden devam)             — Yeni
  ✅ Scan lock (çift tarama engelleme)            — Yeni
  ✅ Excel otomatik export                        — Yeni

Tek doğruluk kaynağı: SQLite veritabanı (setprice.sqlite)
"""
import os
import time
import uuid
import threading
import requests as http_requests
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from .config_loader import ConfigLoader
from .scraper import Scraper
from .akakce import AkakceSearcher
from .price_parser import should_skip_price, parse_price
from .scan_lock import get_scan_lock

# Web backend modelleri — lazy import ile döngüsel bağımlılığı engelliyoruz
_models = None
_crud = None
_schemas = None


def _get_web_models():
    global _models
    if _models is None:
        from src.web_backend import models as m
        _models = m
    return _models


def _get_crud():
    global _crud
    if _crud is None:
        from src.web_backend import crud as c
        _crud = c
    return _crud


def _get_schemas():
    global _schemas
    if _schemas is None:
        from src.web_backend import schemas as s
        _schemas = s
    return _schemas


class Orchestrator:
    """Birleşik tarama motoru. DB'den okur, DB'ye yazar."""

    def __init__(self, config: dict, logger, db: Session):
        self.config = config
        self.logger = logger
        self.db = db

        self.site_configs = ConfigLoader().load_site_configs()
        self.scraper = Scraper(config, self.site_configs, logger)
        self.akakce = AkakceSearcher(config, logger)

        # İstatistikler
        self.ok_items = []
        self.failed_items = []
        self.flagged_items = []
        self.skipped_items = []
        self.price_drops = []
        self.price_increases = []
        self.stats_lock = threading.Lock()

        # Checkpoint
        self._scan_session_id = str(uuid.uuid4())

    # ─── ANA TARAMA ─────────────────────────────────────────────────

    def run_once(self, user_id: int = None, dry_run: bool = False,
                 force: bool = False, lib_product_ids: List[int] = None) -> dict:
        """
        Ana tarama akışı. Tüm ürünleri veya belirli ürünleri tarar.

        Args:
            user_id: Taranacak kullanıcının ID'si (None = tümü, admin modu)
            dry_run: True ise sadece ne yapacağını gösterir, DB'ye yazmaz
            force: True ise checkpoint'leri yok sayar
            lib_product_ids: Belirli ürünleri tara (None = tümü)
        """
        self.logger.info(f"Bot çalıştırılıyor... (dry_run={dry_run}, force={force})")
        start_time = time.time()

        models = _get_web_models()

        # Stats sıfırla
        self.ok_items = []
        self.failed_items = []
        self.flagged_items = []
        self.skipped_items = []
        self.price_drops = []
        self.price_increases = []

        # 1. Taranacak ürünleri DB'den oku
        query = self.db.query(models.LibraryProduct)
        if user_id:
            query = query.filter(models.LibraryProduct.user_id == user_id)
        if lib_product_ids:
            query = query.filter(models.LibraryProduct.id.in_(lib_product_ids))

        lib_products = query.all()

        if not lib_products:
            self.logger.warning("Taranacak ürün bulunamadı.")
            return {"status": "empty", "message": "Taranacak ürün yok"}

        self.logger.info(f"Toplam taranacak ürün: {len(lib_products)}")

        if dry_run:
            for lp in lib_products:
                self.logger.info(f"[DRY-RUN] İşlenecek: {lp.name} | {lp.original_link}")
            return {"status": "success", "message": "Dry run tamamlandı", "total": len(lib_products)}

        # 2. Domain'e göre round-robin serpiştirir
        interleaved = self._interleave_by_domain(lib_products)

        # 3. Fiyat Çekme (Faz 1: Paralel Static, Faz 2: Sıralı Browser)
        static_products = []
        browser_products = []

        for lp in interleaved:
            domain = self.scraper._get_domain(lp.original_link)
            site_cfg = self.site_configs.get(domain, {})
            if site_cfg.get("render", False):
                browser_products.append(lp)
            else:
                static_products.append(lp)

        # Faz 1: Paralel Static tarama
        max_workers = self.config.get("scraping", {}).get("max_workers", 5)
        self.logger.info(f"Paralel static tarama başlatılıyor ({max_workers} thread, {len(static_products)} ürün)...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._scan_product, lp, force): lp
                for lp in static_products
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result == "PENDING_PLAYWRIGHT":
                        browser_products.append(futures[future])
                except Exception as exc:
                    lp = futures[future]
                    self.logger.error(f"{lp.name} static işlenirken hata: {exc}")

        # Faz 2: Sıralı Browser tarama (Playwright)
        if browser_products:
            self.logger.info(f"Sıralı Playwright taraması başlatılıyor ({len(browser_products)} ürün)...")
            for lp in browser_products:
                try:
                    self._scan_product_browser(lp, force)
                except Exception as exc:
                    self.logger.error(f"{lp.name} browser işlenirken hata: {exc}")

        # 4. Akakçe muadilleri ara
        self.logger.info("Akakçe muadilleri aranıyor...")
        self._sync_alternatives(lib_products)

        # 5. Karar motoru sinyallerini güncelle
        lib_ids = [lp.id for lp in lib_products]
        if lib_ids:
            self.logger.info(f"Karar motoru sinyalleri güncelleniyor ({len(lib_ids)} ürün)...")
            crud = _get_crud()
            crud.update_decision_signals(self.db, lib_ids)

        # 6. Tarayıcıları kapat
        self.scraper.close()
        self.akakce.close()

        # 7. Checkpoint'leri temizle (başarılı tamamlandı)
        self._clear_checkpoints()

        # 8. Excel'i otomatik güncelle
        self._auto_export_excel(user_id)

        # 9. Dashboard ve bildirimler
        duration_sec = time.time() - start_time
        self._print_dashboard(duration_sec)
        self._send_notification(duration_sec)

        self.logger.info("Bot çalıştırması tamamlandı.")

        return {
            "status": "success",
            "processed": len(lib_products),
            "ok": len(self.ok_items),
            "failed": len(self.failed_items),
            "flagged": len(self.flagged_items),
            "skipped": len(self.skipped_items),
            "drops": len(self.price_drops),
            "increases": len(self.price_increases),
        }

    # ─── ÜRÜN TARAMA (STATIC) ──────────────────────────────────────

    def _scan_product(self, lp, force: bool = False) -> str:
        """Tek bir ürünü tarar (static yöntemlerle). ThreadPool içinden çağrılır."""
        models = _get_web_models()
        crud = _get_crud()

        url = lp.original_link
        if not url:
            return "SKIPPED"

        # Checkpoint kontrolü
        if not force:
            checkpoint = self._get_checkpoint(url)
            if checkpoint:
                self.logger.info(f"[RESUME] Checkpoint: {lp.name} -> {checkpoint['price']}")
                with self.stats_lock:
                    if checkpoint["status"] == "OK":
                        self.ok_items.append(lp)
                    elif checkpoint["status"] == "FAILED":
                        self.failed_items.append(lp)
                return "CHECKPOINT"

        domain = self.scraper._get_domain(url)
        site_cfg = self.site_configs.get(domain, {})

        # Domain bekleme
        self.scraper._wait_for_domain(domain)

        # HTML Çek (Static)
        self.logger.debug(f"[{domain}] Static (Requests) ile çekiliyor: {url[:60]}...")
        try:
            html = self.scraper._fetch_requests(url)
        except Exception as e:
            self.logger.warning(f"Requests hatası: {e}")
            html = None

        if html in ("403_FORBIDDEN", "429_TOO_MANY_REQUESTS") or not html:
            if self.config.get("scraping", {}).get("cloudscraper_fallback", True):
                self.logger.debug(f"[{domain}] Cloudscraper deneniyor...")
                html = self.scraper._fetch_cloudscraper(url)

        if html in ("403_FORBIDDEN", "429_TOO_MANY_REQUESTS") or not html:
            return "PENDING_PLAYWRIGHT"

        # Fiyat çıkar
        new_price = self.scraper.extract_price(html, site_cfg)
        if new_price is None:
            return "PENDING_PLAYWRIGHT"

        # Ortak güncelleme mantığı
        return self._apply_price_update(lp, html, new_price, site_cfg, domain)

    # ─── ÜRÜN TARAMA (BROWSER/PLAYWRIGHT) ──────────────────────────

    def _scan_product_browser(self, lp, force: bool = False) -> None:
        """Tek bir ürünü Playwright ile tarar. Ana thread'de sıralı çağrılır."""
        models = _get_web_models()

        url = lp.original_link
        if not url:
            return

        if not force:
            checkpoint = self._get_checkpoint(url)
            if checkpoint:
                return

        domain = self.scraper._get_domain(url)
        site_cfg = self.site_configs.get(domain, {})

        # Playwright ile çek
        html = self.scraper._fetch_playwright(url)

        # Fallback zincirleri
        if not html or html in ("403_FORBIDDEN", "429_TOO_MANY_REQUESTS"):
            self.logger.debug(f"[Browser Fallback] Playwright başarısız, static deneniyor: {lp.name[:30]}")
            try:
                html = self.scraper._fetch_requests(url)
            except Exception:
                html = None
            if not html or html in ("403_FORBIDDEN", "429_TOO_MANY_REQUESTS"):
                html = self.scraper._fetch_cloudscraper(url)

        # Fiyat çıkar
        new_price = self.scraper.extract_price(html, site_cfg)

        # Son çare: static HTML ile tekrar dene
        if new_price is None and html:
            self.logger.debug(f"[Browser Fallback] Fiyat bulunamadı, son static denemesi: {lp.name[:30]}")
            try:
                fallback_html = self.scraper._fetch_requests(url)
            except Exception:
                fallback_html = None
            if not fallback_html or fallback_html in ("403_FORBIDDEN", "429_TOO_MANY_REQUESTS"):
                fallback_html = self.scraper._fetch_cloudscraper(url)
            if fallback_html:
                fallback_price = self.scraper.extract_price(fallback_html, site_cfg)
                if fallback_price is not None:
                    new_price = fallback_price
                    html = fallback_html

        if new_price is None:
            self.logger.warning(f"[HATA] Fiyat bulunamadı (Browser): {lp.name}")
            self._mark_failed(lp, domain)
            return

        self._apply_price_update(lp, html, new_price, site_cfg, domain)

    # ─── ORTAK FİYAT GÜNCELLEME ────────────────────────────────────

    def _apply_price_update(self, lp, html: str, new_price: float,
                            site_cfg: dict, domain: str) -> str:
        """Fiyat bulunduktan sonra ortak doğrulama ve DB güncelleme mantığı."""
        models = _get_web_models()
        crud = _get_crud()

        url = lp.original_link
        old_price = lp.current_price

        # Sanity Check (CLI'dan)
        is_valid, err_msg = self._validate_price(old_price, new_price)
        if not is_valid:
            self.logger.warning(f"[FLAG] Olağandışı fiyat: {lp.name} | {old_price} -> {new_price} ({err_msg})")
            if self.config.get("validation", {}).get("flag_instead_of_write", True):
                lp.status = "FLAGGED"
                lp.updated_at = datetime.utcnow()
                self._save_checkpoint(url, old_price, "FLAGGED")
                self.db.commit()
                with self.stats_lock:
                    self.flagged_items.append(lp)
                crud.record_domain_health(self.db, domain, success=False)
                return "FLAGGED"

        # Taksit çıkar (CLI'dan — tüm siteler)
        installment = self.scraper.extract_installment(html)

        # Rating ve review (Web'den)
        rating, review_count = self.scraper.extract_rating_info(html)

        # DB Güncelle
        lp.current_price = new_price
        lp.current_seller = self.scraper._infer_seller(url)
        lp.current_installment = installment
        lp.status = "OK"
        lp.updated_at = datetime.utcnow()

        if rating is not None:
            lp.rating = rating
        if review_count is not None:
            lp.review_count = review_count

        # Fiyat geçmişine ekle (fiyat değiştiyse)
        if old_price != new_price:
            crud.add_price_history(self.db, lp.id, new_price, lp.current_seller)

        # Checkpoint kaydet
        self._save_checkpoint(url, new_price, "OK")

        # Domain sağlık kaydı
        crud.record_domain_health(self.db, domain, success=True)

        self.db.commit()

        self.logger.success(f"[OK] {lp.name} | {lp.current_seller} -> {new_price}")

        # İstatistikleri güncelle
        with self.stats_lock:
            self.ok_items.append(lp)
            if old_price is not None:
                try:
                    old_f = float(old_price)
                    new_f = float(new_price)
                    if new_f < old_f:
                        self.price_drops.append((lp, old_f, new_f))
                    elif new_f > old_f:
                        self.price_increases.append((lp, old_f, new_f))
                except (ValueError, TypeError):
                    pass

        if installment:
            self.logger.info(f"Taksit bulundu: {lp.name} -> {installment}")

        return "OK"

    def _mark_failed(self, lp, domain: str) -> None:
        """Başarısız taramayı işaretle."""
        crud = _get_crud()
        lp.status = "FAILED"
        lp.updated_at = datetime.utcnow()
        self._save_checkpoint(lp.original_link, lp.current_price, "FAILED")
        crud.record_domain_health(self.db, domain, success=False)
        self.db.commit()
        with self.stats_lock:
            self.failed_items.append(lp)

    # ─── DOĞRULAMA ─────────────────────────────────────────────────

    def _validate_price(self, old_price, new_price: float) -> Tuple[bool, str]:
        """Fiyat değişiminin mantıklı olup olmadığını kontrol eder."""
        val_cfg = self.config.get("validation", {})
        min_valid = val_cfg.get("min_valid_price", 1.0)

        if new_price < min_valid:
            return False, f"Fiyat çok düşük (< {min_valid})"

        if old_price is None:
            return True, ""

        try:
            old = float(old_price)
            max_ratio = val_cfg.get("max_change_ratio", 5.0)
            min_ratio = val_cfg.get("min_change_ratio", 0.2)

            if old > 0:
                ratio = new_price / old
                if ratio > max_ratio:
                    return False, f"Fiyat çok arttı (x{ratio:.1f})"
                if ratio < min_ratio:
                    return False, f"Fiyat çok düştü (x{ratio:.1f})"
        except (ValueError, TypeError):
            pass

        return True, ""

    # ─── ROUND-ROBIN SERPİŞTİRME ──────────────────────────────────

    def _interleave_by_domain(self, products) -> list:
        """Ürünleri domain'e göre round-robin serpiştirir. Aynı domain'e
        arka arkaya istek göndermemek için."""
        by_domain = defaultdict(list)
        for lp in products:
            domain = self.scraper._get_domain(lp.original_link)
            by_domain[domain].append(lp)

        interleaved = []
        domains = list(by_domain.keys())
        counts = {d: 0 for d in domains}
        total = sum(len(lst) for lst in by_domain.values())

        while len(interleaved) < total:
            for d in domains:
                lst = by_domain[d]
                if counts[d] < len(lst):
                    interleaved.append(lst[counts[d]])
                    counts[d] += 1
        return interleaved

    # ─── AKAKÇE MUADİLLER ─────────────────────────────────────────

    def _sync_alternatives(self, lib_products) -> None:
        """Başarılı ürünler için Akakçe muadil araması yapar ve DB'ye yazar."""
        crud = _get_crud()
        schemas = _get_schemas()

        terms_map = defaultdict(list)
        name_by_id = {}

        for lp in lib_products:
            if lp.status == "OK":
                search_term = self.akakce._infer_search_term(lp.name, lp.category)
                if search_term:
                    terms_map[search_term].append(lp.id)
                    name_by_id[lp.id] = lp.name

        if not terms_map:
            return

        try:
            terms_payload = {
                term: [name_by_id[lp_id] for lp_id in lp_ids if lp_id in name_by_id]
                for term, lp_ids in terms_map.items()
            }
            id_by_name = {name: lp_id for lp_id, name in name_by_id.items()}

            rows = self.akakce.search_batch(terms_payload, top_n=6)

            grouped = defaultdict(list)
            for row in rows:
                grouped[row.product].append(row)

            from src.web_backend.similarity_utils import classify_match

            for name, product_rows in grouped.items():
                lp_id = id_by_name.get(name)
                if not lp_id:
                    continue
                alt_schemas = []
                for row in product_rows:
                    match_type, confidence = classify_match(name, row.alt_product)
                    alt_schemas.append(schemas.AlternativeBase(
                        title=row.alt_product,
                        price=row.alt_price,
                        seller=row.alt_seller,
                        link=row.alt_link,
                        match_type=match_type,
                        match_confidence=confidence,
                    ))
                crud.sync_alternatives(self.db, lp_id, alt_schemas)

        except Exception as e:
            self.logger.error(f"Akakçe araması sırasında hata: {e}")

    # ─── CHECKPOINT SİSTEMİ ────────────────────────────────────────

    def _get_checkpoint(self, url: str) -> Optional[dict]:
        """URL için mevcut checkpoint döner."""
        models = _get_web_models()
        cp = self.db.query(models.ScanCheckpoint).filter(
            models.ScanCheckpoint.url == url
        ).order_by(models.ScanCheckpoint.created_at.desc()).first()

        if cp:
            return {"price": cp.price, "status": cp.status}
        return None

    def _save_checkpoint(self, url: str, price, status: str) -> None:
        """Checkpoint kaydet veya güncelle."""
        models = _get_web_models()

        existing = self.db.query(models.ScanCheckpoint).filter(
            models.ScanCheckpoint.scan_session_id == self._scan_session_id,
            models.ScanCheckpoint.url == url
        ).first()

        if existing:
            existing.price = price
            existing.status = status
        else:
            cp = models.ScanCheckpoint(
                scan_session_id=self._scan_session_id,
                url=url,
                price=price,
                status=status,
            )
            self.db.add(cp)

    def _clear_checkpoints(self) -> None:
        """Mevcut session'ın checkpoint'lerini temizle (başarılı tamamlandı)."""
        models = _get_web_models()
        self.db.query(models.ScanCheckpoint).filter(
            models.ScanCheckpoint.scan_session_id == self._scan_session_id
        ).delete()
        self.db.commit()

    # ─── EXCEL OTOMATİK EXPORT ─────────────────────────────────────

    def _auto_export_excel(self, user_id: int = None) -> None:
        """Tarama sonunda Excel'i otomatik günceller."""
        try:
            from src.cli.excel_bridge import ExcelExporter
            workbook_path = self.config.get("paths", {}).get("workbook")
            if workbook_path and os.path.exists(workbook_path):
                exporter = ExcelExporter(self.config, self.logger)
                exporter.export_to_excel(workbook_path, self.db, user_id)
                self.logger.info(f"Excel otomatik güncellendi: {workbook_path}")
        except Exception as e:
            self.logger.warning(f"Excel otomatik export hatası: {e}")

    # ─── DASHBOARD ─────────────────────────────────────────────────

    def _print_dashboard(self, duration_sec: float) -> None:
        """Konsol dashboard'u yazdırır."""
        total = len(self.ok_items) + len(self.failed_items) + len(self.flagged_items) + len(self.skipped_items)

        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        duration_str = f"{minutes} dk {seconds} sn" if minutes > 0 else f"{seconds} sn"

        installment_count = sum(1 for lp in self.ok_items if lp.current_installment)

        dashboard = []
        dashboard.append("╔" + "═" * 63 + "╗")
        dashboard.append("║" + "🤖 FİYAT BOTU ÇALIŞTIRMA ÖZETİ".center(63) + "║")
        dashboard.append("╠" + "═" * 63 + "╣")
        dashboard.append(f"║ Toplam İşlenen Ürün  : {total:<43} ║")
        dashboard.append(f"║ Başarılı (OK)        : {len(self.ok_items):<10} ✅ {f'({installment_count} taksit)':<28} ║")
        dashboard.append(f"║ Başarısız (FAILED)   : {len(self.failed_items):<10} ❌                            ║")
        dashboard.append(f"║ Şüpheli (FLAGGED)    : {len(self.flagged_items):<10} ⚠️                            ║")
        dashboard.append(f"║ Pas Geçilen (SKIP)   : {len(self.skipped_items):<10} ▬                             ║")
        dashboard.append("╠" + "═" * 63 + "╣")
        dashboard.append(f"║ Düşen Fiyatlar (▼)   : {len(self.price_drops):<43} ║")
        dashboard.append(f"║ Artan Fiyatlar (▲)   : {len(self.price_increases):<43} ║")
        dashboard.append(f"║ Toplam Geçen Süre    : {duration_str:<43} ║")
        dashboard.append("╚" + "═" * 63 + "╝")

        for line in dashboard:
            print(line)
            self.logger.info(line)

        for lp, old_p, new_p in self.price_drops:
            diff = old_p - new_p
            pct = (diff / old_p) * 100
            alert = f"🔔 FİYAT DÜŞÜŞÜ: {lp.name} -> {old_p} ₺ iken {new_p} ₺ oldu! (-%{pct:.1f})"
            print(f"\033[92m{alert}\033[0m")
            self.logger.success(alert)

        for lp, old_p, new_p in self.price_increases:
            diff = new_p - old_p
            pct = (diff / old_p) * 100
            alert = f"⚠️ FİYAT ARTIŞI: {lp.name} -> {old_p} ₺ iken {new_p} ₺ oldu! (+%{pct:.1f})"
            print(f"\033[91m{alert}\033[0m")
            self.logger.warning(alert)

    # ─── BİLDİRİM ─────────────────────────────────────────────────

    def _send_notification(self, duration_sec: float) -> None:
        """Discord/Telegram bildirimlerini gönderir."""
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        duration_str = f"{minutes} dk {seconds} sn" if minutes > 0 else f"{seconds} sn"

        summary_msg = (
            f"🤖 **Fiyat Botu Tarama Özeti**\n"
            f"✅ Başarılı: {len(self.ok_items)} | ❌ Hata: {len(self.failed_items)} | ⚠️ Şüpheli: {len(self.flagged_items)}\n"
            f"📉 Düşenler: {len(self.price_drops)} | 📈 Artanlar: {len(self.price_increases)}\n"
            f"⏱️ Süre: {duration_str}"
        )

        if self.price_drops:
            summary_msg += "\n\n🔥 **Fiyatı Düşen Ürünler:**"
            for lp, old_p, new_p in self.price_drops[:5]:
                pct = ((old_p - new_p) / old_p) * 100
                summary_msg += f"\n- {lp.name}: {old_p} ₺ -> **{new_p} ₺** (-%{pct:.1f})"

        notif_cfg = self.config.get("notifications", {})
        discord_url = notif_cfg.get("discord_webhook_url")
        tg_token = notif_cfg.get("telegram_token")
        tg_chat_id = notif_cfg.get("telegram_chat_id")

        if discord_url:
            try:
                http_requests.post(discord_url, json={"content": summary_msg}, timeout=10)
                self.logger.info("Discord bildirimi gönderildi.")
            except Exception as e:
                self.logger.warning(f"Discord bildirimi başarısız: {e}")

        if tg_token and tg_chat_id:
            try:
                url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                http_requests.post(url, json={"chat_id": tg_chat_id, "text": summary_msg}, timeout=10)
                self.logger.info("Telegram bildirimi gönderildi.")
            except Exception as e:
                self.logger.warning(f"Telegram bildirimi başarısız: {e}")

    # ─── DURUM BİLGİSİ ────────────────────────────────────────────

    def print_status(self, user_id: int = None) -> None:
        """DB'den durum bilgisini okuyup konsola yazdırır."""
        models = _get_web_models()

        query = self.db.query(models.LibraryProduct)
        if user_id:
            query = query.filter(models.LibraryProduct.user_id == user_id)

        lib_prods = query.all()
        total = len(lib_prods)
        ok_count = sum(1 for lp in lib_prods if lp.status == "OK")
        failed_count = sum(1 for lp in lib_prods if lp.status == "FAILED")
        flagged_count = sum(1 for lp in lib_prods if lp.status == "FLAGGED")
        waiting_count = sum(1 for lp in lib_prods if lp.status == "BEKLEMEDE")

        last_updated = "Bilinmiyor"
        for lp in lib_prods:
            if lp.updated_at:
                date_str = lp.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if last_updated == "Bilinmiyor" or date_str > last_updated:
                    last_updated = date_str

        # Set sayısı
        set_count = self.db.query(models.ProductSet).count()

        print("╔" + "═" * 63 + "╗")
        print("║" + "📊 FİYAT BOTU DURUM RAPORU".center(63) + "║")
        print("╠" + "═" * 63 + "╣")
        print(f"║ Toplam Ürün Sayısı   : {total:<43} ║")
        print(f"║ Başarılı (OK)        : {ok_count:<43} ║")
        print(f"║ Başarısız (FAILED)   : {failed_count:<43} ║")
        print(f"║ Şüpheli (FLAGGED)    : {flagged_count:<43} ║")
        print(f"║ Beklemede            : {waiting_count:<43} ║")
        print(f"║ Set Sayısı           : {set_count:<43} ║")
        print(f"║ Son Güncelleme       : {str(last_updated):<43} ║")
        print("╚" + "═" * 63 + "╝")

# -*- coding: utf-8 -*-
import os
import time
import csv
import json
import sqlite3
import threading
import requests
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import SourceRow, CatalogRow
from .excel_handler import ExcelHandler
from .config_loader import ConfigLoader
from .scraper import Scraper
from .akakce import AkakceSearcher
from .price_parser import should_skip_price, parse_price

class Orchestrator:
    def __init__(self, config: dict, logger):
        self.config = config
        self.logger = logger
        
        self.excel = ExcelHandler(config, logger)
        self.site_configs = ConfigLoader().load_site_configs()
        self.scraper = Scraper(config, self.site_configs, logger)
        self.akakce = AkakceSearcher(config, logger)
        
        # Reports
        self.reports_dir = config.get("paths", {}).get("reports_dir", "./data/reports")
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
            
        self.flagged_items = []
        self.failed_items = []
        self.ok_items = []
        self.skipped_items = []
        self.price_drops = []
        self.price_increases = []
        self.stats_lock = threading.Lock()
        
        self._init_checkpoint_db()

    def run_once(self, dry_run: bool = False, force: bool = False) -> dict:
        self.logger.info(f"Bot çalıştırılıyor... (dry_run={dry_run}, force={force})")
        start_time = time.time()
        
        # Stats sıfırla
        self.flagged_items = []
        self.failed_items = []
        self.ok_items = []
        self.skipped_items = []
        self.price_drops = []
        self.price_increases = []
        
        if not dry_run:
            self.excel.load()
            self.excel.create_backup()
            
        # 1. Kaynakları Oku
        sources = self.excel.read_sources() if not dry_run else []
        if dry_run:
            self.excel.load()
            sources = self.excel.read_sources()
            
        if not sources:
            self.logger.warning("Kaynaklar sayfası boş veya okunamadı.")
            return {"status": "error", "message": "Kaynaklar boş"}
            
        # 2. Domain'e göre serpiştir (round-robin)
        interleaved_sources = self._interleave_by_domain(sources)
        self.logger.info(f"Toplam işlenecek link: {len(interleaved_sources)}")
        
        # 3. Fiyat Çekme (Faz 1: Paralel Static, Faz 2: Sıralı Browser)
        if dry_run:
            for row in interleaved_sources:
                self.logger.info(f"[DRY-RUN] İşlenecek: {row.product} | {row.link}")
        else:
            static_rows = []
            browser_rows = []
            
            for row in interleaved_sources:
                domain = self.scraper._get_domain(row.link)
                site_cfg = self.site_configs.get(domain, {})
                if site_cfg.get("render", False):
                    browser_rows.append(row)
                else:
                    static_rows.append(row)
            
            # Faz 1: Paralel Static tarama
            max_workers = self.config.get("scraping", {}).get("max_workers", 5)
            self.logger.info(f"Paralel static tarama başlatılıyor ({max_workers} thread, {len(static_rows)} link)...")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._process_static_row, row, force): row for row in static_rows}
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        # Eğer static istek başarısız olduysa ve Playwright desteği varsa sıralı gruba ekle
                        if result == "PENDING_PLAYWRIGHT":
                            row = futures[future]
                            browser_rows.append(row)
                    except Exception as exc:
                        row = futures[future]
                        self.logger.error(f"{row.product} static işlenirken hata oluştu: {exc}")
            
            # Faz 2: Sıralı Browser tarama (Ana Thread'de)
            if browser_rows:
                self.logger.info(f"Sıralı tarayıcı (Playwright) taraması başlatılıyor ({len(browser_rows)} link)...")
                for row in browser_rows:
                    try:
                        self._process_browser_row(row, force)
                    except Exception as exc:
                        self.logger.error(f"{row.product} browser işlenirken hata oluştu: {exc}")
                        
        if dry_run:
            return {"status": "success", "message": "Dry run tamamlandı"}
            
        # 4. En ucuz fiyatı bul ve Katalog'u güncelle
        catalog = self.excel.read_catalog()
        new_catalog_data = self._resolve_cheapest(sources, catalog)
        
        now = datetime.now()
        for prod, data in new_catalog_data.items():
            self.excel.write_catalog_row(
                product=prod,
                category=data["category"],
                price=data["price"],
                seller=data["seller"],
                link=data["link"],
                timestamp=now,
                search_term=data["search_term"],
                trend=data.get("trend", "▬")
            )
            
            # Fiyat_Gecmisi
            if data["price"] is not None:
                self.excel.append_history(prod, data["seller"], data["price"], now)
                
        # 5. Muadilleri güncelle
        self.logger.info("Muadiller aranıyor...")
        terms_map = defaultdict(list)
        for cat_row in new_catalog_data.values():
            if cat_row["search_term"]:
                terms_map[cat_row["search_term"]].append(cat_row["product"])
                
        self.scraper.close()
        
        alternatives = self.akakce.search_batch(terms_map)
        self.akakce.close()
        if alternatives:
            self.excel.write_alternatives(alternatives)
            
        # 6. Kaydet ve Raporla
        self.excel.sort_sheet_by_category(self.excel.sources_sheet_name)
        self.excel.sort_sheet_by_category(self.excel.catalog_sheet_name)
        self.excel.add_data_validation_to_sources()
        
        self.excel.save()
        self._write_reports(sources, catalog)
        
        self._close_browsers()
        
        duration_sec = time.time() - start_time
        self._print_dashboard(duration_sec)
        self.logger.info("Bot çalıştırması tamamlandı.")
        
        return {
            "status": "success",
            "processed": len(sources),
            "flagged": len(self.flagged_items),
            "failed": len(self.failed_items)
        }

    def run_alternatives_only(self) -> dict:
        self.logger.info("Sadece Muadiller güncelleniyor...")
        self.excel.load()
        self.excel.create_backup()
        
        catalog = self.excel.read_catalog()
        terms_map = defaultdict(list)
        for row in catalog:
            if row.search_term:
                terms_map[row.search_term].append(row.product)
                
        alternatives = self.akakce.search_batch(terms_map)
        if alternatives:
            self.excel.write_alternatives(alternatives)
            self.excel.save()
            
        self._close_browsers()
        return {"status": "success"}

    def run_watch(self, interval_min: int = 60) -> None:
        self.logger.info(f"Bot izleme modunda başlatıldı. ({interval_min} dakikada bir)")
        try:
            while True:
                self.run_once()
                self.logger.info(f"{interval_min} dakika bekleniyor...")
                time.sleep(interval_min * 60)
        except KeyboardInterrupt:
            self.logger.info("İzleme modu durduruldu.")
            self._close_browsers()

    def _interleave_by_domain(self, sources: List[SourceRow]) -> List[SourceRow]:
        by_domain = defaultdict(list)
        for s in sources:
            domain = self.scraper._get_domain(s.link)
            by_domain[domain].append(s)
            
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

    def _process_static_row(self, row: SourceRow, force: bool = False) -> str:
        # Manuel kontrol (Kilit, Aktif vs)
        if not row.active:
            self.logger.info(f"[ATLA] {row.product} | {row.seller} | Aktif: Hayır")
            with self.stats_lock:
                self.skipped_items.append(row)
            return "SKIPPED"
            
        if row.locked:
            self.logger.info(f"[ATLA] {row.product} | {row.seller} | Kilit: Evet")
            with self.stats_lock:
                self.skipped_items.append(row)
            return "SKIPPED"
            
        skip, reason = should_skip_price(row.price, self.config)
        if skip:
            self.logger.info(f"[ATLA] {row.product} | {row.seller} | Neden: {reason}")
            with self.stats_lock:
                self.skipped_items.append(row)
            return "SKIPPED"
            
        # Checkpoint kontrolü
        checkpoint = self._get_checkpoint(row.link) if not force else None
        if checkpoint:
            self.logger.info(f"[RESUME] Checkpoint bulundu: {row.product} | {row.seller} -> {checkpoint['price']}")
            row.price = checkpoint['price']
            row.status = checkpoint['status']
            # Yerel durumu güncelle
            with self.stats_lock:
                if checkpoint['status'] == "OK":
                    self.ok_items.append(row)
                elif checkpoint['status'] == "FAILED":
                    self.failed_items.append({
                        "product": row.product,
                        "seller": row.seller,
                        "link": row.link,
                        "reason": "Previous Run Failed"
                    })
                elif checkpoint['status'] == "FLAGGED":
                    self.flagged_items.append({
                        "product": row.product,
                        "seller": row.seller,
                        "old_price": row.price,
                        "new_price": row.price,
                        "link": row.link,
                        "reason": "Previous Run Flagged"
                    })
            return "CHECKPOINT"

        site_cfg = self.site_configs.get(self.scraper._get_domain(row.link), {})
        
        # HTML Çek (Sadece static)
        domain = self.scraper._get_domain(row.link)
        self.scraper._wait_for_domain(domain)
        
        self.logger.debug(f"[{domain}] Static (Requests) ile çekiliyor: {row.link[:60]}...")
        try:
            html = self.scraper._fetch_requests(row.link)
        except Exception as e:
            self.logger.warning(f"Requests hatası: {e}")
            html = None
            
        if html == "403_FORBIDDEN" or html == "429_TOO_MANY_REQUESTS" or not html:
            if self.config.get("scraping", {}).get("cloudscraper_fallback", True):
                self.logger.debug(f"[{domain}] Cloudscraper ile deneniyor: {row.link[:60]}...")
                html = self.scraper._fetch_cloudscraper(row.link)
                
        if html == "403_FORBIDDEN" or html == "429_TOO_MANY_REQUESTS" or not html:
            # Playwright gerekebilir, tarayıcı listesine devret
            return "PENDING_PLAYWRIGHT"
            
        # Fiyat Çıkar
        new_price = self.scraper.extract_price(html, site_cfg)
        if new_price is None:
            # Fiyat bulamadık, belki JS ile render ediliyordur, Playwright'a devret
            return "PENDING_PLAYWRIGHT"
            
        # Sanity Check
        is_valid, err_msg = self._validate_price(row.price, new_price)
        if not is_valid:
            self.logger.warning(f"[FLAG] Olağandışı fiyat değişimi: {row.product} | {row.seller} | {row.price} -> {new_price} ({err_msg})")
            if self.config.get("validation", {}).get("flag_instead_of_write", True):
                self._mark_flagged(row, new_price, err_msg)
                return "FLAGGED"
                
        # Taksit Çıkar
        installment = self.scraper.extract_installment(html)
        if installment:
            row.installment = installment
            self.logger.info(f"Taksit bulundu: {row.product} | {row.seller} -> {installment}")
            
        # Başarılı -> Excel'e yaz ve Checkpoint'e kaydet
        self.logger.success(f"[OK] {row.product} | {row.seller} -> {new_price}")
        old_price = row.price
        row.price = new_price
        row.status = "OK"
        row.updated = datetime.now()
        self.excel.write_source_price(row.row_number, new_price, "OK", row.updated, row.installment)
        self._save_checkpoint(row.link, new_price, "OK")
        
        with self.stats_lock:
            if old_price is not None:
                try:
                    old_f = float(old_price)
                    new_f = float(new_price)
                    if new_f < old_f:
                        self.price_drops.append((row, old_f, new_f))
                    elif new_f > old_f:
                        self.price_increases.append((row, old_f, new_f))
                except:
                    pass
            self.ok_items.append(row)
            
        return "OK"

    def _process_browser_row(self, row: SourceRow, force: bool = False) -> None:
        if not row.active or row.locked:
            return
            
        checkpoint = self._get_checkpoint(row.link) if not force else None
        if checkpoint:
            return
            
        site_cfg = self.site_configs.get(self.scraper._get_domain(row.link), {})
        
        # HTML Çek (Playwright ile)
        html = self.scraper._fetch_playwright(row.link)
        
        # Eğer Playwright engellendiyse veya başarısız olduysa static fallback dene
        if not html or html in ["403_FORBIDDEN", "429_TOO_MANY_REQUESTS"]:
            self.logger.debug(f"[Browser Fallback] Playwright engellendi, static deneniyor: {row.product[:30]}")
            try:
                html = self.scraper._fetch_requests(row.link)
            except:
                html = None
            if not html or html in ["403_FORBIDDEN", "429_TOO_MANY_REQUESTS"]:
                html = self.scraper._fetch_cloudscraper(row.link)
                
        # Fiyat Çıkar
        new_price = self.scraper.extract_price(html, site_cfg)
        
        # Eğer fiyat bulunamadıysa (belki Playwright sayfası hatalı yüklenmiştir), son bir kez static html dene
        if new_price is None:
            self.logger.debug(f"[Browser Fallback] Fiyat bulunamadı, son kez static HTML deneniyor: {row.product[:30]}")
            try:
                fallback_html = self.scraper._fetch_requests(row.link)
            except:
                fallback_html = None
            if not fallback_html or fallback_html in ["403_FORBIDDEN", "429_TOO_MANY_REQUESTS"]:
                fallback_html = self.scraper._fetch_cloudscraper(row.link)
                
            if fallback_html:
                fallback_price = self.scraper.extract_price(fallback_html, site_cfg)
                if fallback_price is not None:
                    new_price = fallback_price
                    html = fallback_html
                    
        if new_price is None:
            self.logger.warning(f"[HATA] Fiyat bulunamadı (Browser): {row.product} | {row.seller}")
            self._mark_failed(row, "Parse Failed")
            return
            
        # Sanity Check
        is_valid, err_msg = self._validate_price(row.price, new_price)
        if not is_valid:
            self.logger.warning(f"[FLAG] Olağandışı fiyat değişimi: {row.product} | {row.seller} | {row.price} -> {new_price} ({err_msg})")
            if self.config.get("validation", {}).get("flag_instead_of_write", True):
                self._mark_flagged(row, new_price, err_msg)
                return
                
        # Taksit Çıkar
        installment = self.scraper.extract_installment(html)
        if installment:
            row.installment = installment
            self.logger.info(f"Taksit bulundu: {row.product} | {row.seller} -> {installment}")
            
        # Başarılı -> Excel'e yaz ve Checkpoint'e kaydet
        self.logger.success(f"[OK] {row.product} | {row.seller} -> {new_price}")
        old_price = row.price
        row.price = new_price
        row.status = "OK"
        row.updated = datetime.now()
        self.excel.write_source_price(row.row_number, new_price, "OK", row.updated, row.installment)
        self._save_checkpoint(row.link, new_price, "OK")
        
        with self.stats_lock:
            if old_price is not None:
                try:
                    old_f = float(old_price)
                    new_f = float(new_price)
                    if new_f < old_f:
                        self.price_drops.append((row, old_f, new_f))
                    elif new_f > old_f:
                        self.price_increases.append((row, old_f, new_f))
                except:
                    pass
            self.ok_items.append(row)

    def _validate_price(self, old_price: float, new_price: float) -> Tuple[bool, str]:
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
        except:
            pass
            
        return True, ""

    def _mark_failed(self, row: SourceRow, reason: str):
        row.status = "FAILED"
        self.excel.write_source_price(row.row_number, row.price, "FAILED", datetime.now())
        self._save_checkpoint(row.link, row.price, "FAILED")
        with self.stats_lock:
            self.failed_items.append({
                "product": row.product,
                "seller": row.seller,
                "link": row.link,
                "reason": reason
            })

    def _mark_flagged(self, row: SourceRow, new_price: float, reason: str):
        row.status = "FLAGGED"
        self.excel.write_source_price(row.row_number, row.price, "FLAGGED", datetime.now()) # write old price, just update status
        self._save_checkpoint(row.link, new_price, "FLAGGED")
        with self.stats_lock:
            self.flagged_items.append({
                "product": row.product,
                "seller": row.seller,
                "old_price": row.price,
                "new_price": new_price,
                "link": row.link,
                "reason": reason
            })

    def _resolve_cheapest(self, sources: List[SourceRow], catalog: List[CatalogRow]) -> dict:
        """Katalog güncellemesi için ürün başına en ucuzları bulur."""
        # Ürün -> Kaynak Listesi
        grouped = defaultdict(list)
        for s in sources:
            if s.product: grouped[s.product.strip().lower()].append(s)
            
        # Mevcut katalog (arama terimlerini korumak için)
        cat_map = {c.product.strip().lower(): c for c in catalog if c.product}
        
        result = {}
        for prod_key, s_list in grouped.items():
            valid_sources = [s for s in s_list if s.status == "OK" and s.price is not None and s.active and not s.locked]
            
            # Locked olanlar her zaman OK sayılır
            valid_sources += [s for s in s_list if s.locked and s.price is not None and s.active]
            
            cat_row = cat_map.get(prod_key)
            search_term = cat_row.search_term if cat_row else ""
            category = s_list[0].category if s_list else ""
            prod_name = s_list[0].product if s_list else ""
            
            if valid_sources:
                valid_sources.sort(key=lambda x: x.price)
                best = valid_sources[0]
                
                # Trend hesapla
                trend = "▬"
                if cat_row and cat_row.best_price is not None:
                    try:
                        old_p = float(cat_row.best_price)
                        new_p = float(best.price)
                        if new_p > old_p:
                            trend = "▲"
                        elif new_p < old_p:
                            trend = "▼"
                    except:
                        pass
                        
                result[prod_key] = {
                    "product": prod_name,
                    "category": category,
                    "price": best.price,
                    "seller": best.seller,
                    "link": best.link,
                    "search_term": search_term,
                    "trend": trend
                }
            else:
                # Hepsi FAILED -> Eski fiyatı koru
                result[prod_key] = {
                    "product": prod_name,
                    "category": category,
                    "price": cat_row.best_price if cat_row else None,
                    "seller": cat_row.best_seller if cat_row else "",
                    "link": cat_row.best_link if cat_row else "",
                    "search_term": search_term,
                    "trend": "▬"
                }
                
        return result

    def _write_reports(self, sources: List[SourceRow], catalog: List[CatalogRow]):
        reports_cfg = self.config.get("reports", {})
        
        if reports_cfg.get("write_flagged", True) and self.flagged_items:
            path = os.path.join(self.reports_dir, "flagged.csv")
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["product", "seller", "old_price", "new_price", "link", "reason"])
                writer.writeheader()
                writer.writerows(self.flagged_items)
                
        if reports_cfg.get("write_failed", True) and self.failed_items:
            path = os.path.join(self.reports_dir, "failed.csv")
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["product", "seller", "link", "reason"])
                writer.writeheader()
                writer.writerows(self.failed_items)

        if reports_cfg.get("write_unmatched", True):
            catalog_names = {c.product.strip().lower() for c in catalog if c.product}
            unmatched_items = []
            for s in sources:
                if s.product and s.product.strip().lower() not in catalog_names:
                    unmatched_items.append({
                        "product": s.product,
                        "category": s.category,
                        "seller": s.seller,
                        "link": s.link,
                        "reason": "Katalogda bulunamadı"
                    })
            if unmatched_items:
                path = os.path.join(self.reports_dir, "unmatched.csv")
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=["product", "category", "seller", "link", "reason"])
                    writer.writeheader()
                    writer.writerows(unmatched_items)

    def _close_browsers(self):
        self.scraper.close()
        self.akakce.close()

    def _init_checkpoint_db(self) -> None:
        pass

    def _get_checkpoint(self, url: str) -> Optional[dict]:
        return None

    def _save_checkpoint(self, url: str, price: Optional[float], status: str) -> None:
        pass

    def _send_notification(self, summary_msg: str) -> None:
        notif_cfg = self.config.get("notifications", {})
        discord_url = notif_cfg.get("discord_webhook_url")
        tg_token = notif_cfg.get("telegram_token")
        tg_chat_id = notif_cfg.get("telegram_chat_id")
        
        if discord_url:
            try:
                requests.post(discord_url, json={"content": summary_msg}, timeout=10)
                self.logger.info("Discord bildirimi gönderildi.")
            except Exception as e:
                self.logger.warning(f"Discord bildirimi başarısız: {e}")
                
        if tg_token and tg_chat_id:
            try:
                url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                requests.post(url, json={"chat_id": tg_chat_id, "text": summary_msg}, timeout=10)
                self.logger.info("Telegram bildirimi gönderildi.")
            except Exception as e:
                self.logger.warning(f"Telegram bildirimi başarısız: {e}")

    def _print_dashboard(self, duration_sec: float) -> None:
        total = len(self.ok_items) + len(self.failed_items) + len(self.flagged_items) + len(self.skipped_items)
        
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        duration_str = f"{minutes} dk {seconds} sn" if minutes > 0 else f"{seconds} sn"
        
        installment_count = sum(1 for s in self.ok_items if s.installment)
        
        dashboard = []
        dashboard.append("╔" + "═" * 63 + "╗")
        dashboard.append("║" + "🤖 FİYAT BOTU ÇALIŞTIRMA ÖZETİ".center(63) + "║")
        dashboard.append("╠" + "═" * 63 + "╣")
        dashboard.append(f"║ Toplam İşlenen Satır : {total:<43} ║")
        dashboard.append(f"║ Başarılı (OK)        : {len(self.ok_items):<10} ✅ {f'({installment_count} taksit)':<28} ║")
        dashboard.append(f"║ Başarısız (FAILED)   : {len(self.failed_items):<10} ❌ {f'({len(self.failed_items)} hata)':<28} ║")
        dashboard.append(f"║ Şüpheli (FLAGGED)    : {len(self.flagged_items):<10} ⚠️ {f'({len(self.flagged_items)} kontrol)':<28} ║")
        dashboard.append(f"║ Pas Geçilen (SKIP)   : {len(self.skipped_items):<10} ▬ {f'({len(self.skipped_items)} kilit/pas)':<28} ║")
        dashboard.append("╠" + "═" * 63 + "╣")
        dashboard.append(f"║ Düşen Fiyatlar (▼)   : {len(self.price_drops):<43} ║")
        dashboard.append(f"║ Artan Fiyatlar (▲)   : {len(self.price_increases):<43} ║")
        dashboard.append(f"║ Toplam Geçen Süre    : {duration_str:<43} ║")
        dashboard.append("╚" + "═" * 63 + "╝")
        
        for line in dashboard:
            print(line)
            self.logger.info(line)
            
        for row, old_p, new_p in self.price_drops:
            diff = old_p - new_p
            pct = (diff / old_p) * 100
            alert = f"🔔 FİYAT DÜŞÜŞÜ: {row.product} | {row.seller} -> Fiyat {old_p} ₺ iken {new_p} ₺ oldu! (-%{pct:.1f} indirim!)"
            print(f"\033[92m{alert}\033[0m")
            self.logger.success(alert)
            
        for row, old_p, new_p in self.price_increases:
            diff = new_p - old_p
            pct = (diff / old_p) * 100
            alert = f"⚠️ FİYAT ARTIŞI: {row.product} | {row.seller} -> Fiyat {old_p} ₺ iken {new_p} ₺ oldu! (+%{pct:.1f} zam!)"
            print(f"\033[91m{alert}\033[0m")
            self.logger.warning(alert)
            
        summary_msg = (
            f"🤖 **Fiyat Botu Tarama Özeti**\n"
            f"✅ Başarılı: {len(self.ok_items)} | ❌ Hata: {len(self.failed_items)} | ⚠️ Şüpheli: {len(self.flagged_items)}\n"
            f"📉 Fiyatı Düşenler: {len(self.price_drops)} | 📈 Fiyatı Artanlar: {len(self.price_increases)}\n"
            f"⏱️ Süre: {duration_str}"
        )
        if self.price_drops:
            summary_msg += "\n\n🔥 **Fiyatı Düşen Ürünler:**"
            for row, old_p, new_p in self.price_drops[:5]:
                pct = ((old_p - new_p) / old_p) * 100
                summary_msg += f"\n- {row.product} ({row.seller}): {old_p} ₺ -> **{new_p} ₺** (-%{pct:.1f})"
                
        if self.price_increases:
            summary_msg += "\n\n📈 **Fiyatı Artan Ürünler:**"
            for row, old_p, new_p in self.price_increases[:5]:
                pct = ((new_p - old_p) / old_p) * 100
                summary_msg += f"\n- {row.product} ({row.seller}): {old_p} ₺ -> **{new_p} ₺** (+%{pct:.1f})"
                
        self._send_notification(summary_msg)

    def print_status(self) -> None:
        self.excel.load()
        sources = self.excel.read_sources()
        catalog = self.excel.read_catalog()
        
        total_sources = len(sources)
        active_sources = sum(1 for s in sources if s.active)
        locked_sources = sum(1 for s in sources if s.locked)
        failed_sources = sum(1 for s in sources if s.status == "FAILED")
        flagged_sources = sum(1 for s in sources if s.status == "FLAGGED")
        
        last_updated = "Bilinmiyor"
        for s in sources:
            if s.updated:
                date_str = s.updated.strftime("%Y-%m-%d %H:%M:%S") if isinstance(s.updated, datetime) else str(s.updated)
                if last_updated == "Bilinmiyor" or date_str > last_updated:
                    last_updated = date_str
                    
        print("╔" + "═" * 63 + "╗")
        print("║" + "📊 FİYAT BOTU DURUM RAPORU".center(63) + "║")
        print("╠" + "═" * 63 + "╣")
        print(f"║ Toplam Kaynak Linki  : {total_sources:<43} ║")
        print(f"║ Aktif Link Sayısı    : {active_sources:<43} ║")
        print(f"║ Kilitli Link Sayısı  : {locked_sources:<43} ║")
        print(f"║ Hatalı Linkler       : {failed_sources:<43} ║")
        print(f"║ Şüpheli/Bayraklı     : {flagged_sources:<43} ║")
        print(f"║ Katalog Ürün Sayısı  : {len(catalog):<43} ║")
        print(f"║ Son Güncelleme       : {str(last_updated):<43} ║")
        print("╚" + "═" * 63 + "╝")

    def add_product_interactive(self) -> None:
        self.excel.load()
        print("\n💡 Yeni Ürün Linki Ekleme Ekranı")
        
        catalog = self.excel.read_catalog()
        prod_names = sorted(list(set(c.product for c in catalog if c.product)))
        
        print("\nMevcut Katalog Ürünleri:")
        for idx, name in enumerate(prod_names[:15], 1):
            print(f" [{idx}] {name}")
        if len(prod_names) > 15:
            print(f" ... ve {len(prod_names) - 15} adet daha.")
            
        prod_choice = input("\nBir katalog ürünü seçin (No girin) veya yeni bir ürün adı yazın: ").strip()
        product = ""
        category = ""
        
        if prod_choice.isdigit():
            idx = int(prod_choice) - 1
            if 0 <= idx < len(prod_names):
                product = prod_names[idx]
                for c in catalog:
                    if c.product == product:
                        category = c.category
                        break
        else:
            product = prod_choice
            
        if not product:
            print("❌ Geçersiz ürün adı.")
            return
            
        if not category:
            category = input("Çeşit / Kategori girin (örn: İşlemci, Ekran Kartı): ").strip()
            
        link = input("Ürün URL/Link girin: ").strip()
        if not link.startswith("http"):
            print("❌ Geçersiz URL.")
            return
            
        seller = self.scraper._get_domain(link)
        for cfg_domain, cfg in self.site_configs.items():
            if seller.endswith(cfg_domain):
                seller = cfg.get("seller_name", seller)
                break
                
        # Kaynaklar'a ekle
        ws = self.excel.wb[self.excel.sources_sheet_name]
        cols = self.config.get("workbook", {}).get("sources_columns", {})
        
        header_map = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val: header_map[val] = c
            
        r = ws.max_row + 1
        ws.cell(row=r, column=header_map[cols["product"]], value=product)
        ws.cell(row=r, column=header_map[cols["category"]], value=category)
        ws.cell(row=r, column=header_map[cols["seller"]], value=seller)
        ws.cell(row=r, column=header_map[cols["link"]], value=link)
        ws.cell(row=r, column=header_map[cols["active"]], value="Evet")
        ws.cell(row=r, column=header_map[cols["lock"]], value="Hayır")
        
        # Katalog'da yoksa ekle
        if product not in prod_names:
            c_ws = self.excel.wb[self.excel.catalog_sheet_name]
            c_cols = self.config.get("workbook", {}).get("catalog_columns", {})
            c_header_map = {}
            for c in range(1, c_ws.max_column + 1):
                val = c_ws.cell(row=1, column=c).value
                if val: c_header_map[val] = c
                
            cr = c_ws.max_row + 1
            c_ws.cell(row=cr, column=c_header_map[c_cols["product"]], value=product)
            c_ws.cell(row=cr, column=c_header_map[c_cols["category"]], value=category)
            search_term = self.config.get("matching", {}).get("search_term_map", {}).get(product, f"{category} {product}")
            c_ws.cell(row=cr, column=c_header_map[c_cols["search_term"]], value=search_term)
            
        self.excel.add_data_validation_to_sources()
        self.excel.save()
        print(f"\n✅ Ürün başarıyla eklendi! Satır No: {r} | Satıcı: {seller}")

    def generate_html_report(self) -> None:
        self.excel.load()
        sources = self.excel.read_sources()
        catalog = self.excel.read_catalog()
        
        ok_count = sum(1 for s in sources if s.status == "OK")
        failed_count = sum(1 for s in sources if s.status == "FAILED")
        flagged_count = sum(1 for s in sources if s.status == "FLAGGED")
        skipped_count = sum(1 for s in sources if not s.active or s.locked)
        
        last_updated = "Bilinmiyor"
        for s in sources:
            if s.updated:
                date_str = s.updated.strftime("%Y-%m-%d %H:%M:%S") if isinstance(s.updated, datetime) else str(s.updated)
                if last_updated == "Bilinmiyor" or date_str > last_updated:
                    last_updated = date_str
                    
        # Fiyat geçmişi verisini yükle
        history_data = defaultdict(list)
        if self.excel.history_sheet_name in self.excel.wb.sheetnames:
            h_ws = self.excel.wb[self.excel.history_sheet_name]
            for r in range(2, h_ws.max_row + 1):
                prod = h_ws.cell(row=r, column=1).value
                seller = h_ws.cell(row=r, column=2).value
                price = h_ws.cell(row=r, column=3).value
                date_str = h_ws.cell(row=r, column=4).value
                if prod and price and date_str:
                    parsed_p = parse_price(price, self.config)
                    if parsed_p is not None:
                        history_data[str(prod).strip()].append({
                            "seller": str(seller),
                            "price": parsed_p,
                            "date": str(date_str)
                        })
                    
        # Katalog satırları tablosunu oluştur
        catalog_table_rows = ""
        for c in catalog:
            trend_icon = "▬"
            trend_color = "text-gray-400"
            if c.trend == "▲":
                trend_icon = "▲"
                trend_color = "text-red-500 font-bold"
            elif c.trend == "▼":
                trend_icon = "▼"
                trend_color = "text-green-500 font-bold"
                
            parsed_price = parse_price(c.best_price, self.config)
            price_str = f"{parsed_price:,.2f} ₺" if parsed_price is not None else "Bulunamadı"
            link_html = f'<a href="{c.best_link}" target="_blank" class="text-blue-400 hover:underline">Satıcı Git</a>' if c.best_link else "-"
            
            catalog_table_rows += f"""
            <tr class="border-b border-gray-700 hover:bg-gray-700/50 transition cursor-pointer" onclick="showChart('{c.product}')">
                <td class="p-3 text-white font-medium">{c.product}</td>
                <td class="p-3 text-gray-300">{c.category}</td>
                <td class="p-3 text-white font-bold">{price_str}</td>
                <td class="p-3 text-gray-300">{c.best_seller or "-"}</td>
                <td class="p-3 {trend_color}">{trend_icon}</td>
                <td class="p-3">{link_html}</td>
            </tr>
            """
            
        # Başarısız/Hatalı linkler tablosu
        failed_table_rows = ""
        for s in sources:
            if s.status == "FAILED":
                failed_table_rows += f"""
                <tr class="border-b border-gray-700 hover:bg-gray-700/50 transition">
                    <td class="p-3 text-red-400 font-medium">{s.product}</td>
                    <td class="p-3 text-gray-300">{s.seller}</td>
                    <td class="p-3"><a href="{s.link}" target="_blank" class="text-blue-400 hover:underline">Linke Git</a></td>
                </tr>
                """
        if not failed_table_rows:
            failed_table_rows = '<tr><td colspan="3" class="p-3 text-center text-gray-500">Hatalı ürün bulunmamaktadır.</td></tr>'

        # HTML Şablonu
        html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fiyat Takip Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            background-color: #0f172a;
            color: #f1f5f9;
        }}
    </style>
</head>
<body class="p-6 md:p-12">
    <div class="max-w-7xl mx-auto space-y-8">
        
        <!-- Header -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-6 space-y-4 md:space-y-0">
            <div>
                <h1 class="text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
                    🤖 PC Fiyat Takip Dashboard
                </h1>
                <p class="text-gray-400 mt-1">Sisteminiz için en ucuz parça fiyatları ve geçmiş takibi</p>
            </div>
            <div class="text-right">
                <span class="text-xs text-gray-500 block uppercase tracking-wider font-semibold">Son Tarama Tarihi</span>
                <span class="text-sm font-mono text-blue-400 bg-blue-950/50 px-3 py-1.5 rounded border border-blue-900/50 inline-block mt-1">{last_updated}</span>
            </div>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <div class="bg-gray-800/40 border border-gray-700/60 rounded-xl p-5 backdrop-blur">
                <span class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Katalog Ürün Sayısı</span>
                <div class="text-3xl font-bold text-white mt-1">{len(catalog)}</div>
            </div>
            <div class="bg-gray-800/40 border border-gray-700/60 rounded-xl p-5 backdrop-blur">
                <span class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Taranan Kaynak Link</span>
                <div class="text-3xl font-bold text-white mt-1">{len(sources)}</div>
            </div>
            <div class="bg-green-950/20 border border-green-900/40 rounded-xl p-5 backdrop-blur">
                <span class="text-xs font-semibold text-green-400 uppercase tracking-wider">Başarılı Linkler</span>
                <div class="text-3xl font-bold text-green-400 mt-1">{ok_count}</div>
            </div>
            <div class="bg-red-950/20 border border-red-900/40 rounded-xl p-5 backdrop-blur">
                <span class="text-xs font-semibold text-red-400 uppercase tracking-wider">Hatalı / Şüpheli</span>
                <div class="text-3xl font-bold text-red-400 mt-1">{failed_count + flagged_count}</div>
            </div>
        </div>

        <!-- Interactive Chart & Table -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <!-- Katalog Tablosu (2/3 Genişlik) -->
            <div class="lg:col-span-2 bg-gray-800/30 border border-gray-700/50 rounded-xl p-6 overflow-hidden">
                <h2 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    📋 Katalog Fiyat Listesi
                </h2>
                <div class="overflow-x-auto max-h-[500px]">
                    <table class="w-full text-left border-collapse text-sm">
                        <thead>
                            <tr class="bg-gray-800/80 text-gray-400 uppercase text-xs tracking-wider border-b border-gray-700">
                                <th class="p-3">Ürün</th>
                                <th class="p-3">Çeşit</th>
                                <th class="p-3">Fiyat</th>
                                <th class="p-3">Satıcı</th>
                                <th class="p-3">Trend</th>
                                <th class="p-3">Aksiyon</th>
                            </tr>
                        </thead>
                        <tbody>
                            {catalog_table_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Sağ Panel: Grafik & Hatalı Linkler -->
            <div class="space-y-8">
                <!-- Grafik -->
                <div id="chartContainer" class="bg-gray-800/30 border border-gray-700/50 rounded-xl p-6 hidden">
                    <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        📈 <span id="chartProductTitle">Fiyat Geçmişi</span>
                    </h2>
                    <canvas id="priceChart" class="w-full"></canvas>
                </div>
                
                <div class="bg-gray-800/30 border border-gray-700/50 rounded-xl p-6">
                    <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        ❌ Hatalı Taramalar
                    </h2>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm">
                            <thead>
                                <tr class="text-gray-400 text-xs border-b border-gray-700">
                                    <th class="pb-2">Ürün</th>
                                    <th class="pb-2">Satıcı</th>
                                    <th class="pb-2">Aksiyon</th>
                                </tr>
                            </thead>
                            <tbody>
                                {failed_table_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
        </div>
        
    </div>

    <script>
        const historyData = {json.dumps(history_data, ensure_ascii=False)};
        let activeChart = null;

        function showChart(productName) {{
            const data = historyData[productName];
            if (!data || data.length === 0) {{
                alert("Bu ürün için henüz geçmiş fiyat verisi toplanmamış.");
                return;
            }}

            document.getElementById("chartContainer").classList.remove("hidden");
            document.getElementById("chartProductTitle").textContent = productName.substring(0, 30) + "... Geçmişi";

            // Sırala tarihe göre
            data.sort((a, b) => new Date(a.date) - new Date(b.date));

            const labels = data.map(item => item.date.substring(5, 16)); // MM-DD HH:MM
            const prices = data.map(item => item.price);

            const ctx = document.getElementById('priceChart').getContext('2d');
            
            if (activeChart) {{
                activeChart.destroy();
            }}

            activeChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: 'Fiyat (₺)',
                        data: prices,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.2,
                        fill: true
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{
                            grid: {{ color: '#334155' }},
                            ticks: {{ color: '#94a3b8' }}
                        }},
                        x: {{
                            grid: {{ display: false }},
                            ticks: {{ color: '#94a3b8' }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ display: false }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>"""
        
        # Kaydet
        report_path = os.path.join(self.reports_dir, "dashboard.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        self.logger.info(f"HTML Fiyat Raporu başarıyla oluşturuldu: {report_path}")
        print(f"✅ HTML Raporu oluşturuldu: {report_path}")


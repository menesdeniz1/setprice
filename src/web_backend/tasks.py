# -*- coding: utf-8 -*-
import os
import time
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session
from celery import Celery

from src.config_loader import ConfigLoader
from src.scraper import Scraper
from src.akakce import AkakceSearcher
from src.price_parser import should_skip_price
from src.logger import setup_logger

from .database import SessionLocal
from . import models, crud, schemas
from .similarity_utils import classify_match

ALTERNATIVES_TOP_N = 6

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)


def _sync_akakce_alternatives(db, akakce, logger, terms_map, name_by_id):
    """terms_map: arama_terimi -> [library_product_id, ...]
    name_by_id: library_product_id -> ürün adı

    Akakçe'de arayıp sonuçları başlık benzerliğine göre 'same_product'
    (muhtemelen aynı ürün, farklı satıcı) / 'similar' (spec bazlı muadil)
    olarak etiketleyip her ürün için senkronize eder.

    Not: search_batch() List[AlternativeRow] döner (CLI/Excel botunun da
    kullandığı paylaşılan tip) — dict değil; önceki sürüm bunu yanlışlıkla
    dict gibi kullanıyordu ve her çağrıda sessizce AttributeError atıyordu.
    """
    if not terms_map:
        return
    try:
        terms_payload = {
            term: [name_by_id[lp_id] for lp_id in lp_ids if lp_id in name_by_id]
            for term, lp_ids in terms_map.items()
        }
        id_by_name = {name: lp_id for lp_id, name in name_by_id.items()}

        rows = akakce.search_batch(terms_payload, top_n=ALTERNATIVES_TOP_N)

        grouped = defaultdict(list)
        for row in rows:
            grouped[row.product].append(row)

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
            crud.sync_alternatives(db, lp_id, alt_schemas)
    except Exception as e:
        logger.error(f"Akakçe araması sırasında hata: {e}")

def run_set_scan(set_id: int):
    """Verilen set kimliğine ait tüm ürünleri sırayla tarar."""
    db: Session = SessionLocal()
    
    # Config & Logger Yükle
    config_loader = ConfigLoader()
    config = config_loader.load()
    logger = setup_logger(config)
    
    db_set = db.query(models.ProductSet).filter(models.ProductSet.id == set_id).first()
    if not db_set:
        logger.error(f"Set bulunamadı: ID={set_id}")
        db.close()
        return
        
    set_name = db_set.name  # döngüdeki commit()'ler attribute'ları expire eder; session kapanmadan önce sabitle
    logger.info(f"[Web Scan] Set taraması başladı: {set_name}")

    # Scraper ve Akakçe nesnelerini yükle
    site_configs = config_loader.load_site_configs()
    scraper = Scraper(config, site_configs, logger)
    akakce = AkakceSearcher(config, logger)
    
    # Aktif ve kilitli olmayan ürünleri getir
    products = db.query(models.Product).filter(
        models.Product.set_id == set_id,
        models.Product.is_active == True,
        models.Product.is_locked == False
    ).all()
    
    # Domainlerine göre grupla (round-robin beklemesi için)
    # Basitlik için sıralı tarayalım, scraper zaten beklemeyi domain bazlı yapıyor
    for prod in products:
        lib_prod = prod.library_product
        if not lib_prod:
            continue
            
        url = lib_prod.original_link
        domain = scraper._get_domain(url)
        site_cfg = site_configs.get(domain, {})
        
        logger.info(f"[Web Scan] Taranıyor: {lib_prod.name} | Site: {domain}")
        
        # HTML Çek
        html = None
        render_required = site_cfg.get("render", False)
        
        try:
            if render_required:
                html = scraper._fetch_playwright(url)
            else:
                html = scraper._fetch_requests(url)
                
            if not html or html in ["403_FORBIDDEN", "429_TOO_MANY_REQUESTS"]:
                # Fallback dene
                html = scraper._fetch_cloudscraper(url)
                if not html and render_required:
                    html = scraper._fetch_playwright(url)
        except Exception as e:
            logger.warning(f"URL çekilirken hata oluştu ({url[:40]}): {e}")
            
        # Fiyat Çıkar
        new_price = scraper.extract_price(html, site_cfg)
        
        # Taksit kontrolü
        installment = None
        if html and "n11.com" in url:
            import re
            taksit_match = re.search(r'(\d+)\s*Taksit', html)
            if taksit_match:
                installment = f"{taksit_match.group(1)} Taksit"
                
        # Rating & Review Count
        rating, review_count = scraper.extract_rating_info(html)
        if rating is not None:
            lib_prod.rating = rating
        if review_count is not None:
            lib_prod.review_count = review_count
                
        # Güncelleme
        if new_price is not None:
            # Fiyat limit kontrolü
            skip, reason = should_skip_price(new_price, config)
            if skip:
                lib_prod.status = "FLAGGED"
                logger.warning(f"[FLAG] Olağandışı fiyat ({lib_prod.name}): {new_price} | Sebep: {reason}")
            else:
                # Başarılı güncelleme
                old_price = lib_prod.current_price
                lib_prod.current_price = new_price
                lib_prod.current_seller = scraper._infer_seller(url)
                lib_prod.current_installment = installment
                lib_prod.status = "OK"
                
                # Fiyat geçmişine ekle (Eğer fiyat değiştiyse)
                if old_price != new_price:
                    crud.add_price_history(db, lib_prod.id, new_price, lib_prod.current_seller)
                    logger.info(f"[Web Scan] Fiyat değişti: {lib_prod.name} -> {new_price} ₺")
        else:
            lib_prod.status = "FAILED"
            logger.error(f"[Web Scan] Fiyat bulunamadı: {lib_prod.name}")

        crud.record_domain_health(db, domain, success=(lib_prod.status == "OK"))
        lib_prod.updated_at = datetime.utcnow()
        db.commit()

    # Akakçe Muadilleri Ara
    logger.info("[Web Scan] Akakçe muadilleri aranıyor...")
    terms_map = defaultdict(list)
    name_by_id = {}
    for prod in products:
        lib_prod = prod.library_product
        if lib_prod and lib_prod.status == "OK":
            search_term = akakce._infer_search_term(lib_prod.name, lib_prod.category)
            if search_term:
                terms_map[search_term].append(lib_prod.id)
                name_by_id[lib_prod.id] = lib_prod.name

    _sync_akakce_alternatives(db, akakce, logger, terms_map, name_by_id)

    # Karar Motoru sinyallerini güncelle (alternatifler senkronize edildikten sonra,
    # böylece value_score güncel benchmark_price'ı kullanır)
    lib_ids = list({prod.library_product_id for prod in products if prod.library_product})
    if lib_ids:
        logger.info(f"[Web Scan] Karar motoru sinyalleri güncelleniyor ({len(lib_ids)} ürün)...")
        crud.update_decision_signals(db, lib_ids)

    scraper.close()
    akakce.close()
    db.close()
    logger.info(f"[Web Scan] Set taraması tamamlandı: {set_name}")

@celery_app.task
def scan_product_set_celery_task(set_id: int):
    run_set_scan(set_id)

def run_library_scan(lib_product_id: int = None, user_id: int = None):
    """Kütüphanedeki tek bir ürünü, bir kullanıcının tüm ürünlerini veya tüm ürünleri tarar."""
    db: Session = SessionLocal()
    config_loader = ConfigLoader()
    config = config_loader.load()
    logger = setup_logger(config)
    
    if lib_product_id:
        lib_prods = db.query(models.LibraryProduct).filter(models.LibraryProduct.id == lib_product_id).all()
        logger.info(f"[Library Scan] Tekli ürün taraması başladı: ID={lib_product_id}")
    elif user_id:
        lib_prods = db.query(models.LibraryProduct).filter(models.LibraryProduct.user_id == user_id).all()
        logger.info(f"[Library Scan] Kullanıcı ({user_id}) toplu kütüphane taraması başladı ({len(lib_prods)} ürün)")
    else:
        lib_prods = db.query(models.LibraryProduct).all()
        logger.info(f"[Library Scan] Toplu kütüphane taraması başladı ({len(lib_prods)} ürün)")
        
    site_configs = config_loader.load_site_configs()
    scraper = Scraper(config, site_configs, logger)
    akakce = AkakceSearcher(config, logger)

    terms_map = defaultdict(list)
    name_by_id = {}

    for lib_prod in lib_prods:
        url = lib_prod.original_link
        if not url: continue
        
        domain = scraper._get_domain(url)
        site_cfg = site_configs.get(domain, {})
        
        logger.info(f"[Library Scan] Taranıyor: {lib_prod.name} | Site: {domain}")
        
        html = None
        render_required = site_cfg.get("render", False)
        
        try:
            if render_required:
                html = scraper._fetch_playwright(url)
            else:
                html = scraper._fetch_requests(url)
                
            if not html or html in ["403_FORBIDDEN", "429_TOO_MANY_REQUESTS"]:
                html = scraper._fetch_cloudscraper(url)
                if not html and render_required:
                    html = scraper._fetch_playwright(url)
        except Exception as e:
            logger.warning(f"URL çekilirken hata oluştu ({url[:40]}): {e}")
            
        new_price = scraper.extract_price(html, site_cfg)
        
        installment = None
        if html and "n11.com" in url:
            import re
            taksit_match = re.search(r'(\d+)\s*Taksit', html)
            if taksit_match:
                installment = f"{taksit_match.group(1)} Taksit"
                
        # Rating & Review Count
        rating, review_count = scraper.extract_rating_info(html)
        if rating is not None:
            lib_prod.rating = rating
        if review_count is not None:
            lib_prod.review_count = review_count
                
        if new_price is not None:
            skip, reason = should_skip_price(new_price, config)
            if skip:
                lib_prod.status = "FLAGGED"
            else:
                old_price = lib_prod.current_price
                lib_prod.current_price = new_price
                lib_prod.current_seller = scraper._infer_seller(url)
                lib_prod.current_installment = installment
                lib_prod.status = "OK"
                
                if old_price != new_price:
                    crud.add_price_history(db, lib_prod.id, new_price, lib_prod.current_seller)
        else:
            lib_prod.status = "FAILED"

        crud.record_domain_health(db, domain, success=(lib_prod.status == "OK"))
        lib_prod.updated_at = datetime.utcnow()
        db.commit()

        # Akakçe için hazırla
        if lib_prod.status == "OK":
            search_term = akakce._infer_search_term(lib_prod.name, lib_prod.category)
            if search_term:
                terms_map[search_term].append(lib_prod.id)
                name_by_id[lib_prod.id] = lib_prod.name

    _sync_akakce_alternatives(db, akakce, logger, terms_map, name_by_id)

    # Karar Motoru sinyallerini güncelle
    lib_ids = [lp.id for lp in lib_prods]
    if lib_ids:
        logger.info(f"[Library Scan] Karar motoru sinyalleri güncelleniyor ({len(lib_ids)} ürün)...")
        crud.update_decision_signals(db, lib_ids)

    scraper.close()
    akakce.close()
    db.close()
    logger.info("[Library Scan] Tarama tamamlandı")


@celery_app.task
def periodic_library_scan_celery_task():
    run_library_scan()


def run_ai_decisions():
    """Tüm kütüphane ürünleri için AI karar motorunu çalıştırır. Fiyatları
    yeniden çekmez — sadece DB'deki güncel fiyat/geçmiş üzerinden karar
    üretir. Günde bir kez çalışacak şekilde tasarlandı (ücretsiz API
    kotalarını korumak için)."""
    db: Session = SessionLocal()
    config_loader = ConfigLoader()
    logger = setup_logger(config_loader.load())

    lib_ids = [lp.id for lp in db.query(models.LibraryProduct).all()]
    if lib_ids:
        logger.info(f"[AI Decisions] Günlük AI karar üretimi başladı ({len(lib_ids)} ürün)...")
        crud.update_ai_decisions(db, lib_ids)
        logger.info("[AI Decisions] Günlük AI karar üretimi tamamlandı")

    db.close()


@celery_app.task
def daily_ai_decision_task():
    run_ai_decisions()


# USE_CELERY=true ise periyodik kütüphane taraması Celery Beat üzerinden
# çalışır (bu, ayrı bir `celery -A src.web_backend.tasks beat` process'i
# gerektirir). USE_CELERY kapalıysa main.py'deki asyncio tabanlı döngü
# devrede kalır — Redis/Celery kurulmadan da sıfır ek altyapıyla çalışsın diye.
if os.environ.get("USE_CELERY", "false").lower() == "true":
    celery_app.conf.beat_schedule = {
        "periodic-library-scan": {
            "task": "src.web_backend.tasks.periodic_library_scan_celery_task",
            "schedule": 600.0,  # 10 dakika
        },
        "daily-ai-decisions": {
            "task": "src.web_backend.tasks.daily_ai_decision_task",
            "schedule": 86400.0,  # 24 saat
        },
    }

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
from . import models, crud

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

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
        
    logger.info(f"[Web Scan] Set taraması başladı: {db_set.name}")
    
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
            
        lib_prod.updated_at = datetime.utcnow()
        db.commit()
        
    # Akakçe Muadilleri Ara
    logger.info("[Web Scan] Akakçe muadilleri aranıyor...")
    terms_map = defaultdict(list)
    for prod in products:
        lib_prod = prod.library_product
        if lib_prod and lib_prod.status == "OK":
            search_term = akakce._infer_search_term(lib_prod.name, lib_prod.category)
            if search_term:
                terms_map[search_term].append(lib_prod.id)
                
    if terms_map:
        try:
            # terms_map values are library_product_ids
            alternatives = akakce.search_batch({term: [p.library_product.name for p in products if p.library_product_id in lp_ids] for term, lp_ids in terms_map.items()})
            for term, alts in alternatives.items():
                lp_ids = terms_map[term]
                for lp_id in lp_ids:
                    alt_schemas = [
                        schemas.AlternativeBase(
                            title=a["title"],
                            price=a["price"],
                            seller=a["seller"],
                            link=a["link"]
                        ) for a in alts
                    ]
                    crud.sync_alternatives(db, lp_id, alt_schemas)
        except Exception as e:
            logger.error(f"Akakçe araması sırasında hata: {e}")
            
    scraper.close()
    akakce.close()
    db.close()
    logger.info(f"[Web Scan] Set taraması tamamlandı: {db_set.name}")

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
            
        lib_prod.updated_at = datetime.utcnow()
        db.commit()
        
        # Akakçe için hazırla
        if lib_prod.status == "OK":
            search_term = akakce._infer_search_term(lib_prod.name, lib_prod.category)
            if search_term:
                terms_map[search_term].append(lib_prod.id)
                
    if terms_map:
        try:
            alternatives = akakce.search_batch({term: [] for term in terms_map.keys()})
            for term, alts in alternatives.items():
                lp_ids = terms_map[term]
                for lp_id in lp_ids:
                    from . import schemas
                    alt_schemas = [
                        schemas.AlternativeBase(
                            title=a["title"], price=a["price"], seller=a["seller"], link=a["link"]
                        ) for a in alts
                    ]
                    crud.sync_alternatives(db, lp_id, alt_schemas)
        except Exception as e:
            logger.error(f"Akakçe araması sırasında hata: {e}")
            
    scraper.close()
    akakce.close()
    db.close()
    logger.info("[Library Scan] Tarama tamamlandı")

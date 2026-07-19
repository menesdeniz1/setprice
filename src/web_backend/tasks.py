# -*- coding: utf-8 -*-
"""
Web Backend — Arka Plan Görevleri.
Artık kendi scraping mantığı yok — paylaşılan core orchestrator'ı kullanır.
"""
import os
import filelock
from datetime import datetime
from sqlalchemy.orm import Session
from celery import Celery

from src.core.config_loader import ConfigLoader
from src.core.scan_lock import get_scan_lock
from src.core.logger import setup_logger

from .database import SessionLocal
from . import models, crud

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)


def run_set_scan(set_id: int):
    """Verilen set kimliğine ait tüm ürünleri birleşik orchestrator ile tarar."""
    from src.core.orchestrator import Orchestrator

    db: Session = SessionLocal()
    config_loader = ConfigLoader()
    config = config_loader.load()
    logger = setup_logger(config)

    db_set = db.query(models.ProductSet).filter(models.ProductSet.id == set_id).first()
    if not db_set:
        logger.error(f"Set bulunamadı: ID={set_id}")
        db.close()
        return

    set_name = db_set.name
    logger.info(f"[Web Scan] Set taraması başladı: {set_name}")

    # Set'teki aktif ve kilitli olmayan ürünlerin library_product_id'lerini topla
    products = db.query(models.Product).filter(
        models.Product.set_id == set_id,
        models.Product.is_active == True,
        models.Product.is_locked == False
    ).all()

    lib_product_ids = list({prod.library_product_id for prod in products if prod.library_product})

    if not lib_product_ids:
        logger.warning(f"[Web Scan] Set'te taranacak ürün yok: {set_name}")
        db.close()
        return

    try:
        lock = get_scan_lock(timeout=10)
        with lock:
            orchestrator = Orchestrator(config, logger, db)
            orchestrator.run_once(
                user_id=db_set.user_id,
                lib_product_ids=lib_product_ids,
            )
    except filelock.Timeout:
        logger.warning("[Web Scan] Başka bir tarama çalışıyor, set taraması atlanıyor.")
    except Exception as e:
        logger.error(f"[Web Scan] Set tarama hatası: {e}")
    finally:
        db.close()

    logger.info(f"[Web Scan] Set taraması tamamlandı: {set_name}")


@celery_app.task
def scan_product_set_celery_task(set_id: int):
    run_set_scan(set_id)


def run_library_scan(lib_product_id: int = None, user_id: int = None):
    """Kütüphanedeki ürünleri birleşik orchestrator ile tarar."""
    from src.core.orchestrator import Orchestrator

    db: Session = SessionLocal()
    config_loader = ConfigLoader()
    config = config_loader.load()
    logger = setup_logger(config)

    # Taranacak ürünleri belirle
    lib_product_ids = None
    if lib_product_id:
        lib_product_ids = [lib_product_id]
        logger.info(f"[Library Scan] Tekli ürün taraması: ID={lib_product_id}")
    elif user_id:
        lib_prods = db.query(models.LibraryProduct).filter(models.LibraryProduct.user_id == user_id).all()
        lib_product_ids = [lp.id for lp in lib_prods]
        logger.info(f"[Library Scan] Kullanıcı taraması ({user_id}): {len(lib_product_ids)} ürün")
    else:
        logger.info("[Library Scan] Toplu kütüphane taraması")

    try:
        lock = get_scan_lock(timeout=10)
        with lock:
            orchestrator = Orchestrator(config, logger, db)
            orchestrator.run_once(
                user_id=user_id,
                lib_product_ids=lib_product_ids,
            )
    except filelock.Timeout:
        logger.warning("[Library Scan] Başka bir tarama çalışıyor, atlanıyor.")
    except Exception as e:
        logger.error(f"[Library Scan] Tarama hatası: {e}")
    finally:
        db.close()


@celery_app.task
def periodic_library_scan_celery_task():
    run_library_scan()


def run_ai_decisions():
    """Tüm kütüphane ürünleri için AI karar motorunu çalıştırır."""
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


# Celery Beat schedule
if os.environ.get("USE_CELERY", "false").lower() == "true":
    celery_app.conf.beat_schedule = {
        "periodic-library-scan": {
            "task": "src.web_backend.tasks.periodic_library_scan_celery_task",
            "schedule": 600.0,
        },
        "daily-ai-decisions": {
            "task": "src.web_backend.tasks.daily_ai_decision_task",
            "schedule": 86400.0,
        },
    }

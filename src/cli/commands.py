# -*- coding: utf-8 -*-
"""
SetPrice CLI — Komut fonksiyonları.
main.py'deki argparse komutları bu fonksiyonları çağırır.
"""
import os
import time
import filelock
from datetime import datetime

from src.core.config_loader import ConfigLoader
from src.core.database import get_db_session, init_db
from src.core.scan_lock import get_scan_lock


def _ensure_db():
    """DB tablolarının oluşturulduğundan emin ol."""
    init_db()
    # ScanCheckpoint gibi yeni modeller için import gerekli
    from src.web_backend import models  # noqa: F401
    init_db()


def _get_or_create_admin_user(db):
    """CLI admin kullanıcısını getir veya oluştur."""
    from src.web_backend import models, crud

    admin_email = "admin@setprice.bot"
    user = crud.get_user_by_email(db, admin_email)
    if not user:
        from src.web_backend.schemas import UserCreate
        password = os.environ.get("SETPRICE_INITIAL_ADMIN_PASSWORD", "")
        if len(password) < 16:
            raise RuntimeError("Set SETPRICE_INITIAL_ADMIN_PASSWORD to a unique password of at least 16 characters before creating the admin account.")
        user = crud.create_user(db, UserCreate(email=admin_email, password=password))
        print(f"Admin kullanıcısı oluşturuldu: {admin_email}")
    return user


def cmd_once(config: dict, logger, args) -> dict:
    """--once komutu: tek seferlik tarama."""
    from src.core.orchestrator import Orchestrator

    _ensure_db()
    db = get_db_session()

    try:
        user = _get_or_create_admin_user(db)

        lock = get_scan_lock(timeout=30)
        try:
            with lock:
                orchestrator = Orchestrator(config, logger, db)
                result = orchestrator.run_once(
                    user_id=user.id,
                    dry_run=getattr(args, 'dry_run', False),
                    force=getattr(args, 'force', False),
                )
                return result
        except filelock.Timeout:
            logger.warning("Başka bir tarama zaten çalışıyor! Lütfen bekleyin.")
            return {"status": "locked", "message": "Başka bir tarama çalışıyor"}
    finally:
        db.close()


def cmd_watch(config: dict, logger, args) -> None:
    """--watch komutu: belirli aralıklarla sürekli tarama."""
    interval = getattr(args, 'interval', 60)
    logger.info(f"İzleme modu başlatılıyor (her {interval} dakikada bir)...")

    while True:
        try:
            result = cmd_once(config, logger, args)
            logger.info(f"Tarama tamamlandı: {result}")
        except Exception as e:
            logger.error(f"Tarama hatası: {e}")

        logger.info(f"Sonraki tarama {interval} dakika sonra...")
        time.sleep(interval * 60)


def cmd_status(config: dict, logger) -> None:
    """--status komutu: durum bilgisi."""
    from src.core.orchestrator import Orchestrator

    _ensure_db()
    db = get_db_session()

    try:
        user = _get_or_create_admin_user(db)
        orchestrator = Orchestrator(config, logger, db)
        orchestrator.print_status(user_id=user.id)
    finally:
        db.close()


def cmd_import_excel(config: dict, logger, args) -> dict:
    """--import-excel komutu: Excel'den DB'ye toplu aktarım."""
    from src.cli.excel_bridge import ExcelImporter

    _ensure_db()
    db = get_db_session()

    try:
        user = _get_or_create_admin_user(db)

        excel_path = getattr(args, 'excel_path', None) or config.get("paths", {}).get("workbook")
        if not excel_path:
            logger.error("Excel dosya yolu bulunamadı. --excel-path ile belirtin veya config.yaml'da ayarlayın.")
            return {"status": "error"}

        if not os.path.exists(excel_path):
            logger.error(f"Excel dosyası bulunamadı: {excel_path}")
            return {"status": "error"}

        importer = ExcelImporter(config, logger)
        result = importer.import_from_excel(excel_path, db, user.id)
        logger.info(f"Import sonucu: {result}")
        return result
    finally:
        db.close()


def cmd_export_excel(config: dict, logger, args) -> None:
    """--export-excel komutu: DB'den Excel'e manuel export."""
    from src.cli.excel_bridge import ExcelExporter

    _ensure_db()
    db = get_db_session()

    try:
        user = _get_or_create_admin_user(db)

        excel_path = getattr(args, 'excel_path', None) or config.get("paths", {}).get("workbook")
        if not excel_path:
            logger.error("Excel dosya yolu bulunamadı.")
            return

        exporter = ExcelExporter(config, logger)
        exporter.export_to_excel(excel_path, db, user.id)
        logger.info(f"Excel güncellendi: {excel_path}")
    finally:
        db.close()


def cmd_migrate(config: dict, logger, args) -> None:
    """--migrate komutu: Eski Excel yapısını yeni DB yapısına göç ettir."""
    from src.cli.migration import Migration

    _ensure_db()

    # Önce eski migration'ı çalıştır (Excel sayfalarını oluşturur)
    migration = Migration(config, logger)
    migration.run()

    # Sonra Excel'den DB'ye import et
    cmd_import_excel(config, logger, args)
    logger.info("Migration tamamlandı: Excel yapısı oluşturuldu ve veriler DB'ye aktarıldı.")

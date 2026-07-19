# -*- coding: utf-8 -*-
import sys
import io
import traceback
import argparse

# Force UTF-8 encoding for standard streams
if hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except:
        pass
if hasattr(sys.stderr, 'buffer'):
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

from src.core.config_loader import ConfigLoader
from src.core.logger import setup_logger


def main():
    parser = argparse.ArgumentParser(description="Fiyat Botu — Birleşik CLI")
    parser.add_argument("--migrate", action="store_true", help="Excel dosyasını yeni formata geçirir ve DB'ye aktarır")
    parser.add_argument("--apply-formulas", action="store_true", help="Migration sırasında setup formüllerini uygular")
    parser.add_argument("--once", action="store_true", help="Botu tek sefer çalıştırır (DB merkezli)")
    parser.add_argument("--watch", action="store_true", help="Botu sürekli izleme modunda çalıştırır")
    parser.add_argument("--interval", type=int, default=60, help="İzleme modunda bekleme süresi (dakika)")
    parser.add_argument("--dry-run", action="store_true", help="Değişiklikleri kaydetmeden çalıştırır")
    parser.add_argument("--force", action="store_true", help="Checkpoint'leri yok sayıp sıfırdan taze tarama yapar")
    parser.add_argument("--status", action="store_true", help="DB durum bilgisini gösterir")
    parser.add_argument("--import-excel", action="store_true", help="Excel'den DB'ye toplu ürün aktarır")
    parser.add_argument("--export-excel", action="store_true", help="DB'den Excel'e güncel verileri yazar")
    parser.add_argument("--excel-path", type=str, help="Excel dosya yolu (varsayılan: config'ten okunur)")
    
    args = parser.parse_args()
    
    valid_commands = [
        args.migrate, args.once, args.watch, args.status,
        args.import_excel, args.export_excel,
    ]
    if not any(valid_commands):
        parser.print_help()
        sys.exit(1)

    try:
        # Config yükle
        config_loader = ConfigLoader()
        config = config_loader.load()
        
        # Logger başlat
        logger = setup_logger(config)
        logger.info("Fiyat Botu başlatılıyor...")

        # Lazy import — CLI komutları
        from src.cli.commands import (
            cmd_once, cmd_watch, cmd_status,
            cmd_import_excel, cmd_export_excel, cmd_migrate,
        )
        
        # Komutları çalıştır
        if args.migrate:
            logger.info("=== MİGRASYON MODU ===")
            cmd_migrate(config, logger, args)
            
        elif args.once:
            logger.info("=== TEK SEFERLİK ÇALIŞTIRMA (DB Merkezli) ===")
            result = cmd_once(config, logger, args)
            logger.info(f"Çalıştırma sonucu: {result}")
            
        elif args.watch:
            logger.info(f"=== İZLEME MODU ({args.interval} dk) ===")
            cmd_watch(config, logger, args)

        elif args.status:
            logger.info("=== DURUM BİLGİSİ ===")
            cmd_status(config, logger)

        elif args.import_excel:
            logger.info("=== EXCEL → DB AKTARIMI ===")
            result = cmd_import_excel(config, logger, args)
            logger.info(f"Import sonucu: {result}")

        elif args.export_excel:
            logger.info("=== DB → EXCEL GÜNCELLEME ===")
            cmd_export_excel(config, logger, args)
            
    except Exception as e:
        print(f"\nBeklenmeyen bir hata oluştu: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

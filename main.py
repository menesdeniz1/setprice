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

from src.config_loader import ConfigLoader
from src.logger import setup_logger
from src.excel_handler import ExcelHandler
from src.migration import Migration
from src.orchestrator import Orchestrator

def main():
    parser = argparse.ArgumentParser(description="Fiyat Botu")
    parser.add_argument("--migrate", action="store_true", help="Excel dosyasını yeni formata geçirir")
    parser.add_argument("--apply-formulas", action="store_true", help="Migration sırasında setup formüllerini uygular")
    parser.add_argument("--once", action="store_true", help="Botu tek sefer çalıştırır")
    parser.add_argument("--watch", action="store_true", help="Botu sürekli izleme modunda çalıştırır")
    parser.add_argument("--interval", type=int, default=60, help="İzleme modunda bekleme süresi (dakika)")
    parser.add_argument("--alternatives-only", action="store_true", help="Sadece muadil (Akakçe) aramasını günceller")
    parser.add_argument("--dry-run", action="store_true", help="Değişiklikleri kaydetmeden çalıştırır")
    parser.add_argument("--force", action="store_true", help="Hafızayı (checkpoint) yok sayıp sıfırdan taze tarama yapar")
    parser.add_argument("--status", action="store_true", help="Excel veritabanı durumunu gösterir")
    parser.add_argument("--add-product", action="store_true", help="Etkileşimli CLI ile yeni ürün ekler")
    parser.add_argument("--html-report", action="store_true", help="HTML dashboard raporu üretir")
    
    args = parser.parse_args()
    
    if not any([args.migrate, args.once, args.watch, args.alternatives_only, args.status, args.add_product, args.html_report]):
        parser.print_help()
        sys.exit(1)

    try:
        # Config yükle
        config_loader = ConfigLoader()
        config = config_loader.load()
        
        # Logger başlat
        logger = setup_logger(config)
        logger.info("Fiyat Botu başlatılıyor...")
        
        # Komutları çalıştır
        if args.migrate:
            logger.info("=== MIGRATION MODU ===")
            excel = ExcelHandler(config, logger)
            excel.load()
            migration = Migration(excel, config, logger)
            result = migration.run(apply_formulas=args.apply_formulas, dry_run=args.dry_run)
            logger.info(f"Migration sonucu: {result}")
            
        elif args.once:
            logger.info("=== TEK SEFERLİK ÇALIŞTIRMA ===")
            orchestrator = Orchestrator(config, logger)
            result = orchestrator.run_once(dry_run=args.dry_run, force=args.force)
            logger.info(f"Çalıştırma sonucu: {result}")
            
        elif args.watch:
            logger.info(f"=== İZLEME MODU ({args.interval} dk) ===")
            orchestrator = Orchestrator(config, logger)
            orchestrator.run_watch(interval_min=args.interval)
            
        elif args.alternatives_only:
            logger.info("=== SADECE MUADİLLER ===")
            orchestrator = Orchestrator(config, logger)
            result = orchestrator.run_alternatives_only()
            logger.info(f"Sonuç: {result}")

        elif args.status:
            logger.info("=== DURUM BİLGİSİ ===")
            orchestrator = Orchestrator(config, logger)
            orchestrator.print_status()

        elif args.add_product:
            logger.info("=== YENİ ÜRÜN EKLEME ===")
            orchestrator = Orchestrator(config, logger)
            orchestrator.add_product_interactive()

        elif args.html_report:
            logger.info("=== HTML RAPORU OLUŞTURMA ===")
            orchestrator = Orchestrator(config, logger)
            orchestrator.generate_html_report()
            
    except Exception as e:
        print(f"\nBeklenmeyen bir hata oluştu: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

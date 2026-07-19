# -*- coding: utf-8 -*-
"""
Excel Bridge — DB ↔ Excel import/export köprüsü.

Import: Mevcut pc_setup.xlsx'ten ürünleri DB'ye aktarır.
Export: DB'den güncel verileri alıp Excel sayfalarını günceller.
"""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from src.core.config_loader import ConfigLoader
from src.core.price_parser import parse_price


class ExcelImporter:
    """Excel'den DB'ye ürün aktarımı."""

    def __init__(self, config: dict, logger):
        self.config = config
        self.logger = logger

    def import_from_excel(self, excel_path: str, db: Session, user_id: int) -> dict:
        """Mevcut pc_setup.xlsx'ten ürünleri DB'ye aktarır.
        Setup sayfalarından linkleri okur, LibraryProduct olarak DB'ye yazar.
        Çakışma kontrolü: aynı link varsa güncelle, yoksa ekle.
        """
        from src.cli.excel_handler import ExcelHandler
        from src.web_backend import models, crud

        excel = ExcelHandler(self.config, self.logger)
        excel.workbook_path = excel_path
        excel.load()

        site_configs = ConfigLoader().load_site_configs()
        skip_patterns = self.config.get("migration", {}).get("skip_product_patterns", [])
        start_row = self.config.get("migration", {}).get("data_start_row", 5)

        imported = 0
        updated = 0
        skipped = 0

        for sheet_name in excel.wb.sheetnames:
            if sheet_name in excel.writable_sheets:
                continue

            ws = excel.wb[sheet_name]
            for r in range(start_row, ws.max_row + 1):
                cat = ws.cell(row=r, column=2).value
                prod = ws.cell(row=r, column=3).value
                price = ws.cell(row=r, column=4).value
                link = ws.cell(row=r, column=6).value

                if not prod and not link:
                    continue

                prod_str = str(prod).strip() if prod else ""
                if any(p.lower() in prod_str.lower() for p in skip_patterns):
                    continue

                if not link or str(link).startswith("="):
                    skipped += 1
                    continue

                link_str = str(link).strip()
                cat_str = str(cat).strip() if cat else "Diğer"

                # Fiyatı parse et
                price_val = None
                if price and not str(price).startswith("="):
                    price_val = parse_price(price, self.config)

                # Çakışma kontrolü: aynı link varsa güncelle
                existing = crud.get_library_product_by_link(db, link_str, user_id)
                if existing:
                    if price_val and existing.current_price != price_val:
                        existing.current_price = price_val
                        existing.updated_at = datetime.utcnow()
                        updated += 1
                    continue

                # Yeni ürün ekle
                from src.core.scraper import Scraper
                scraper = Scraper(self.config, site_configs, self.logger)
                seller = scraper._infer_seller(link_str)

                db_lib = crud.get_or_create_library_product(
                    db,
                    name=prod_str[:80],
                    category=cat_str,
                    original_link=link_str,
                    user_id=user_id
                )

                if price_val:
                    db_lib.current_price = price_val
                    db_lib.current_seller = seller
                    db_lib.status = "BEKLEMEDE"
                    db.commit()
                    crud.add_price_history(db, db_lib.id, price_val, seller)

                imported += 1

        db.commit()
        self.logger.info(f"Excel import tamamlandı: {imported} yeni, {updated} güncellenen, {skipped} atlanan")

        return {"imported": imported, "updated": updated, "skipped": skipped}


class ExcelExporter:
    """DB'den Excel'e veri aktarımı."""

    def __init__(self, config: dict, logger):
        self.config = config
        self.logger = logger

    def export_to_excel(self, excel_path: str, db: Session, user_id: int = None) -> None:
        """DB'den güncel verileri alıp Excel sayfalarını günceller.
        - Kaynaklar sayfası: LibraryProduct'lardan oluşturulur
        - Katalog sayfası: Ürün başına en ucuz fiyat
        - Muadiller sayfası: Alternative tablosundan
        - Fiyat_Gecmisi: PriceHistory tablosundan
        - Setup sayfalarına DOKUNMAZ
        """
        from src.cli.excel_handler import ExcelHandler
        from src.web_backend import models

        if not os.path.exists(excel_path):
            self.logger.warning(f"Excel dosyası bulunamadı: {excel_path}")
            return

        excel = ExcelHandler(self.config, self.logger)
        excel.workbook_path = excel_path
        excel.load()
        excel.create_backup()

        wb_cfg = self.config.get("workbook", {})

        # DB'den verileri çek
        query = db.query(models.LibraryProduct)
        if user_id:
            query = query.filter(models.LibraryProduct.user_id == user_id)
        lib_prods = query.all()

        if not lib_prods:
            self.logger.info("DB'de ürün bulunamadı, Excel güncellenmedi.")
            return

        # --- Kaynaklar Sayfasını Güncelle ---
        self._write_sources_sheet(excel, lib_prods, wb_cfg)

        # --- Katalog Sayfasını Güncelle ---
        self._write_catalog_sheet(excel, lib_prods, wb_cfg)

        # --- Muadiller Sayfasını Güncelle ---
        self._write_alternatives_sheet(excel, lib_prods, wb_cfg)

        # --- Sırala ve Kaydet ---
        try:
            excel.sort_sheet_by_category(excel.sources_sheet_name)
            excel.sort_sheet_by_category(excel.catalog_sheet_name)
        except Exception as e:
            self.logger.warning(f"Sıralama hatası: {e}")

        try:
            excel.add_data_validation_to_sources()
        except Exception as e:
            self.logger.warning(f"Veri doğrulama hatası: {e}")

        excel.save()
        self.logger.info(f"Excel başarıyla güncellendi: {excel_path}")

    def _write_sources_sheet(self, excel, lib_prods, wb_cfg) -> None:
        """Kaynaklar sayfasını DB'den günceller."""
        sources_name = wb_cfg.get("sources_sheet", "Kaynaklar")
        cols = wb_cfg.get("sources_columns", {})

        # Sayfayı temizle ve yeniden oluştur
        if sources_name in excel.wb.sheetnames:
            excel.wb.remove(excel.wb[sources_name])

        s_cols = list(cols.values())
        excel.create_sheet_if_missing(sources_name, s_cols)
        ws = excel.wb[sources_name]

        header_map = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val:
                header_map[val] = c

        r = 2
        for lp in lib_prods:
            if cols.get("product") in header_map:
                ws.cell(row=r, column=header_map[cols["product"]], value=lp.name)
            if cols.get("category") in header_map:
                ws.cell(row=r, column=header_map[cols["category"]], value=lp.category)
            if cols.get("seller") in header_map:
                ws.cell(row=r, column=header_map[cols["seller"]], value=lp.current_seller or "")
            if cols.get("link") in header_map:
                ws.cell(row=r, column=header_map[cols["link"]], value=lp.original_link)
            if cols.get("price") in header_map:
                ws.cell(row=r, column=header_map[cols["price"]], value=lp.current_price)
            if cols.get("installment") in header_map:
                ws.cell(row=r, column=header_map[cols["installment"]], value=lp.current_installment or "")
            if cols.get("updated") in header_map:
                ts = lp.updated_at.strftime("%Y-%m-%d %H:%M:%S") if lp.updated_at else ""
                ws.cell(row=r, column=header_map[cols["updated"]], value=ts)
            if cols.get("status") in header_map:
                ws.cell(row=r, column=header_map[cols["status"]], value=lp.status or "")
            if cols.get("active") in header_map:
                ws.cell(row=r, column=header_map[cols["active"]], value="Evet")
            if cols.get("lock") in header_map:
                ws.cell(row=r, column=header_map[cols["lock"]], value="Hayır")
            r += 1

    def _write_catalog_sheet(self, excel, lib_prods, wb_cfg) -> None:
        """Katalog sayfasını DB'den günceller (ürün başına tek satır)."""
        catalog_name = wb_cfg.get("catalog_sheet", "Katalog")
        cols = wb_cfg.get("catalog_columns", {})

        if catalog_name in excel.wb.sheetnames:
            excel.wb.remove(excel.wb[catalog_name])

        c_cols = list(cols.values())
        excel.create_sheet_if_missing(catalog_name, c_cols)
        ws = excel.wb[catalog_name]

        header_map = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val:
                header_map[val] = c

        # Ürün başına en ucuz fiyatı bul (aynı isim varsa)
        from collections import defaultdict
        product_map = defaultdict(list)
        for lp in lib_prods:
            product_map[lp.name].append(lp)

        r = 2
        for name, lps in product_map.items():
            # En ucuz ve OK olanı bul
            ok_prods = [lp for lp in lps if lp.status == "OK" and lp.current_price]
            best = min(ok_prods, key=lambda x: x.current_price) if ok_prods else lps[0]

            if cols.get("product") in header_map:
                ws.cell(row=r, column=header_map[cols["product"]], value=best.name)
            if cols.get("category") in header_map:
                ws.cell(row=r, column=header_map[cols["category"]], value=best.category)
            if cols.get("best_price") in header_map:
                ws.cell(row=r, column=header_map[cols["best_price"]], value=best.current_price)
            if cols.get("best_seller") in header_map:
                ws.cell(row=r, column=header_map[cols["best_seller"]], value=best.current_seller or "")
            if cols.get("best_link") in header_map:
                ws.cell(row=r, column=header_map[cols["best_link"]], value=best.original_link)
            if cols.get("updated") in header_map:
                ts = best.updated_at.strftime("%Y-%m-%d %H:%M:%S") if best.updated_at else ""
                ws.cell(row=r, column=header_map[cols["updated"]], value=ts)
            if cols.get("trend") in header_map:
                ws.cell(row=r, column=header_map[cols["trend"]], value="▬")
            r += 1

    def _write_alternatives_sheet(self, excel, lib_prods, wb_cfg) -> None:
        """Muadiller sayfasını DB'den günceller."""
        alt_name = wb_cfg.get("alternatives_sheet", "Muadiller")
        cols = wb_cfg.get("alternatives_columns", {})

        if alt_name in excel.wb.sheetnames:
            excel.wb.remove(excel.wb[alt_name])

        a_cols = list(cols.values())
        excel.create_sheet_if_missing(alt_name, a_cols)
        ws = excel.wb[alt_name]

        header_map = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val:
                header_map[val] = c

        r = 2
        for lp in lib_prods:
            if not hasattr(lp, 'alternatives'):
                continue
            for idx, alt in enumerate(lp.alternatives, 1):
                if cols.get("product") in header_map:
                    ws.cell(row=r, column=header_map[cols["product"]], value=lp.name)
                if cols.get("rank") in header_map:
                    ws.cell(row=r, column=header_map[cols["rank"]], value=idx)
                if cols.get("alt_product") in header_map:
                    ws.cell(row=r, column=header_map[cols["alt_product"]], value=alt.title)
                if cols.get("alt_price") in header_map:
                    ws.cell(row=r, column=header_map[cols["alt_price"]], value=alt.price)
                if cols.get("alt_seller") in header_map:
                    ws.cell(row=r, column=header_map[cols["alt_seller"]], value=alt.seller or "")
                if cols.get("alt_link") in header_map:
                    ws.cell(row=r, column=header_map[cols["alt_link"]], value=alt.link)
                if cols.get("updated") in header_map:
                    ts = alt.updated_at.strftime("%Y-%m-%d %H:%M:%S") if alt.updated_at else ""
                    ws.cell(row=r, column=header_map[cols["updated"]], value=ts)
                r += 1

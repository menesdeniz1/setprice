# -*- coding: utf-8 -*-
from typing import List, Dict, Tuple
from collections import defaultdict
import urllib.parse
import re

from .excel_handler import ExcelHandler
from src.core.config_loader import ConfigLoader

class Migration:
    def __init__(self, excel: ExcelHandler, config: dict, logger):
        self.excel = excel
        self.config = config
        self.logger = logger
        self.site_configs = ConfigLoader().load_site_configs()

    def run(self, apply_formulas: bool = False, dry_run: bool = False) -> dict:
        """
        Ana göç akışı. 7 setup sayfasından verileri okuyup Kaynaklar ve Katalog sayfalarını oluşturur.
        """
        self.logger.info(f"Migration başlıyor (dry_run={dry_run}, apply_formulas={apply_formulas})")
        
        # 1. & 2. Tüm satırları oku ve filtrele
        all_rows = self._scan_and_filter_setups()
        self.logger.info(f"Bulunan geçerli veri satırı: {len(all_rows)}")
        
        # 3. Tekilleştir ve zenginleştir (kanonikleştirmeler vb)
        sources_data, catalog_data = self._process_data(all_rows)
        self.logger.info(f"Benzersiz Kaynaklar satırı: {len(sources_data)}")
        self.logger.info(f"Benzersiz Katalog satırı: {len(catalog_data)}")
        
        if not dry_run:
            # 4. Sayfaları oluştur
            self._create_bot_sheets()
            
            # 5. Kaynaklar'ı yaz
            self._write_sources(sources_data)
            
            # 6. Katalog'u yaz
            self._write_catalog(catalog_data)
            
            # Kategoriye göre sırala
            self.excel.sort_sheet_by_category(self.excel.sources_sheet_name)
            self.excel.sort_sheet_by_category(self.excel.catalog_sheet_name)
            
            # Veri doğrulama açılır listesini ekle
            self.excel.add_data_validation_to_sources()
            
            # 7. Setup formüllerini değiştir (opsiyonel)
            if apply_formulas:
                self.logger.info("Setup formülleri uygulanıyor...")
                self.excel.apply_setup_formulas(dry_run=False)
                
            self.excel.save()
            self.logger.info("Migration tamamlandı ve kaydedildi.")
            
        return {
            "total_rows": len(all_rows),
            "unique_sources": len(sources_data),
            "unique_catalog": len(catalog_data)
        }

    def _scan_and_filter_setups(self) -> List[dict]:
        all_rows = []
        skip_patterns = self.config.get("migration", {}).get("skip_product_patterns", [])
        start_row = self.config.get("migration", {}).get("data_start_row", 5)
        
        for sheet_name in self.excel.wb.sheetnames:
            if sheet_name in self.excel.writable_sheets:
                continue
                
            ws = self.excel.wb[sheet_name]
            for r in range(start_row, ws.max_row + 1):
                cat = ws.cell(row=r, column=2).value
                prod = ws.cell(row=r, column=3).value
                price = ws.cell(row=r, column=4).value
                install = ws.cell(row=r, column=5).value
                link = ws.cell(row=r, column=6).value
                
                if not prod and not link:
                    continue
                    
                prod_str = str(prod).strip()
                if any(p.lower() in prod_str.lower() for p in skip_patterns):
                    continue
                    
                # Eğer fiyat veya link formül ise (yani = ile başlıyorsa) boş geç
                price_val = price
                if str(price).startswith("="):
                    price_val = None
                    
                link_val = link
                if str(link).startswith("="):
                    link_val = ""
                    
                all_rows.append({
                    "sheet": sheet_name,
                    "row": r,
                    "category": str(cat).strip() if cat else "",
                    "product": prod_str,
                    "price": price_val,
                    "installment": str(install).strip() if install else "",
                    "link": link_val
                })
                
        return all_rows

    def _process_data(self, all_rows: List[dict]) -> Tuple[List[dict], List[dict]]:
        unique_sources = {}
        unique_catalog = {}
        
        for r in all_rows:
            prod = r["product"]
            link = r["link"]
            
            # Kategori kanonikleştir
            cat = self._canonicalize_category(r["category"])
            
            if link:
                key = f"{prod}|{link}"
                if key not in unique_sources:
                    seller = self._infer_seller(link)
                    unique_sources[key] = {
                        "product": prod,
                        "category": cat,
                        "seller": seller,
                        "link": link,
                        "price": r["price"],
                        "installment": r["installment"],
                        "status": "",
                        "active": "Evet",
                        "lock": "Hayır" if not str(r["price"]).startswith("*") else "Evet"
                    }
            
            if prod not in unique_catalog:
                search_term = self._infer_search_term(prod, cat)
                unique_catalog[prod] = {
                    "product": prod,
                    "category": cat,
                    "best_price": r["price"],  # Başlangıçta mevcut olanı koyalım
                    "best_seller": self._infer_seller(link) if link else "",
                    "best_link": link,
                    "search_term": search_term
                }
                
        return list(unique_sources.values()), list(unique_catalog.values())

    def _canonicalize_category(self, cat: str) -> str:
        aliases = self.config.get("category_aliases", {})
        return aliases.get(cat, cat)

    def _infer_seller(self, link: str) -> str:
        try:
            parsed = urllib.parse.urlparse(link)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
                
            # Config'teki sitelerden ara
            for cfg_domain, cfg in self.site_configs.items():
                if domain.endswith(cfg_domain):
                    return cfg.get("seller_name", domain)
                    
            return domain
        except:
            return ""

    def _infer_search_term(self, product: str, category: str) -> str:
        # Arama terimi tahmini
        p = product.lower()
        if "5070 ti" in p and "16g" in p: return "RTX 5070 Ti 16GB Ekran Kartı"
        if "5070 " in p and "12gb" in p: return "RTX 5070 12GB Ekran Kartı"
        if "5080 " in p: return "RTX 5080 16GB Ekran Kartı"
        if "7800x3d" in p: return "Ryzen 7 7800X3D İşlemci"
        if "9800x3d" in p: return "Ryzen 7 9800X3D İşlemci"
        if "b850" in p: return "B850 ATX Wi-Fi Anakart"
        if "b650" in p: return "B650 ATX Wi-Fi Anakart"
        if "ddr5 6000mhz" in p and "32gb" in p: return "32GB (2x16) DDR5 6000MHz RAM"
        if "sn850x" in p or "nm790" in p: return "1TB/2TB PCIe Gen4 NVMe M.2 SSD"
        if "850w" in p: return "850W 80 Plus Gold ATX 3.1 Tam Modüler Güç Kaynağı"
        if "750w" in p: return "750W 80 Plus Bronze Güç Kaynağı"
        if "kasa" in p or "tower" in p: return "Mid-Tower Mesh Oyuncu Kasası"
        if "soğutucu" in p or "spirit" in p: return "Çift Kule Tipi İşlemci Hava Soğutucu"
        if "priz" in p: return "5'li Akım Korumalı Priz"
        if "monitör" in p or "monitor" in p or "oled" in p: return "27 inç 2K/240Hz Gaming Monitör"
        if "ups" in p or "kgk" in p or "line interactive" in p: return "Line Interactive UPS"
        if "kulaklık" in p or "headset" in p: return "Kablosuz Gaming Kulaklık"
        if "mouse" in p: return "Hafif Kablosuz Oyuncu Mouse"
        if "klavye" in p or "mekanik" in p: return "Mekanik TKL Kablosuz Klavye"
        if "pad" in p: return "XXL Gaming Mouse Pad"
        
        # Tahmin edilemeyenler için kategori + ilk 3 kelime
        words = product.split()[:3]
        return f"{category} {' '.join(words)}"

    def _create_bot_sheets(self):
        wb_cfg = self.config.get("workbook", {})
        
        # Temizle (Varsa silerek üzerine yaz) - Fiyat Geçmişini koruyoruz!
        for name in [self.excel.sources_sheet_name, self.excel.catalog_sheet_name, 
                     self.excel.alternatives_sheet_name]:
            if name in self.excel.wb.sheetnames:
                self.excel.wb.remove(self.excel.wb[name])
        
        # Kaynaklar
        s_cols = list(wb_cfg.get("sources_columns", {}).values())
        self.excel.create_sheet_if_missing(wb_cfg.get("sources_sheet", "Kaynaklar"), s_cols)
        
        # Katalog
        c_cols = list(wb_cfg.get("catalog_columns", {}).values())
        self.excel.create_sheet_if_missing(wb_cfg.get("catalog_sheet", "Katalog"), c_cols)
        
        # Muadiller
        a_cols = list(wb_cfg.get("alternatives_columns", {}).values())
        self.excel.create_sheet_if_missing(wb_cfg.get("alternatives_sheet", "Muadiller"), a_cols)
        
        # Fiyat_Gecmisi
        h_cols = ["Ürün", "Satıcı", "Fiyat", "Tarih"]
        self.excel.create_sheet_if_missing(wb_cfg.get("history_sheet", "Fiyat_Gecmisi"), h_cols)

    def _write_sources(self, data: List[dict]):
        ws = self.excel.wb[self.excel.sources_sheet_name]
        cols = self.config.get("workbook", {}).get("sources_columns", {})
        
        header_map = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val: header_map[val] = c
            
        r = ws.max_row + 1
        for item in data:
            if cols.get("product") in header_map: ws.cell(row=r, column=header_map[cols["product"]], value=item["product"])
            if cols.get("category") in header_map: ws.cell(row=r, column=header_map[cols["category"]], value=item["category"])
            if cols.get("seller") in header_map: ws.cell(row=r, column=header_map[cols["seller"]], value=item["seller"])
            if cols.get("link") in header_map: ws.cell(row=r, column=header_map[cols["link"]], value=item["link"])
            if cols.get("price") in header_map: ws.cell(row=r, column=header_map[cols["price"]], value=item["price"])
            if cols.get("installment") in header_map: ws.cell(row=r, column=header_map[cols["installment"]], value=item["installment"])
            if cols.get("status") in header_map: ws.cell(row=r, column=header_map[cols["status"]], value=item["status"])
            if cols.get("active") in header_map: ws.cell(row=r, column=header_map[cols["active"]], value=item["active"])
            if cols.get("lock") in header_map: ws.cell(row=r, column=header_map[cols["lock"]], value=item["lock"])
            r += 1

    def _write_catalog(self, data: List[dict]):
        ws = self.excel.wb[self.excel.catalog_sheet_name]
        cols = self.config.get("workbook", {}).get("catalog_columns", {})
        
        header_map = {}
        for c in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=c).value
            if val: header_map[val] = c
            
        r = ws.max_row + 1
        for item in data:
            if cols.get("product") in header_map: ws.cell(row=r, column=header_map[cols["product"]], value=item["product"])
            if cols.get("category") in header_map: ws.cell(row=r, column=header_map[cols["category"]], value=item["category"])
            if cols.get("best_price") in header_map: ws.cell(row=r, column=header_map[cols["best_price"]], value=item["best_price"])
            if cols.get("best_seller") in header_map: ws.cell(row=r, column=header_map[cols["best_seller"]], value=item["best_seller"])
            if cols.get("best_link") in header_map: ws.cell(row=r, column=header_map[cols["best_link"]], value=item["best_link"])
            if cols.get("search_term") in header_map: ws.cell(row=r, column=header_map[cols["search_term"]], value=item["search_term"])
            r += 1

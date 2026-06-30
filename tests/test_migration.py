import pytest
from unittest.mock import MagicMock
from src.migration import Migration
from src.excel_handler import ExcelHandler

@pytest.fixture
def config():
    return {
        "migration": {
            "data_start_row": 5,
            "skip_product_patterns": ["Total"]
        },
        "category_aliases": {
            "CPU": "İşlemci"
        }
    }

def test_migration_filtering_and_canonicalization(config):
    logger = MagicMock()
    excel = MagicMock()
    
    migration = Migration(excel, config, logger)
    
    # Dummy veriler
    all_rows = [
        {"product": "Ryzen 7", "category": "CPU", "price": 100, "installment": "", "link": "http://a"},
        {"product": "Aynı Ürün", "category": "RAM", "price": 50, "installment": "", "link": "http://b"},
        {"product": "Aynı Ürün", "category": "RAM", "price": 60, "installment": "", "link": "http://b"} # Duplicate link
    ]
    
    sources, catalog = migration._process_data(all_rows)
    
    assert len(sources) == 2
    
    # Kanonikleştirmeler çalışmalı
    assert sources[0]["category"] == "İşlemci"
    
    # Aynı (ürün, link) çifti tekilleştirilmeli
    assert len([s for s in sources if s["product"] == "Aynı Ürün"]) == 1
    
    # Katalog'da 2 benzersiz ürün olmalı
    assert len(catalog) == 2
    
def test_migration_infer_search_term(config):
    migration = Migration(MagicMock(), config, MagicMock())
    
    assert migration._infer_search_term("AMD Ryzen 7 7800X3D", "İşlemci") == "Ryzen 7 7800X3D İşlemci"
    assert migration._infer_search_term("Palit RTX 5070 Ti GamingPro 16G", "Ekran Kartı") == "RTX 5070 Ti 16GB Ekran Kartı"
    # Bilinmeyen ürün için generic tahmin (kategori + ilk 3 kelime)
    assert migration._infer_search_term("Bilinmeyen Marka Model XYZ", "TestKategori") == "TestKategori Bilinmeyen Marka Model"

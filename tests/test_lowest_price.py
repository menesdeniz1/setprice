import pytest
from unittest.mock import MagicMock
from src.orchestrator import Orchestrator
from src.models import SourceRow, CatalogRow

@pytest.fixture
def orchestrator():
    config = {
        "workbook": {"catalog_columns": {"product": "Ürün", "category": "Çeşit", "best_price": "En Ucuz Fiyat", "best_seller": "En Ucuz Satıcı", "best_link": "Link", "search_term": "Arama Terimi"}},
        "paths": {"reports_dir": "./data/reports"}
    }
    logger = MagicMock()
    orch = Orchestrator(config, logger)
    return orch

def test_resolve_cheapest_basic(orchestrator):
    sources = [
        SourceRow(product="ürün1", category="Kategori", seller="Satıcı A", link="http://a", price=100.0, status="OK"),
        SourceRow(product="Ürün1", category="Kategori", seller="Satıcı B", link="http://b", price=90.0, status="OK"),
        SourceRow(product="ürün1 ", category="Kategori", seller="Satıcı C", link="http://c", price=110.0, status="OK")
    ]
    
    result = orchestrator._resolve_cheapest(sources, [])
    assert "ürün1" in result
    assert result["ürün1"]["price"] == 90.0
    assert result["ürün1"]["seller"] == "Satıcı B"

def test_resolve_cheapest_all_failed(orchestrator):
    sources = [
        SourceRow(product="ürün1", category="Kategori", seller="Satıcı A", link="http://a", price=None, status="FAILED"),
        SourceRow(product="ürün1", category="Kategori", seller="Satıcı B", link="http://b", price=None, status="FAILED")
    ]
    catalog = [
        CatalogRow(product="ürün1", category="Kategori", best_price=100.0, best_seller="Eski Satıcı", best_link="http://eski", search_term="")
    ]
    
    result = orchestrator._resolve_cheapest(sources, catalog)
    assert "ürün1" in result
    # Eski fiyat korunmalı
    assert result["ürün1"]["price"] == 100.0
    assert result["ürün1"]["seller"] == "Eski Satıcı"

def test_resolve_cheapest_with_locked(orchestrator):
    sources = [
        SourceRow(product="ürün1", category="Kategori", seller="Satıcı A", link="http://a", price=100.0, status="OK"),
        SourceRow(product="ürün1", category="Kategori", seller="Manuel Satıcı", link="http://m", price=50.0, status="FLAGGED", locked=True)
    ]
    
    result = orchestrator._resolve_cheapest(sources, [])
    # Kilitli olan FLAGGED olsa bile seçilmeli çünkü price'ı var
    assert result["ürün1"]["price"] == 50.0
    assert result["ürün1"]["seller"] == "Manuel Satıcı"

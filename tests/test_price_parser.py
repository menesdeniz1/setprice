import pytest
from src.price_parser import parse_price, should_skip_price

@pytest.fixture
def config():
    return {
        "price_parsing": {
            "currency_symbols": ["₺", "TL", "TRY", "tl"],
            "strip_chars": ["*", "~", " "]
        },
        "respect_manual": {
            "skip_if_price_starts_with": ["*"],
            "skip_if_has_parenthetical": True,
            "owned_keywords": ["Mevcut"],
            "hold_keywords": ["Alınmayacak"]
        }
    }

def test_parse_price(config):
    assert parse_price("14799.0", config) == 14799.00
    assert parse_price("2.798,80 ₺", config) == 2798.80
    assert parse_price("2,399.00 TL", config) == 2399.00
    assert parse_price("53.599", config) == 53599.00
    assert parse_price("53.599,00", config) == 53599.00
    assert parse_price("52.107", config) == 52107.00
    assert parse_price("57.528", config) == 57528.00
    assert parse_price(None, config) is None
    assert parse_price("", config) is None

def test_should_skip_price(config):
    # Yıldız
    skip, reason = should_skip_price("*17999", config)
    assert skip is True
    assert "StartsWith" in reason

    # Parantez
    skip, reason = should_skip_price("25499 (Şuan Alınmayacak)", config)
    assert skip is True
    assert "Parenthetical" in reason

    # Mevcut
    skip, reason = should_skip_price("0 (Mevcut)", config)
    assert skip is True

    # Normal fiyat
    skip, reason = should_skip_price("14799", config)
    assert skip is False

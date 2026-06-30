import pytest
from src.price_parser import should_skip_price
from src.models import SourceRow

def test_should_skip_logic():
    config = {
        "respect_manual": {
            "skip_if_price_starts_with": ["*"],
            "skip_if_has_parenthetical": True,
            "owned_keywords": ["Mevcut"],
            "hold_keywords": ["Alınmayacak"]
        }
    }
    
    # Normal fiyat -> atlama
    skip, reason = should_skip_price("15000", config)
    assert not skip
    
    # Kilit yıldızı
    skip, reason = should_skip_price("*15000", config)
    assert skip
    assert "StartsWith" in reason
    
    # Parantez (karar belirtme)
    skip, reason = should_skip_price("15000 (Daha ucuzu var)", config)
    assert skip
    assert "Parenthetical" in reason
    
    # Sahip olunan (fiyat kısmına yazılmışsa)
    skip, reason = should_skip_price("0 (Mevcut)", config)
    assert skip
    
    # Alınmayacak
    skip, reason = should_skip_price("15000 (Şuan Alınmayacak)", config)
    assert skip

# -*- coding: utf-8 -*-
import re
from typing import Optional, Tuple, Any

def parse_price(raw: Any, config: dict) -> Optional[float]:
    """
    Türkçe/İngilizce karma fiyat string'ini float'a çevirir.

    Desteklenen formatlar:
      "14799.0"              → 14799.00
      "2.798,80 ₺"           → 2798.80
      "2,399.00 TL"          → 2399.00
      "53.599"               → 53599.00
      "53.599,00"            → 53599.00
      "57.528"               → 57528.00

    Kural: Son ayraçtan sonra 2 hane varsa o ondalıktır.
    """
    if raw is None or str(raw).strip() == "":
        return None

    raw_str = str(raw).strip()
    
    # Temizle (boşluklar, para birimleri, * vb.)
    for char in config.get("price_parsing", {}).get("strip_chars", ["*", "~", " "]):
        raw_str = raw_str.replace(char, "")
    for sym in config.get("price_parsing", {}).get("currency_symbols", ["₺", "TL", "TRY", "tl", "£", "$", "€"]):
        raw_str = raw_str.replace(sym, "")
        
    raw_str = raw_str.strip()
    
    # Sadece sayılar, virgül ve nokta kalsın
    raw_str = re.sub(r'[^\d.,]', '', raw_str)
    
    if not raw_str:
        return None

    # Eğer hiç ayraç yoksa direkt float
    if ',' not in raw_str and '.' not in raw_str:
        try:
            return float(raw_str)
        except ValueError:
            return None

    # En sağdaki ayracı bul
    last_comma = raw_str.rfind(',')
    last_dot = raw_str.rfind('.')
    last_sep = max(last_comma, last_dot)

    if last_sep != -1:
        # Son ayraçtan sonra 2 veya 3 karakter varsa (kuruş), bu ondalıktır.
        # Bazı yerlerde ondalık 2 basamak, bazı yerlerde 1 veya 3 olabilir. Genelde 2'dir.
        chars_after_sep = len(raw_str) - 1 - last_sep
        if chars_after_sep == 2 or chars_after_sep == 1:
            # Ondalık ayracı
            sep_char = raw_str[last_sep]
            other_char = '.' if sep_char == ',' else ','
            # Binlik ayraçlarını sil
            clean_str = raw_str.replace(other_char, '')
            # Ondalık ayracını noktaya çevir
            clean_str = clean_str.replace(sep_char, '.')
            try:
                return float(clean_str)
            except ValueError:
                pass
        else:
            # Son ayraç muhtemelen binlik ayracıdır (örn 53.599)
            # Tüm ayraçları sil
            clean_str = raw_str.replace('.', '').replace(',', '')
            try:
                return float(clean_str)
            except ValueError:
                pass

    try:
        return float(raw_str)
    except ValueError:
        return None

def should_skip_price(raw: Any, config: dict) -> Tuple[bool, str]:
    """
    Manuel karar kontrolü. True + sebep dönerse atla.
    """
    if raw is None:
        return False, ""
        
    raw_str = str(raw).strip()
    if raw_str.startswith("="):
        return False, ""
        
    respect_config = config.get("respect_manual", {})
    
    if respect_config.get("skip_if_price_starts_with"):
        for start_char in respect_config.get("skip_if_price_starts_with"):
            if raw_str.startswith(start_char):
                return True, f"StartsWith('{start_char}')"
                
    if respect_config.get("skip_if_has_parenthetical") and "(" in raw_str and ")" in raw_str:
        return True, "Parenthetical Note"
        
    for kw in respect_config.get("owned_keywords", []):
        if kw.lower() in raw_str.lower():
            return True, f"OwnedKeyword('{kw}')"
            
    for kw in respect_config.get("hold_keywords", []):
        if kw.lower() in raw_str.lower():
            return True, f"HoldKeyword('{kw}')"

    return False, ""

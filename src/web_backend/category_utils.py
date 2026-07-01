# -*- coding: utf-8 -*-
"""
Ürün adından kategori tahmini. Bu bir kesin sınıflandırma değil, sadece bir
öneri — kullanıcı her zaman elle geçersiz kılabilir (bkz. ProductCreate.category).
"""
from typing import List, Optional

_KEYWORD_MAP = {
    "kulaklık": "Kulaklık", "headset": "Kulaklık", "earphone": "Kulaklık",
    "mouse": "Mouse", "fare": "Mouse",
    "klavye": "Klavye", "keyboard": "Klavye",
    "anakart": "Anakart", "motherboard": "Anakart", "mainboard": "Anakart",
    "işlemci": "İşlemci", "islemci": "İşlemci", "cpu": "İşlemci",
    "ekran kartı": "Ekran Kartı", "ekran karti": "Ekran Kartı", "vga": "Ekran Kartı",
    "gpu": "Ekran Kartı", "graphics card": "Ekran Kartı",
    "ram": "RAM", "bellek": "RAM", "memory": "RAM",
    "ssd": "Depolama", "hdd": "Depolama", "harddisk": "Depolama", "depolama": "Depolama",
    "kasa": "Kasa", "case": "Kasa",
    "güç kaynağı": "Güç Kaynağı", "guc kaynagi": "Güç Kaynağı", "psu": "Güç Kaynağı",
    "power supply": "Güç Kaynağı",
    "soğutma": "Soğutma", "sogutma": "Soğutma", "soğutucu": "Soğutma", "sogutucu": "Soğutma",
    "cooler": "Soğutma",
}


def infer_category(product_name: str, known_categories: Optional[List[str]] = None) -> str:
    """Ürün adına göre kategori tahmini yapar.

    Önce (varsa) setin kendi kategori listesiyle eşleştirmeyi dener — bu,
    PC dışı setlerde (kıyafet, ev eşyası vb.) de anlamlı sonuç verir.
    Bulamazsa dahili elektronik anahtar-kelime sözlüğüne düşer.
    """
    lower_name = (product_name or "").lower()

    if known_categories:
        for cat in known_categories:
            if cat and cat.lower() in lower_name:
                return cat

    for keyword, normalized_cat in _KEYWORD_MAP.items():
        if keyword in lower_name:
            return normalized_cat

    return "Diğer"

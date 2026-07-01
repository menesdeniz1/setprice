# -*- coding: utf-8 -*-
"""
Set şablonları — sabit/sistem tanımlı. DB tablosu değil, düz Python listesi:
bunlar nadiren değişen ürün-tasarım kararları, kullanıcı verisi değil.
Kullanıcının kendi özelleştirdiği kategori listesi (SetCategory) ayrı bir
DB tablosunda tutulur ve şablondan bağımsız olarak düzenlenebilir.
"""
from typing import Optional, List, Dict

SET_TEMPLATES: List[Dict] = [
    {
        "key": "pc_setup",
        "name": "Masaüstü Setup",
        "categories": [
            "İşlemci", "Anakart", "Ekran Kartı", "RAM", "Depolama",
            "Güç Kaynağı", "Kasa", "Soğutma", "Monitör",
        ],
    },
    {
        "key": "outfit",
        "name": "Kombin / Kıyafet",
        "categories": ["Tişört", "Pantolon", "Ayakkabı", "Ceket", "Aksesuar"],
    },
    {
        "key": "blank",
        "name": "Boş / Özel",
        "categories": [],
    },
]

_BY_KEY = {t["key"]: t for t in SET_TEMPLATES}


def get_template(key: Optional[str]) -> Optional[Dict]:
    if not key:
        return None
    return _BY_KEY.get(key)

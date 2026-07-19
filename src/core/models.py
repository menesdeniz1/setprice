# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class SourceRow:
    product: str
    category: str
    seller: str
    link: str
    price: Optional[float] = None
    installment: Optional[str] = None
    updated: Optional[datetime] = None
    status: str = ""           # OK / STALE / FAILED / FLAGGED
    active: bool = True        # Evet/Hayır
    locked: bool = False       # Evet/Hayır
    row_number: int = 0        # Excel satır numarası (yazma için)

@dataclass
class CatalogRow:
    product: str
    category: str
    best_price: Optional[float] = None
    best_seller: Optional[str] = None
    best_link: Optional[str] = None
    updated: Optional[datetime] = None
    search_term: Optional[str] = None
    trend: Optional[str] = "▬"

@dataclass
class AlternativeRow:
    product: str               # referans ürün adı
    search_term: str
    rank: int                  # 1, 2, 3
    alt_product: str           # muadil ürün adı
    alt_price: float
    alt_seller: str
    alt_link: str
    updated: datetime

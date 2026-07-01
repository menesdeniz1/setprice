# -*- coding: utf-8 -*-
"""
CPU/GPU performans referans verisi ve eşleştirme.

ÖNEMLİ — kapsam notu: Bu, PassMark'tan CANLI çekilen bir veri değil. Elle
küratörlüğü yapılmış, yaklaşık/gösterge niteliğinde bir başlangıç veri seti
(cpubenchmark.net / videocardbenchmark.net figürlerine dayanan kaba tahminler).
Canlı scraping eklenmedi çünkü PassMark'ın sayfa yapısı bu oturumda doğrulanamadı
(JS-render olasılığı var) — doğrulanmamış selector'larla sessizce kırılacak bir
scraper yazmak, hiç yazmamaktan daha kötü olurdu. Bu dosya, ileride gerçek bir
senkron script'i eklendiğinde değiştirilecek/genişletilecek şekilde tasarlandı:
`BenchmarkEntry` tablosu zaten DB'de, tek yapılması gereken bu SEED listesi
yerine gerçek zamanlı çekilen veriyle upsert yapmak.

Skorlar PassMark "CPU Mark" / "G3D Mark" tarzı tekil özet skorlardır.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from . import models
from .similarity_utils import title_similarity

MATCH_THRESHOLD = 0.5

# (kategori, ürün adı, yaklaşık skor)
BENCHMARK_SEED: List[Tuple[str, str, float]] = [
    # --- İşlemci (yaklaşık PassMark CPU Mark) ---
    ("İşlemci", "Intel Core i3-12100F", 13500),
    ("İşlemci", "Intel Core i5-12400F", 18700),
    ("İşlemci", "Intel Core i5-13400F", 24500),
    ("İşlemci", "Intel Core i5-14400F", 25600),
    ("İşlemci", "Intel Core i5-14600K", 33000),
    ("İşlemci", "Intel Core i7-12700F", 28000),
    ("İşlemci", "Intel Core i7-13700F", 35000),
    ("İşlemci", "Intel Core i7-14700F", 38000),
    ("İşlemci", "Intel Core i9-13900K", 59000),
    ("İşlemci", "Intel Core i9-14900K", 63000),
    ("İşlemci", "AMD Ryzen 5 5600", 22200),
    ("İşlemci", "AMD Ryzen 5 5600X", 23100),
    ("İşlemci", "AMD Ryzen 5 7600", 28800),
    ("İşlemci", "AMD Ryzen 5 7600X", 29500),
    ("İşlemci", "AMD Ryzen 7 5700X", 26500),
    ("İşlemci", "AMD Ryzen 7 7700X", 34000),
    ("İşlemci", "AMD Ryzen 7 7800X3D", 32000),
    ("İşlemci", "AMD Ryzen 9 7900X", 44000),
    ("İşlemci", "AMD Ryzen 9 7950X", 59000),

    # --- Ekran Kartı (yaklaşık PassMark G3D Mark) ---
    ("Ekran Kartı", "NVIDIA GeForce GTX 1650", 9000),
    ("Ekran Kartı", "NVIDIA GeForce RTX 3050", 13500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 3060", 17200),
    ("Ekran Kartı", "NVIDIA GeForce RTX 3060 Ti", 21800),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4060", 20500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4060 Ti", 23500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4070", 28500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4070 Super", 30500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4070 Ti", 32500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4080", 35500),
    ("Ekran Kartı", "NVIDIA GeForce RTX 4090", 39500),
    ("Ekran Kartı", "AMD Radeon RX 6600", 15800),
    ("Ekran Kartı", "AMD Radeon RX 6700 XT", 21900),
    ("Ekran Kartı", "AMD Radeon RX 7600", 18700),
    ("Ekran Kartı", "AMD Radeon RX 7700 XT", 25800),
    ("Ekran Kartı", "AMD Radeon RX 7800 XT", 29000),
    ("Ekran Kartı", "AMD Radeon RX 7900 XT", 34500),
    ("Ekran Kartı", "AMD Radeon RX 7900 XTX", 37500),
]

BENCHMARK_CATEGORIES = {row[0] for row in BENCHMARK_SEED}


def seed_benchmark_entries(db: Session) -> None:
    """Idempotent: sadece eksik olan (kategori, isim) çiftlerini ekler."""
    existing = {
        (e.category, e.name) for e in db.query(models.BenchmarkEntry).all()
    }
    added = False
    for category, name, score in BENCHMARK_SEED:
        if (category, name) in existing:
            continue
        db.add(models.BenchmarkEntry(category=category, name=name, score=score, source="PassMark (seed)"))
        added = True
    if added:
        db.commit()


def find_best_match(db: Session, product_name: str, category: str) -> Optional[Tuple[str, float]]:
    """Verilen ürün adına en yakın benchmark girdisini bulur.
    Returns: (eşleşen_referans_adı, ham_skor) ya da eşik altındaysa None."""
    if category not in BENCHMARK_CATEGORIES:
        return None
    entries = db.query(models.BenchmarkEntry).filter(models.BenchmarkEntry.category == category).all()
    if not entries:
        return None

    best_entry = None
    best_score = 0.0
    for entry in entries:
        sim = title_similarity(product_name, entry.name)
        if sim > best_score:
            best_score = sim
            best_entry = entry

    if best_entry and best_score >= MATCH_THRESHOLD:
        return best_entry.name, best_entry.score
    return None


def normalize_score(db: Session, category: str, raw_score: float) -> float:
    """Kategori içindeki min/max'a göre 0-100 aralığına ölçekler."""
    entries = db.query(models.BenchmarkEntry.score).filter(models.BenchmarkEntry.category == category).all()
    scores = [e[0] for e in entries]
    if not scores:
        return 50.0
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return 50.0
    normalized = (raw_score - lo) / (hi - lo) * 100
    return round(max(0.0, min(100.0, normalized)), 1)

# -*- coding: utf-8 -*-
"""
Başlık benzerliği — bir arama sonucunun kaynak ürünle "muhtemelen aynı ürün"
mü yoksa "spec bazlı muadil" mi olduğunu ayırt etmek için kullanılır.
Harici bağımlılık yok; stdlib difflib yeterli hassasiyette.
"""
from difflib import SequenceMatcher

SAME_PRODUCT_THRESHOLD = 0.55


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def classify_match(source_name: str, candidate_title: str):
    """Returns (match_type, confidence) — match_type: 'same_product' | 'similar'."""
    score = title_similarity(source_name, candidate_title)
    match_type = "same_product" if score >= SAME_PRODUCT_THRESHOLD else "similar"
    return match_type, round(score, 2)

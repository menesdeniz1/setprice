# -*- coding: utf-8 -*-
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.web_backend.similarity_utils import title_similarity, classify_match, SAME_PRODUCT_THRESHOLD


def test_title_similarity_identical():
    assert title_similarity("Nike Air Max 90", "Nike Air Max 90") == 1.0


def test_title_similarity_empty():
    assert title_similarity("", "Nike Air Max 90") == 0.0
    assert title_similarity(None, "Nike Air Max 90") == 0.0


def test_classify_match_same_product():
    match_type, confidence = classify_match("Nike Air Max 90 Beyaz", "Nike Air Max 90 Beyaz - 42 Numara")
    assert match_type == "same_product"
    assert confidence >= SAME_PRODUCT_THRESHOLD


def test_classify_match_similar():
    match_type, confidence = classify_match("Nike Air Max 90 Beyaz", "Adidas Superstar Siyah")
    assert match_type == "similar"
    assert confidence < SAME_PRODUCT_THRESHOLD

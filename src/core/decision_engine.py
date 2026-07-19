# -*- coding: utf-8 -*-
"""
AI Shopping Intelligence — Decision Engine v2

Ürün = canlı varlık. Fiyat = hikaye. Karar = zaman.
Bu motor fiyat takip etmez; doğru alım zamanını hesaplar.
"""
from typing import List, Dict, Optional
import datetime
import re
import random
import statistics


class DecisionEngine:
    """
    Fiyat/değer hesaplama yardımcıları — her ürün için:
    1. Trend analizi (yükseliş/düşüş/stabil)
    2. Dip bölge tespiti (tarihsel minimum'a yakınlık)
    3. Bull-trap (sahte indirim) dedektörü
    4. Value Score (benchmark karşılaştırması)
    5. Satisfaction Score (rating + review güvenilirliği)

    Nihai BUY/WAIT/AVOID kararı ve gerekçe metni artık burada değil,
    src/ai_decision_engine.py'de üretiliyor — bu sınıf ona zemin
    hazırlayan hesaplanmış sinyalleri sağlar.
    """

    # ── Trend Analizi ──────────────────────────────────────────────

    def analyze_trend(self, history: List[float]) -> Dict:
        """
        Fiyat geçmişinden trend bilgisi çıkarır.
        Returns:
            direction: "down" | "up" | "stable"
            strength: 0.0 - 1.0 (trendin gücü)
            volatility: 0.0 - 1.0 (fiyat oynaklığı)
            ma_short: kısa vadeli hareketli ortalama
            ma_long: uzun vadeli hareketli ortalama
        """
        if not history or len(history) < 2:
            return {
                "direction": "stable",
                "strength": 0.0,
                "volatility": 0.0,
                "ma_short": history[0] if history else 0,
                "ma_long": history[0] if history else 0,
            }

        # Kısa ve uzun vadeli MA
        short_window = min(3, len(history))
        long_window = min(7, len(history))
        ma_short = statistics.mean(history[-short_window:])
        ma_long = statistics.mean(history[-long_window:])

        # Trend yönü: MA crossover
        if ma_long > 0:
            cross_ratio = (ma_short - ma_long) / ma_long
        else:
            cross_ratio = 0.0

        if cross_ratio < -0.03:
            direction = "down"
        elif cross_ratio > 0.03:
            direction = "up"
        else:
            direction = "stable"

        # Trend gücü (ne kadar keskin hareket)
        strength = min(1.0, abs(cross_ratio) * 10)

        # Volatilite (fiyat oynaklığı)
        if len(history) >= 3:
            mean_price = statistics.mean(history)
            if mean_price > 0:
                stdev = statistics.stdev(history)
                volatility = min(1.0, stdev / mean_price)
            else:
                volatility = 0.0
        else:
            volatility = 0.0

        return {
            "direction": direction,
            "strength": round(strength, 2),
            "volatility": round(volatility, 3),
            "ma_short": round(ma_short, 2),
            "ma_long": round(ma_long, 2),
        }

    # ── Dip Bölge Tespiti ──────────────────────────────────────────

    def detect_bottom_zone(self, current_price: float, history: List[float]) -> Dict:
        """
        Güncel fiyatın tarihsel dip bölgeye ne kadar yakın olduğunu hesaplar.
        Returns:
            is_near_bottom: bool
            percentile: 0-100 (0 = tarihsel en düşük, 100 = en yüksek)
            historical_min: float
            historical_max: float
        """
        if not history or len(history) < 2:
            return {
                "is_near_bottom": False,
                "percentile": 50.0,
                "historical_min": current_price,
                "historical_max": current_price,
            }

        hist_min = min(history)
        hist_max = max(history)
        price_range = hist_max - hist_min

        if price_range == 0:
            percentile = 50.0
        else:
            percentile = ((current_price - hist_min) / price_range) * 100
            percentile = max(0.0, min(100.0, percentile))

        # Dip bölge: fiyat, tarihsel aralığın alt %20'sindeyse
        is_near_bottom = percentile <= 20.0

        return {
            "is_near_bottom": is_near_bottom,
            "percentile": round(percentile, 1),
            "historical_min": hist_min,
            "historical_max": hist_max,
        }

    # ── Bull-Trap (Sahte İndirim) ──────────────────────────────────

    def detect_bull_trap(self, current_price: float, history: List[float]) -> bool:
        """
        Fiyat önce şişirilip sonra indirilmişse (ama hâlâ medyandan pahalıysa) = tuzak.
        """
        if not history or len(history) < 3:
            return False

        prev_price = history[-2] if history[-1] == current_price else history[-1]
        sorted_hist = sorted(history)
        median_price = sorted_hist[len(sorted_hist) // 2]

        # Güncel fiyat medyandan %10+ pahalı VE bir önceki fiyattan düşmüş
        if current_price > (median_price * 1.10) and prev_price > current_price:
            return True

        return False

    # ── Value Score ────────────────────────────────────────────────

    def calculate_value_score(self, current_price: float, benchmark_price: Optional[float]) -> float:
        """
        Ürünün benchmark'a göre değer skoru. 0-100.
        50 = fair value, 70+ = ucuz, 30- = pahalı
        """
        if not benchmark_price or benchmark_price == 0:
            return 50.0

        ratio = current_price / benchmark_price
        score = 50 + ((1.0 - ratio) * 100)
        return round(max(0.0, min(100.0, score)), 1)

    # ── Satisfaction Score ─────────────────────────────────────────

    def calculate_satisfaction_score(self, rating: Optional[float], review_count: Optional[int]) -> float:
        """
        Rating ve yorum sayısına dayalı güvenilirlik skoru. 0-100.
        """
        if rating is None:
            return 50.0  # Veri yoksa nötr

        base_score = (rating / 5.0) * 100 if rating <= 5.0 else rating

        # Yorum sayısı güveni artırır
        if review_count is None or review_count < 5:
            return round((base_score + 50) / 2, 1)

        return round(base_score, 1)

    # ── Ticker Üretimi ─────────────────────────────────────────────

    def generate_ticker(self, product_name: str, category: str) -> str:
        """
        Ürün adından otomatik Ticker üretir (örn: APL-IPH-342).
        """
        words = re.findall(r'[A-Za-z0-9]+', product_name.upper())
        if not words:
            return "UNK-001"

        brand = words[0][:3]
        model = "".join([w[:2] for w in words[1:3]]) if len(words) > 1 else words[0][-3:]
        suffix = str(random.randint(100, 999))
        return f"{brand}-{model}-{suffix}"

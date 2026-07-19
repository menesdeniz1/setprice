# -*- coding: utf-8 -*-
"""
AI Karar Motoru — ücretsiz katmanlı birden fazla LLM sağlayıcısını sırayla
dener (biri kotasını bitirirse/başarısız olursa otomatik bir sonrakine geçer).
Hiçbir sağlayıcı yanıt veremezse None döner; çağıran taraf mevcut kararı
DB'de olduğu gibi bırakır (boş/şablon yorum yazılmaz).

decision_engine.DecisionEngine'daki hesaplama yardımcıları (trend, dip bölge,
bull-trap, value/satisfaction score) burada AI'ın kararına "gerçek sayılarla"
zemin hazırlamak için kullanılıyor — nihai BUY/WAIT/AVOID kararını ve
gerekçe metnini artık sabit bir if/elif ağacı değil, model üretiyor.
"""
from typing import Dict, Optional
import json
import logging
import os
import re

import requests

from .decision_engine import DecisionEngine

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SEC = 20

PROVIDERS = [
    {
        "name": "gemini",
        "kind": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-2.5-flash",
    },
    {
        "name": "groq",
        "kind": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    {
        "name": "cerebras",
        "kind": "openai_compat",
        "base_url": "https://api.cerebras.ai/v1/chat/completions",
        "api_key_env": "CEREBRAS_API_KEY",
        "model": "llama-3.3-70b",
    },
    {
        "name": "openrouter",
        "kind": "openai_compat",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    {
        "name": "github_models",
        "kind": "openai_compat",
        "base_url": "https://models.github.ai/inference/chat/completions",
        "api_key_env": "GITHUB_MODELS_TOKEN",
        "model": "openai/gpt-4o-mini",
    },
]


def _build_prompt(context: Dict) -> str:
    engine = DecisionEngine()
    history = context.get("history") or []
    current_price = context.get("current_price") or 0.0
    benchmark_price = context.get("benchmark_price")

    trend = engine.analyze_trend(history)
    bottom = engine.detect_bottom_zone(current_price, history)
    is_bull_trap = engine.detect_bull_trap(current_price, history)
    computed_value = engine.calculate_value_score(current_price, benchmark_price)
    satisfaction = engine.calculate_satisfaction_score(
        context.get("rating"), context.get("review_count")
    )

    return f"""Sen bir e-ticaret fiyat analistisin. Aşağıdaki ürün için BUY (satın al), WAIT (bekle) veya AVOID (kaçın) kararı ver ve kısa bir Türkçe gerekçe yaz.

Ürün: {context.get('name', 'Bilinmiyor')}
Kategori: {context.get('category', 'Bilinmiyor')}
Güncel fiyat: {current_price} TL
Karşılaştırma fiyatı (benzer ürünler ortalaması): {benchmark_price if benchmark_price else 'yok'}
Fiyat/değer oranı skoru (0-100, 50=adil fiyat): {computed_value}
Fiyat trendi: {trend['direction']} (güç: {trend['strength']})
Tarihsel dip bölgede mi: {'evet' if bottom['is_near_bottom'] else 'hayır'} (yüzdelik dilim: {bottom['percentile']})
Şüpheli/sahte indirim tespit edildi mi: {'evet' if is_bull_trap else 'hayır'}
Kullanıcı memnuniyeti skoru (0-100): {satisfaction}

SADECE aşağıdaki JSON formatında cevap ver, başka hiçbir metin ekleme:
{{"signal": "BUY", "value_score": 0-100 arası sayı, "reasoning": "1-2 cümlelik kısa Türkçe gerekçe"}}
signal alanı sadece BUY, WAIT veya AVOID olabilir."""


def _extract_json(text: str) -> Optional[Dict]:
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def _validate_decision(data: Optional[Dict]) -> Optional[Dict]:
    if not isinstance(data, dict):
        return None
    signal = str(data.get("signal", "")).strip().upper()
    if signal not in ("BUY", "WAIT", "AVOID"):
        return None
    try:
        value_score = float(data.get("value_score"))
    except (TypeError, ValueError):
        return None
    value_score = max(0.0, min(100.0, value_score))
    reasoning = str(data.get("reasoning", "")).strip()
    if not reasoning:
        return None
    return {"signal": signal, "value_score": round(value_score, 1), "reasoning": reasoning}


def _call_openai_compatible(provider: Dict, api_key: str, prompt: str) -> str:
    resp = requests.post(
        provider["base_url"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": provider["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 300,
        },
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_gemini(provider: Dict, api_key: str, prompt: str) -> str:
    resp = requests.post(
        provider["base_url"],
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def has_any_provider_configured() -> bool:
    return any(os.environ.get(p["api_key_env"]) for p in PROVIDERS)


def generate_ai_decision(context: Dict) -> Optional[Dict]:
    """
    Her aktif sağlayıcıyı sırayla dener (API key'i ortam değişkeninde
    tanımlı olanlar). İlk geçerli JSON döndüren sağlayıcının sonucu
    kullanılır. Hiçbiri başarılı olmazsa None döner.
    """
    prompt = _build_prompt(context)

    for provider in PROVIDERS:
        api_key = os.environ.get(provider["api_key_env"])
        if not api_key:
            continue

        try:
            if provider["kind"] == "gemini":
                raw_text = _call_gemini(provider, api_key, prompt)
            else:
                raw_text = _call_openai_compatible(provider, api_key, prompt)

            validated = _validate_decision(_extract_json(raw_text))
            if validated:
                logger.info(f"AI karar üretildi ({provider['name']}): {validated['signal']}")
                return validated

            logger.warning(f"{provider['name']} geçersiz/boş yanıt döndürdü, sıradaki sağlayıcıya geçiliyor")
        except requests.exceptions.RequestException as e:
            logger.warning(f"{provider['name']} çağrısı başarısız: {e}, sıradaki sağlayıcıya geçiliyor")
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f"{provider['name']} yanıtı ayrıştırılamadı: {e}, sıradaki sağlayıcıya geçiliyor")

    return None

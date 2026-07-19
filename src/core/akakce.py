# -*- coding: utf-8 -*-
import json
import os
import random
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from bs4 import BeautifulSoup

from .models import AlternativeRow
from .price_parser import parse_price

class AkakceSearcher:
    def __init__(self, config: dict, logger):
        self.config = config
        self.logger = logger
        
        self._browser_ctx = None
        self._page = None
        self._playwright = None
        
        self._cache = {}
        self._cache_file = config.get("paths", {}).get("reports_dir", "./data/reports") + "/akakce_cache.json"
        self._cache_hours = config.get("alternatives", {}).get("cache_hours", 24)
        
        self._load_cache()

    def _load_cache(self) -> None:
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except Exception as e:
                self.logger.warning(f"Cache yüklenemedi: {e}")
                self._cache = {}

    def _save_cache(self) -> None:
        os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"Cache kaydedilemedi: {e}")

    def _init_playwright(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright kurulu değil!")
            
        if not self._playwright:
            self.logger.info("Akakçe için Playwright başlatılıyor...")
            self._playwright = sync_playwright().start()
            browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._browser_ctx = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                locale="tr-TR",
                timezone_id="Europe/Istanbul"
            )
            self._page = self._browser_ctx.new_page()
            self._page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def search_batch(self, terms: Dict[str, List[str]], top_n: int = 3) -> List[AlternativeRow]:
        """
        Benzersiz arama terimlerini arar.
        terms: {arama_terimi: [ilgili_ürün_adları]}
        """
        if not self.config.get("alternatives", {}).get("enabled", True):
            return []
            
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.error("Playwright kurulu değil, Akakçe muadil araması yapılamaz!")
            return []
            
        all_alternatives = []
        delay_range = self.config.get("alternatives", {}).get("delay_between_sec", [3, 6])
        
        now = datetime.now()
        
        for term, products in terms.items():
            if not term: continue
            
            # Cache kontrolü
            cached = self._cache.get(term)
            if cached:
                try:
                    cache_time = datetime.fromisoformat(cached["timestamp"])
                    if now - cache_time < timedelta(hours=self._cache_hours):
                        self.logger.info(f"[Akakçe] Cache'den alındı: '{term}'")
                        for p in products:
                            for idx, res in enumerate(cached["results"][:top_n], 1):
                                all_alternatives.append(AlternativeRow(
                                    product=p,
                                    search_term=term,
                                    rank=idx,
                                    alt_product=res["title"],
                                    alt_price=res["price"],
                                    alt_seller=res.get("seller", "Akakçe"),
                                    alt_link=res["link"],
                                    updated=now
                                ))
                        continue
                except:
                    pass
            
            # Yeni arama yap
            self.logger.info(f"[Akakçe] Aranıyor: '{term}'")
            try:
                results = self.search(term, top_n)
                if results:
                    self._cache[term] = {
                        "timestamp": now.isoformat(),
                        "results": results
                    }
                    self._save_cache()
                    
                    for p in products:
                        for idx, res in enumerate(results[:top_n], 1):
                            all_alternatives.append(AlternativeRow(
                                product=p,
                                search_term=term,
                                rank=idx,
                                alt_product=res["title"],
                                alt_price=res["price"],
                                alt_seller=res.get("seller", "Akakçe"),
                                alt_link=res["link"],
                                updated=now
                            ))
                
                # Akakçe'ye nazik ol
                delay = random.uniform(delay_range[0], delay_range[1])
                time.sleep(delay)
                
            except Exception as e:
                self.logger.error(f"[Akakçe] Arama hatası '{term}': {e}")
                
        return all_alternatives

    def _infer_search_term(self, name: str, category: str) -> str:
        """
        Ürün adından gereksiz detayları kırparak (varsa) Akakçe arama terimi oluşturur.
        """
        if not name:
            return ""
        # Basitçe ilk 60 karakteri veya bazı ekleri atarak arama yapalım
        term = name.split("(")[0].strip() if "(" in name else name
        term = term.split("-")[0].strip() if "-" in term else term
        term = term.split("|")[0].strip() if "|" in term else term
        # Kategoriyi eklemek yerine sadece ürün adının kısa halini kullanıyoruz
        # Arama başarısı için çok uzun stringleri kırp
        return term[:60].strip()

    def search(self, term: str, top_n: int = 3) -> List[dict]:
        """Tek bir terimi arar ve list_dict döner."""
        self._init_playwright()
        
        encoded_term = urllib.parse.quote_plus(term)
        # Fiyata göre artan sıralama parametresi s=2
        url = f"https://www.akakce.com/arama/?q={encoded_term}&s=2"
        
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Cloudflare engeli mi?
            if response and response.status in [403, 429]:
                self.logger.warning(f"[Akakçe] 403/429 aldı. Cloudflare olabilir.")
                return []
                
            self._page.wait_for_timeout(2000)
            html = self._page.content()
            
            return self._parse_results(html, top_n)
            
        except PlaywrightTimeoutError:
            self.logger.warning(f"[Akakçe] Timeout: {url}")
            return []
        except Exception as e:
            self.logger.warning(f"[Akakçe] Playwright hatası: {e}")
            return []

    def _parse_results(self, html: str, top_n: int) -> List[dict]:
        soup = BeautifulSoup(html, 'lxml')
        results = []
        
        # Akakçe ürün listesi selector'u
        items = soup.select('ul#APL li')
        if not items:
            items = soup.select('li.w')
        if not items:
            items = soup.select('div.p')
            
        for item in items:
            if len(results) >= top_n:
                break
                
            # Başlık ve link
            a_tag = item.find('a')
            if not a_tag: continue
            
            title = a_tag.get('title') or a_tag.get_text(strip=True)
            link = a_tag.get('href')
            if link and not link.startswith('http'):
                link = f"https://www.akakce.com{link}"
                
            # Fiyat
            price_elem = item.select_one('span.pt_v8')
            if not price_elem:
                price_elem = item.select_one('span.pt_v9')
            if not price_elem:
                price_elem = item.select_one('[class*="price"]')
            if not price_elem:
                price_elem = item.select_one('[class*="prc"]')
                
            if not price_elem: continue
            
            raw_price = price_elem.get_text(strip=True)
            price = parse_price(raw_price, self.config)
            
            if title and link and price:
                results.append({
                    "title": title[:100],
                    "price": price,
                    "link": link,
                    "seller": "Akakçe (Karşılaştır)"
                })
                
        return results

    def close(self):
        if self._playwright:
            self.logger.info("Akakçe Playwright kapatılıyor...")
            try:
                if self._browser_ctx: self._browser_ctx.close()
                self._playwright.stop()
            except:
                pass
            self._playwright = None
            self._browser_ctx = None
            self._page = None

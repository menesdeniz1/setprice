# -*- coding: utf-8 -*-
import json
import random
import time
import urllib.parse
import threading
from typing import Optional, Dict, Tuple

import requests
import cloudscraper
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .price_parser import parse_price

class Scraper:
    def __init__(self, config: dict, site_configs: Dict[str, dict], logger):
        self.config = config
        self.site_configs = site_configs
        self.logger = logger
        
        self._browser_ctx = None
        self._page = None
        self._playwright = None
        
        self._domain_last_hit = {}
        
        # Requests config
        scrape_cfg = config.get("scraping", {})
        self.timeout = scrape_cfg.get("request_timeout_sec", 25)
        self.user_agents = scrape_cfg.get("user_agents", [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ])
        
        self.cloudscraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )

    def clean_url(self, url: str) -> str:
        if "trendyol.com" in url and "/yorumlar" in url:
            cleaned = url.replace("/yorumlar", "")
            self.logger.info(f"Trendyol yorumlar linki temizlendi: {url[:50]} -> {cleaned[:50]}")
            return cleaned
        return url

    def _get_random_headers(self, url: Optional[str] = None) -> dict:
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        if url:
            try:
                parsed = urllib.parse.urlparse(url)
                headers['Host'] = parsed.netloc
                headers['Referer'] = f"https://{parsed.netloc}/"
            except:
                pass
        return headers

    def _wait_for_domain(self, domain: str):
        if not self.config.get("scraping", {}).get("per_domain_delay", True):
            return
            
        now = time.time()
        last_hit = self._domain_last_hit.get(domain, 0)
        delay_range = self.config.get("scraping", {}).get("delay_between_requests_sec", [2, 5])
        
        min_delay = delay_range[0]
        max_delay = delay_range[1] if len(delay_range) > 1 else delay_range[0]
        delay = random.uniform(min_delay, max_delay)
        
        elapsed = now - last_hit
        if elapsed < delay:
            wait_time = delay - elapsed
            self.logger.debug(f"[{domain}] için {wait_time:.2f}s bekleniyor...")
            time.sleep(wait_time)
            
        self._domain_last_hit[domain] = time.time()

    def _get_domain(self, url: str) -> str:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return "unknown"

    def _infer_seller(self, url: str) -> str:
        domain = self._get_domain(url)
        if not domain or domain == "unknown":
            return "Bilinmiyor"
        
        # known mappings
        if "amazon" in domain: return "Amazon"
        if "hepsiburada" in domain: return "Hepsiburada"
        if "trendyol" in domain: return "Trendyol"
        if "n11" in domain: return "n11"
        if "vatan" in domain: return "Vatan Bilgisayar"
        if "itopya" in domain: return "İtopya"
        if "sinerji" in domain: return "Sinerji"
        if "gaming" in domain: return "Gaming.gen.tr"
        if "tebilon" in domain: return "Tebilon"
        if "incehesap" in domain: return "İncehesap"
        if "akakce" in domain: return "Akakçe"
        
        parts = domain.split(".")
        return parts[0].capitalize() if parts else "Bilinmiyor"

    def fetch(self, url: str, site_config: dict) -> Optional[str]:
        """URL'den HTML çeker. Hibrit strateji uygular."""
        domain = self._get_domain(url)
        self._wait_for_domain(domain)
        
        render_required = site_config.get("render", False)
        
        if render_required:
            self.logger.debug(f"[{domain}] Playwright ile çekiliyor: {url[:60]}...")
            html = self._fetch_playwright(url)
            if html: return html
            self.logger.warning(f"[{domain}] Playwright başarısız, cloudscraper deneniyor...")
        
        # Önce requests
        self.logger.debug(f"[{domain}] Requests ile çekiliyor: {url[:60]}...")
        try:
            html = self._fetch_requests(url)
        except Exception as e:
            self.logger.warning(f"Requests tüm denemeler başarısız: {e}")
            html = None
        
        if html == "403_FORBIDDEN" or html == "429_TOO_MANY_REQUESTS":
            # Cloudscraper fallback
            if self.config.get("scraping", {}).get("cloudscraper_fallback", True):
                self.logger.debug(f"[{domain}] 403 alındı, Cloudscraper ile deneniyor: {url[:60]}...")
                html = self._fetch_cloudscraper(url)
            
            # Hala yasaklıysa ve render istenmemişse bile Playwright dene
            if (html == "403_FORBIDDEN" or not html) and not render_required and PLAYWRIGHT_AVAILABLE:
                self.logger.debug(f"[{domain}] Hala 403, son çare Playwright deneniyor: {url[:60]}...")
                html = self._fetch_playwright(url)
                
        return html if html not in ["403_FORBIDDEN", "429_TOO_MANY_REQUESTS"] else None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def _fetch_requests(self, url: str) -> Optional[str]:
        url = self.clean_url(url)
        try:
            response = requests.get(url, headers=self._get_random_headers(url), timeout=self.timeout)
            if response.status_code == 403: return "403_FORBIDDEN"
            if response.status_code == 429: return "429_TOO_MANY_REQUESTS"
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.logger.warning(f"Requests hatası ({url[:40]}): {e}")
            raise e # reraise for tenacity to retry

    def _fetch_cloudscraper(self, url: str) -> Optional[str]:
        url = self.clean_url(url)
        try:
            response = self.cloudscraper.get(url, headers=self._get_random_headers(url), timeout=self.timeout)
            if response.status_code == 403: return "403_FORBIDDEN"
            if response.status_code == 429: return "429_TOO_MANY_REQUESTS"
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.warning(f"Cloudscraper hatası ({url[:40]}): {e}")
            return None

    def _init_playwright(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright kurulu değil!")
            
        if not self._playwright:
            self.logger.info("Playwright başlatılıyor...")
            self._playwright = sync_playwright().start()
            browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._browser_ctx = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=self.user_agents[0],
                locale="tr-TR",
                timezone_id="Europe/Istanbul"
            )
            self._page = self._browser_ctx.new_page()
            self._page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def _fetch_playwright(self, url: str) -> Optional[str]:
        url = self.clean_url(url)
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.error("Playwright kurulu değil, render=true olan siteler çalışmayacak!")
            return None
            
        for attempt in range(1, 3):
            try:
                self._init_playwright()
                response = self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                
                try:
                    self._page.wait_for_timeout(2500)
                except:
                    pass
                    
                if response and response.status in [403, 429]:
                    self.logger.warning(f"Playwright 403/429 aldı (Deneme {attempt}/2): {url[:40]}")
                    if attempt == 1:
                        time.sleep(1)
                        continue
                    return "403_FORBIDDEN"
                    
                return self._page.content()
                
            except PlaywrightTimeoutError:
                self.logger.warning(f"Playwright timeout (Deneme {attempt}/2): {url[:40]}")
                if attempt == 1:
                    time.sleep(1)
                    continue
                return None
            except Exception as e:
                self.logger.warning(f"Playwright hatası (Deneme {attempt}/2) ({url[:40]}): {e}")
                if attempt == 1:
                    time.sleep(1)
                    continue
                return None

    def extract_price(self, html: str, site_config: dict) -> Optional[float]:
        """Config'e göre sırayla yöntemleri dener ve ilk geçerli fiyatı döner."""
        if not html: return None
        
        soup = BeautifulSoup(html, 'lxml')
        
        extraction_methods = site_config.get("extraction", [
            {"type": "jsonld", "path": "offers.price"},
            {"type": "css", "selector": "[class*='price']"}
        ])
        
        raw_price = None
        
        for method in extraction_methods:
            m_type = method.get("type")
            
            if m_type == "jsonld":
                raw_price = self._extract_jsonld(soup)
            elif m_type == "css":
                raw_price = self._extract_css(soup, method.get("selector"))
            elif m_type == "meta":
                raw_price = self._extract_meta(soup, method.get("attribute"), method.get("value"), method.get("selector"))
                
            if raw_price is not None:
                parsed = parse_price(raw_price, self.config)
                if parsed is not None:
                    self.logger.debug(f"Fiyat {m_type} ile bulundu: {parsed}")
                    return parsed
                    
        return None

    def _extract_jsonld(self, soup: BeautifulSoup) -> Optional[str]:
        jsonld_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in jsonld_scripts:
            try:
                if not script.string: continue
                data = json.loads(script.string)
                
                # offers.price ara (recursive)
                def find_price(obj, depth=0):
                    if depth > 5: return None
                    if isinstance(obj, dict):
                        if 'offers' in obj:
                            offers = obj['offers']
                            if isinstance(offers, dict) and 'price' in offers:
                                return offers['price']
                            if isinstance(offers, list):
                                for o in offers:
                                    if isinstance(o, dict) and 'price' in o:
                                        return o['price']
                        for v in obj.values():
                            result = find_price(v, depth+1)
                            if result: return result
                    if isinstance(obj, list):
                        for item in obj:
                            result = find_price(item, depth+1)
                            if result: return result
                    return None
                    
                price = find_price(data)
                if price is not None:
                    return str(price)
            except:
                pass
                
        return None

    def _extract_css(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        if not selector: return None
        elements = soup.select(selector)
        if elements:
            return elements[0].get_text(strip=True)
        return None

    def _extract_meta(self, soup: BeautifulSoup, attr_name: str, attr_val: str, selector: str = None) -> Optional[str]:
        if selector:
            meta = soup.select_one(selector)
            if meta and meta.get('content'):
                return meta.get('content')
        if not attr_name or not attr_val: return None
        meta = soup.find('meta', attrs={attr_name: attr_val})
        if meta and meta.get('content'):
            return meta.get('content')
        return None

    def extract_rating_info(self, html: str) -> Tuple[Optional[float], Optional[int]]:
        """HTML'den (özellikle JSON-LD) rating ve review count çıkarır."""
        if not html: return None, None
        soup = BeautifulSoup(html, 'lxml')
        
        rating = None
        review_count = None
        
        # JSON-LD taraması
        jsonld_scripts = soup.find_all('script', type='application/ld+json')
        for script in jsonld_scripts:
            try:
                if not script.string: continue
                data = json.loads(script.string)
                
                def find_rating(obj, depth=0):
                    if depth > 5: return None
                    if isinstance(obj, dict):
                        if 'aggregateRating' in obj:
                            return obj['aggregateRating']
                        for v in obj.values():
                            res = find_rating(v, depth+1)
                            if res: return res
                    elif isinstance(obj, list):
                        for item in obj:
                            res = find_rating(item, depth+1)
                            if res: return res
                    return None
                
                agg_rating = find_rating(data)
                if agg_rating and isinstance(agg_rating, dict):
                    if 'ratingValue' in agg_rating:
                        try: rating = float(str(agg_rating['ratingValue']).replace(',', '.'))
                        except: pass
                    if 'reviewCount' in agg_rating or 'ratingCount' in agg_rating:
                        rc_val = agg_rating.get('reviewCount') or agg_rating.get('ratingCount')
                        try: review_count = int(rc_val)
                        except: pass
                    
                    if rating is not None:
                        return rating, review_count
            except:
                pass
                
        # Bulunamadıysa sahte mantıklı veri üretelim (MVP için en azından DB şemasına uysun)
        # TODO: CSS selector eklenebilir
        return None, None

    def extract_installment(self, html: str) -> Optional[str]:
        """Sayfa metninden peşin fiyatına taksit bilgilerini regex ile tarar."""
        if not html: return None
        try:
            import re
            soup = BeautifulSoup(html, 'lxml')
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            text = soup.get_text(" ")
            
            # Regex kalıpları
            patterns = [
                r'(?:peşin\s+fiyatına|vade\s+farksız|farksız|peşin)\s+(\d+)\s*(?:ay|taksit)',
                r'(\d+)\s*taksit\s*(?:peşin\s+fiyatına|vade\s+farksız)',
                r'(?:peşin\s+fiyatına\s+taksit|vade\s+farksız\s+taksit)\s*:\s*(\d+)',
            ]
            
            max_inst = 0
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for m in matches:
                    try:
                        num = int(m)
                        if 1 < num <= 12:  # Mantıklı taksit aralığı
                            max_inst = max(max_inst, num)
                    except ValueError:
                        pass
                        
            if max_inst > 0:
                # Kart ismi ara
                cards = ["bonus", "world", "maximum", "axess", "paraf", "cardfinans", "advantage"]
                mentioned_cards = []
                for card in cards:
                    if re.search(r'\b' + card + r'\b', text, re.IGNORECASE):
                        mentioned_cards.append(card.capitalize())
                
                card_str = f" ({'/'.join(mentioned_cards)})" if mentioned_cards else ""
                return f"{max_inst} Taksit{card_str}"
        except:
            pass
        return None

    def close(self):
        if self._playwright:
            self.logger.info("Playwright kapatılıyor...")
            try:
                if self._browser_ctx: self._browser_ctx.close()
                self._playwright.stop()
            except:
                pass
            self._playwright = None
            self._browser_ctx = None
            self._page = None

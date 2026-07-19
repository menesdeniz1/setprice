# -*- coding: utf-8 -*-
import os
import yaml
from typing import Dict, Optional
import urllib.parse

class ConfigLoader:
    def __init__(self, config_path: str = "config/config.yaml", sites_dir: str = "config/sites"):
        self.config_path = config_path
        self.sites_dir = sites_dir

    def load(self) -> dict:
        """Ana config dosyasını yükler."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config dosyası bulunamadı: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        return config

    def load_site_configs(self) -> Dict[str, dict]:
        """Tüm site config dosyalarını yükler. {domain: config} döner."""
        site_configs = {}
        if not os.path.exists(self.sites_dir):
            return site_configs
            
        for filename in os.listdir(self.sites_dir):
            if filename.endswith('.yaml') and not filename.startswith('_'):
                filepath = os.path.join(self.sites_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    site_cfg = yaml.safe_load(f)
                    if site_cfg and 'domain' in site_cfg:
                        # domain değerinden www. kısmını atalım, tutarlılık için
                        domain = site_cfg['domain'].lower().replace('www.', '')
                        site_configs[domain] = site_cfg
                        
        return site_configs

    def get_site_config(self, url: str, site_configs: Dict[str, dict]) -> Optional[dict]:
        """URL'den domaini çıkarıp eşleşen site config'i döner."""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
                
            # Tam eşleşme
            if domain in site_configs:
                return site_configs[domain]
                
            # Kısmi eşleşme (örn: satici.trendyol.com -> trendyol.com)
            for site_domain, cfg in site_configs.items():
                if domain.endswith(site_domain):
                    return cfg
                    
        except Exception:
            pass
            
        return None

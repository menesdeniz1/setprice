# -*- coding: utf-8 -*-
import sys
import os
from loguru import logger
from datetime import datetime

def setup_logger(config: dict) -> logger:
    """
    Loguru yapılandırması.
    """
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    logs_dir = config.get("paths", {}).get("logs_dir", "./logs")
    
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        
    log_file = os.path.join(logs_dir, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Varsayılan handler'ı kaldır
    logger.remove()
    
    # Konsol handler
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level=log_level, colorize=True)
    
    # Dosya handler
    rotate_mb = log_config.get("rotate_mb", 10)
    keep_backups = log_config.get("keep_backups", 5)
    logger.add(log_file, format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}", level=log_level, rotation=f"{rotate_mb} MB", retention=keep_backups, encoding="utf-8")
    
    return logger

# Singleton benzeri bir yapı için (başlatıldıktan sonra import logger_instance olarak kullanılabilir)
# Ancak genelde logger'ı her modülde direkt import edip logger.info() kullanacağız.

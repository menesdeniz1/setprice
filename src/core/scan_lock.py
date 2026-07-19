# -*- coding: utf-8 -*-
"""
Tarama Kilidi — CLI ve Web'in aynı anda tarama yapmasını engeller.
Basit dosya kilidi (filelock) kullanır.
"""
import os
import filelock

SCAN_LOCK_PATH = os.path.join("data", ".scan.lock")


def get_scan_lock(timeout: int = 10) -> filelock.FileLock:
    """Tarama kilidi döner. Context manager olarak kullanılır:

    try:
        with get_scan_lock():
            # taramayı yap
    except filelock.Timeout:
        logger.warning("Başka bir tarama çalışıyor, atlanıyor.")
    """
    os.makedirs(os.path.dirname(SCAN_LOCK_PATH), exist_ok=True)
    return filelock.FileLock(SCAN_LOCK_PATH, timeout=timeout)

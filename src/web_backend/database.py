# -*- coding: utf-8 -*-
"""
Web Backend Database — Core database modülünden re-export.
Geriye dönük uyumluluk için mevcut import yollarını korur.
"""
from src.core.database import (
    engine,
    Base,
    get_db,
    get_db_session,
    SessionLocal,
    run_lightweight_migrations,
    init_db,
)

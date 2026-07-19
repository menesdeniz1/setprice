# -*- coding: utf-8 -*-
"""
SetPrice Core — Paylaşılan veritabanı bağlantısı.
CLI ve Web backend aynı DB'yi kullanır.
"""
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/setprice.sqlite")

# SQLite için thread güvenliği ayarı
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency injection için DB session generator."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """CLI ve background tasks için doğrudan DB session döner."""
    return SessionLocal()


def run_lightweight_migrations():
    """SQLite için basit otomatik migrasyon: modelde tanımlı olup mevcut DB
    tablosunda bulunmayan kolonları ALTER TABLE ile ekler."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                col_type = column.type.compile(engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}'))


def init_db():
    """Tabloları oluştur ve migration'ları çalıştır."""
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()

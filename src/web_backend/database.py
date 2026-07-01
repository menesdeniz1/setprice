# -*- coding: utf-8 -*-
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/setprice.sqlite")

# SQLite için thread güvenliği ayarı
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations():
    """SQLite için basit otomatik migrasyon: modelde tanımlı olup mevcut DB
    tablosunda bulunmayan kolonları ALTER TABLE ile ekler.

    Yeni TABLOLAR zaten Base.metadata.create_all ile oluşturulur; bu fonksiyon
    sadece var olan bir tabloya sonradan eklenen KOLONLAR içindir (ör.
    ProductSet.template_name). Kolon/tablo adları kullanıcı girdisi değil,
    Python model tanımlarından geldiği için raw SQL güvenlidir.

    Not: Bu proje büyüdükçe (Faz 5) gerçek bir migration aracına (Alembic)
    geçmek daha sürdürülebilir olur — bu yalnızca solo/erken aşama için
    yeterli, hafif bir çözümdür.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue  # create_all zaten oluşturdu, ekstra işlem gerekmiyor
            existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                col_type = column.type.compile(engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}'))

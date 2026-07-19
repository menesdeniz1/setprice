# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    telegram_chat_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sets = relationship("ProductSet", back_populates="user", cascade="all, delete-orphan")


class ProductSet(Base):
    __tablename__ = "product_sets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    target_budget = Column(Float, default=0.0)
    template_name = Column(String, nullable=True)  # bilgilendirme amaçlı: hangi şablonla oluşturuldu
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sets")
    products = relationship("Product", back_populates="product_set", cascade="all, delete-orphan")
    categories = relationship("SetCategory", back_populates="product_set", cascade="all, delete-orphan", order_by="SetCategory.sort_order")


class SetCategory(Base):
    """Bir Set'e özgü, kullanıcının düzenleyebildiği kategori/slot listesi.
    Şablon seçildiğinde ön-doldurulur, sonrasında serbestçe eklenip/çıkarılabilir."""
    __tablename__ = "set_categories"

    id = Column(Integer, primary_key=True, index=True)
    set_id = Column(Integer, ForeignKey("product_sets.id"), nullable=False)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)

    product_set = relationship("ProductSet", back_populates="categories")

    __table_args__ = (
        UniqueConstraint('set_id', 'name', name='uix_set_category_name'),
    )


class DomainHealth(Base):
    """Hafif scraper gözlemlenebilirliği: hangi domain ne sıklıkla başarılı/
    başarısız oluyor. Tekil satır per domain (upsert), sınırsız büyüyen bir
    log tablosu değil — Faz 5'in "hafif" amacına uygun."""
    __tablename__ = "domain_health"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True, nullable=False)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_status = Column(String, nullable=True)  # 'OK' | 'FAILED'
    last_checked_at = Column(DateTime, default=datetime.utcnow)


class BenchmarkEntry(Base):
    """CPU/GPU performans referans skorları (bkz. benchmark_utils.py)."""
    __tablename__ = "benchmark_entries"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    name = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    source = Column(String, default="PassMark (seed)")

    __table_args__ = (
        UniqueConstraint('category', 'name', name='uix_benchmark_category_name'),
    )


class LibraryProduct(Base):
    __tablename__ = "library_products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    original_link = Column(String, index=True, nullable=False)
    current_price = Column(Float, nullable=True)
    current_seller = Column(String, nullable=True)
    current_installment = Column(String, nullable=True)
    status = Column(String, default="BEKLEMEDE")
    
    # Yeni Varlık (Asset) ve Karar Motoru Alanları
    ticker = Column(String, unique=True, index=True, nullable=True)
    value_score = Column(Float, nullable=True)
    satisfaction_score = Column(Float, nullable=True)
    decision_signal = Column(String, default="WAIT")
    decision_reasoning = Column(String, nullable=True)  # Neden BUY/WAIT/AVOID?
    benchmark_price = Column(Float, nullable=True)
    price_alert_threshold = Column(Float, nullable=True)  # Fiyat bu altına düşerse alert
    rating = Column(Float, nullable=True)  # Mağaza puanı (0-5)
    review_count = Column(Integer, nullable=True)  # Yorum sayısı

    # Performans skoru (CPU/GPU gibi kategoriler için) — kategorisi içinde 0-100
    # normalize edilmiş PassMark bazlı skor. benchmark_match_name, hangi referans
    # ürünle eşleştiğini gösterir (şeffaflık için).
    performance_score = Column(Float, nullable=True)
    benchmark_match_name = Column(String, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ai_decision_updated_at = Column(DateTime, nullable=True)  # AI karar motoru en son ne zaman başarıyla çalıştı

    __table_args__ = (
        UniqueConstraint('user_id', 'original_link', name='uix_user_link'),
    )

    set_links = relationship("Product", back_populates="library_product", cascade="all, delete-orphan")
    history = relationship("PriceHistory", back_populates="library_product", cascade="all, delete-orphan")
    alternatives = relationship("Alternative", back_populates="library_product", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="library_product", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    set_id = Column(Integer, ForeignKey("product_sets.id"), nullable=False)
    library_product_id = Column(Integer, ForeignKey("library_products.id"), nullable=False)
    locked_price = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product_set = relationship("ProductSet", back_populates="products")
    library_product = relationship("LibraryProduct", back_populates="set_links")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    library_product_id = Column(Integer, ForeignKey("library_products.id"), nullable=False)
    price = Column(Float, nullable=False)
    seller = Column(String, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    library_product = relationship("LibraryProduct", back_populates="history")


class Alternative(Base):
    __tablename__ = "alternatives"

    id = Column(Integer, primary_key=True, index=True)
    library_product_id = Column(Integer, ForeignKey("library_products.id"), nullable=False)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    seller = Column(String, nullable=True)
    link = Column(String, nullable=False)
    # 'same_product' = başlık benzerliği yüksek, muhtemelen aynı ürün farklı satıcı
    # 'similar'      = spec bazlı muadil, farklı ama karşılaştırılabilir ürün
    match_type = Column(String, default="similar")
    match_confidence = Column(Float, nullable=True)  # 0-1, başlık benzerlik oranı
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    library_product = relationship("LibraryProduct", back_populates="alternatives")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    library_product_id = Column(Integer, ForeignKey("library_products.id"), nullable=False)
    alert_type = Column(String, nullable=False)  # THRESHOLD, BULL_TRAP, SIGNAL_CHANGE, TREND_DIP
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    library_product = relationship("LibraryProduct", back_populates="alerts")


class ScanCheckpoint(Base):
    """Tarama checkpoint'leri — yarıda kalan taramaları kaldığı yerden devam
    ettirmek için. Her run_once() çağrısı benzersiz bir scan_session_id üretir.
    Tarama başarıyla tamamlanınca checkpoint'ler temizlenir."""
    __tablename__ = "scan_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    scan_session_id = Column(String, index=True, nullable=False)
    url = Column(String, nullable=False)
    price = Column(Float, nullable=True)
    status = Column(String, nullable=True)  # OK / FAILED / FLAGGED
    created_at = Column(DateTime, default=datetime.utcnow)

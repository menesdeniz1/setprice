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
    created_at = Column(DateTime, default=datetime.utcnow)

    sets = relationship("ProductSet", back_populates="user", cascade="all, delete-orphan")


class ProductSet(Base):
    __tablename__ = "product_sets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    target_budget = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sets")
    products = relationship("Product", back_populates="product_set", cascade="all, delete-orphan")


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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'original_link', name='uix_user_link'),
    )

    set_links = relationship("Product", back_populates="library_product", cascade="all, delete-orphan")
    history = relationship("PriceHistory", back_populates="library_product", cascade="all, delete-orphan")
    alternatives = relationship("Alternative", back_populates="library_product", cascade="all, delete-orphan")


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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    library_product = relationship("LibraryProduct", back_populates="alternatives")

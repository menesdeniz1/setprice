import bcrypt
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from . import models, schemas

# --- Password Utilities ---
def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# --- User CRUD ---
def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# --- Set CRUD ---
def get_sets_by_user(db: Session, user_id: int) -> List[models.ProductSet]:
    return db.query(models.ProductSet).filter(models.ProductSet.user_id == user_id).all()

def get_set_by_id(db: Session, set_id: int) -> Optional[models.ProductSet]:
    return db.query(models.ProductSet).filter(models.ProductSet.id == set_id).first()

def create_set(db: Session, set_in: schemas.ProductSetCreate, user_id: int) -> models.ProductSet:
    db_set = models.ProductSet(**set_in.model_dump(), user_id=user_id)
    db.add(db_set)
    db.commit()
    db.refresh(db_set)
    return db_set

def update_set(db: Session, db_set: models.ProductSet, set_update: schemas.ProductSetUpdate) -> models.ProductSet:
    update_data = set_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_set, field, value)
    db.commit()
    db.refresh(db_set)
    return db_set

def delete_set(db: Session, set_id: int) -> bool:
    db_set = get_set_by_id(db, set_id)
    if db_set:
        db.delete(db_set)
        db.commit()
        return True
    return False


# --- Product CRUD ---
def get_products_by_set(db: Session, set_id: int) -> List[models.Product]:
    return db.query(models.Product).filter(models.Product.set_id == set_id).all()

def get_product_by_id(db: Session, product_id: int) -> Optional[models.Product]:
    return db.query(models.Product).filter(models.Product.id == product_id).first()

def create_product(db: Session, library_product_id: int, set_id: int) -> models.Product:
    db_product = models.Product(
        set_id=set_id,
        library_product_id=library_product_id,
        is_active=True,
        is_locked=False,
        locked_price=None
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, db_product: models.Product, product_update: schemas.ProductUpdate) -> models.Product:
    update_data = product_update.model_dump(exclude_unset=True)
    # is_active, is_locked, locked_price are product/set specific
    for field in ["is_active", "is_locked", "locked_price"]:
        if field in update_data:
            setattr(db_product, field, update_data[field])
            
    # name, category are library product specific!
    lib = db_product.library_product
    if lib:
        for field in ["name", "category"]:
            if field in update_data and update_data[field] is not None:
                setattr(lib, field, update_data[field])
                
    db.commit()
    db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: int) -> bool:
    db_product = get_product_by_id(db, product_id)
    if db_product:
        db.delete(db_product)
        db.commit()
        return True
    return False


# --- Library Product Helpers ---
def get_library_product_by_id(db: Session, library_product_id: int) -> Optional[models.LibraryProduct]:
    return db.query(models.LibraryProduct).filter(models.LibraryProduct.id == library_product_id).first()

def get_library_product_by_link(db: Session, link: str, user_id: int) -> Optional[models.LibraryProduct]:
    return db.query(models.LibraryProduct).filter(
        models.LibraryProduct.original_link == link,
        models.LibraryProduct.user_id == user_id
    ).first()

def get_library_products(db: Session, user_id: int, category: Optional[str] = None) -> List[models.LibraryProduct]:
    query = db.query(models.LibraryProduct).filter(models.LibraryProduct.user_id == user_id)
    if category:
        query = query.filter(models.LibraryProduct.category == category)
    return query.all()

def get_library_products_by_category(db: Session, category: str, user_id: int) -> List[models.LibraryProduct]:
    return db.query(models.LibraryProduct).filter(
        models.LibraryProduct.category == category,
        models.LibraryProduct.user_id == user_id
    ).all()

def get_or_create_library_product(db: Session, name: str, category: str, original_link: str, user_id: int) -> models.LibraryProduct:
    db_lib = get_library_product_by_link(db, original_link, user_id)
    if not db_lib:
        db_lib = models.LibraryProduct(
            user_id=user_id,
            name=name,
            category=category,
            original_link=original_link,
            current_price=None,
            current_seller=None,
            current_installment=None,
            status="BEKLEMEDE"
        )
        db.add(db_lib)
        db.commit()
        db.refresh(db_lib)
    return db_lib

def delete_library_product(db: Session, library_product_id: int, user_id: int) -> bool:
    db_lib = db.query(models.LibraryProduct).filter(
        models.LibraryProduct.id == library_product_id,
        models.LibraryProduct.user_id == user_id
    ).first()
    if db_lib:
        db.delete(db_lib)
        db.commit()
        return True
    return False


def get_library_categories(db: Session, user_id: int) -> List[dict]:
    from sqlalchemy import func
    counts = db.query(
        models.LibraryProduct.category,
        func.count(models.LibraryProduct.id)
    ).filter(
        models.LibraryProduct.user_id == user_id,
        models.LibraryProduct.category != None
    ).group_by(models.LibraryProduct.category).all()
    
    # Kategori ismine göre alfabetik sırala
    sorted_counts = sorted([{"name": c[0], "count": c[1]} for c in counts if c[0]], key=lambda x: x["name"])
    return sorted_counts

# --- History and Alternatives CRUD ---
def add_price_history(db: Session, library_product_id: int, price: float, seller: Optional[str] = None) -> models.PriceHistory:
    db_history = models.PriceHistory(library_product_id=library_product_id, price=price, seller=seller)
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history

def get_history_by_product(db: Session, product_id: int) -> List[models.PriceHistory]:
    db_product = get_product_by_id(db, product_id)
    if not db_product:
        return []
    return db.query(models.PriceHistory).filter(models.PriceHistory.library_product_id == db_product.library_product_id).order_by(models.PriceHistory.recorded_at.asc()).all()

def sync_alternatives(db: Session, library_product_id: int, alternatives_list: List[schemas.AlternativeBase]) -> None:
    # Eski alternatifleri temizle
    db.query(models.Alternative).filter(models.Alternative.library_product_id == library_product_id).delete()
    # Yenileri ekle
    for alt in alternatives_list:
        db_alt = models.Alternative(**alt.model_dump(), library_product_id=library_product_id)
        db.add(db_alt)
    db.commit()

def get_alternatives_by_product(db: Session, product_id: int) -> List[models.Alternative]:
    db_product = get_product_by_id(db, product_id)
    if not db_product:
        return []
    return db.query(models.Alternative).filter(models.Alternative.library_product_id == db_product.library_product_id).order_by(models.Alternative.price.asc()).all()

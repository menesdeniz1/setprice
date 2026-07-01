import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import List, Optional

from . import models, schemas
from .set_templates import get_template
from . import benchmark_utils
from .notifiers import notify_user

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

def update_telegram_chat_id(db: Session, db_user: models.User, chat_id: Optional[str]) -> models.User:
    db_user.telegram_chat_id = chat_id
    db.commit()
    db.refresh(db_user)
    return db_user


# --- Scraper Health (Faz 5 — hafif gözlemlenebilirlik) ---
def record_domain_health(db: Session, domain: str, success: bool) -> None:
    entry = db.query(models.DomainHealth).filter(models.DomainHealth.domain == domain).first()
    if not entry:
        entry = models.DomainHealth(domain=domain, success_count=0, failure_count=0)
        db.add(entry)
    if success:
        entry.success_count += 1
        entry.last_status = "OK"
    else:
        entry.failure_count += 1
        entry.last_status = "FAILED"
    entry.last_checked_at = datetime.utcnow()
    db.commit()

def get_domain_health(db: Session) -> List[models.DomainHealth]:
    return db.query(models.DomainHealth).order_by(models.DomainHealth.domain).all()


# --- Set CRUD ---
def get_sets_by_user(db: Session, user_id: int) -> List[models.ProductSet]:
    return db.query(models.ProductSet).filter(models.ProductSet.user_id == user_id).all()

def get_set_by_id(db: Session, set_id: int) -> Optional[models.ProductSet]:
    return db.query(models.ProductSet).filter(models.ProductSet.id == set_id).first()

def create_set(db: Session, set_in: schemas.ProductSetCreate, user_id: int) -> models.ProductSet:
    template = get_template(set_in.template_key)
    data = set_in.model_dump(exclude={"template_key"})
    db_set = models.ProductSet(**data, user_id=user_id, template_name=template["name"] if template else None)
    db.add(db_set)
    db.commit()
    db.refresh(db_set)

    if template and template["categories"]:
        seed_set_categories(db, db_set.id, template["categories"])
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


# --- Set Category CRUD ---
def get_set_categories(db: Session, set_id: int) -> List[models.SetCategory]:
    return db.query(models.SetCategory).filter(
        models.SetCategory.set_id == set_id
    ).order_by(models.SetCategory.sort_order, models.SetCategory.id).all()

def seed_set_categories(db: Session, set_id: int, category_names: List[str]) -> None:
    for i, name in enumerate(category_names):
        db.add(models.SetCategory(set_id=set_id, name=name, sort_order=i))
    db.commit()

def add_set_category(db: Session, set_id: int, name: str) -> models.SetCategory:
    existing = db.query(models.SetCategory).filter(
        models.SetCategory.set_id == set_id, models.SetCategory.name == name
    ).first()
    if existing:
        return existing
    max_order = db.query(func.max(models.SetCategory.sort_order)).filter(
        models.SetCategory.set_id == set_id
    ).scalar() or 0
    cat = models.SetCategory(set_id=set_id, name=name, sort_order=max_order + 1)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

def rename_set_category(db: Session, set_id: int, category_id: int, new_name: str) -> Optional[models.SetCategory]:
    cat = db.query(models.SetCategory).filter(
        models.SetCategory.id == category_id, models.SetCategory.set_id == set_id
    ).first()
    if not cat:
        return None
    cat.name = new_name
    db.commit()
    db.refresh(cat)
    return cat

def delete_set_category(db: Session, set_id: int, category_id: int) -> bool:
    cat = db.query(models.SetCategory).filter(
        models.SetCategory.id == category_id, models.SetCategory.set_id == set_id
    ).first()
    if not cat:
        return False
    db.delete(cat)
    db.commit()
    return True


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
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        try:
            from decision_engine import DecisionEngine
            ticker = DecisionEngine().generate_ticker(name, category)
        except Exception:
            import random
            ticker = f"UNK-{random.randint(100, 999)}"
            
        db_lib = models.LibraryProduct(
            user_id=user_id,
            name=name,
            category=category,
            original_link=original_link,
            current_price=None,
            current_seller=None,
            current_installment=None,
            status="BEKLEMEDE",
            ticker=ticker
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

def _compute_benchmark_price(db_lib: models.LibraryProduct) -> Optional[float]:
    """Aynı ürün, farklı satıcı eşleşmelerinin ortalaması (elma-elma kıyas),
    yoksa tüm muadillere düşer."""
    same_product_prices = [a.price for a in db_lib.alternatives if a.price and (a.match_type or "similar") == "same_product"]
    alts = same_product_prices or [a.price for a in db_lib.alternatives if a.price]
    return sum(alts) / len(alts) if alts else None


def update_decision_signals(db: Session, library_product_ids: List[int]) -> None:
    """Her taramada çalışır: performans skoru (PassMark eşleştirme) ve fiyat
    bazlı erken uyarılar (hedef fiyat, bull-trap, dip bölge). Nihai
    BUY/WAIT/AVOID kararı artık burada üretilmiyor — bkz. update_ai_decisions()."""
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    try:
        from decision_engine import DecisionEngine
        engine = DecisionEngine()
    except Exception:
        return

    for lp_id in library_product_ids:
        db_lib = db.query(models.LibraryProduct).filter(models.LibraryProduct.id == lp_id).first()
        if not db_lib:
            continue

        history = [h.price for h in db_lib.history]
        db_lib.benchmark_price = _compute_benchmark_price(db_lib)

        # Performans skoru (CPU/GPU gibi kategoriler için, benchmark_utils'teki
        # küratörlü başlangıç veri setine göre)
        match = benchmark_utils.find_best_match(db, db_lib.name, db_lib.category)
        if match:
            match_name, raw_score = match
            db_lib.benchmark_match_name = match_name
            db_lib.performance_score = benchmark_utils.normalize_score(db, db_lib.category, raw_score)
        else:
            db_lib.benchmark_match_name = None
            db_lib.performance_score = None

        # ── Alert Üretimi ──

        # 1) Threshold Alert
        if (db_lib.price_alert_threshold and db_lib.current_price
                and db_lib.current_price <= db_lib.price_alert_threshold):
            _create_alert_if_not_exists(
                db, db_lib.user_id, lp_id,
                alert_type="THRESHOLD",
                title=f"Fiyat Alarmı: {db_lib.name}",
                message=f"Fiyat hedef seviyenin ({db_lib.price_alert_threshold:.0f}₺) altına düştü: {db_lib.current_price:.0f}₺"
            )

        # 2) Bull-trap Alert
        if engine.detect_bull_trap(db_lib.current_price or 0, history):
            _create_alert_if_not_exists(
                db, db_lib.user_id, lp_id,
                alert_type="BULL_TRAP",
                title=f"Sahte İndirim: {db_lib.name}",
                message=f"Bu üründe sahte indirim (bull-trap) tespit edildi. Fiyat şişirilip düşürülmüş."
            )

        # 3) Trend Dip Alert
        bottom = engine.detect_bottom_zone(db_lib.current_price or 0, history)
        if bottom["is_near_bottom"] and len(history) >= 5:
            _create_alert_if_not_exists(
                db, db_lib.user_id, lp_id,
                alert_type="TREND_DIP",
                title=f"Dip Bölge: {db_lib.name}",
                message=f"Bu ürün tarihsel dip bölgede (alt %{bottom['percentile']:.0f}). Alım fırsatı olabilir."
            )

    db.commit()


def update_ai_decisions(db: Session, library_product_ids: List[int]) -> None:
    """Günde bir kez (Celery Beat) çalışır: her ürün için AI karar motorunu
    çağırır. Bir ürün için tüm sağlayıcılar başarısız olursa o ürünün mevcut
    decision_signal/decision_reasoning'i DB'de olduğu gibi bırakılır — boş
    veya şablon bir yorumla ezilmez."""
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    try:
        from ai_decision_engine import generate_ai_decision, has_any_provider_configured
    except Exception:
        return

    if not has_any_provider_configured():
        return

    for lp_id in library_product_ids:
        db_lib = db.query(models.LibraryProduct).filter(models.LibraryProduct.id == lp_id).first()
        if not db_lib:
            continue

        history = [h.price for h in db_lib.history]
        benchmark = _compute_benchmark_price(db_lib)

        result = generate_ai_decision({
            "name": db_lib.name,
            "category": db_lib.category,
            "current_price": db_lib.current_price or 0.0,
            "history": history,
            "benchmark_price": benchmark,
            "rating": db_lib.rating,
            "review_count": db_lib.review_count,
        })

        if not result:
            continue

        old_signal = db_lib.decision_signal
        db_lib.decision_signal = result["signal"]
        db_lib.value_score = result["value_score"]
        db_lib.decision_reasoning = result["reasoning"]
        db_lib.ai_decision_updated_at = datetime.utcnow()
        db.commit()

        if old_signal and old_signal != result["signal"]:
            emoji = {"BUY": "🟢", "WAIT": "🟡", "AVOID": "🔴"}.get(result["signal"], "")
            _create_alert_if_not_exists(
                db, db_lib.user_id, lp_id,
                alert_type="SIGNAL_CHANGE",
                title=f"Sinyal Değişimi: {db_lib.name}",
                message=f"{old_signal} → {result['signal']} {emoji} | {result['reasoning']}"
            )


def _create_alert_if_not_exists(db: Session, user_id: int, lp_id: int, alert_type: str, title: str, message: str):
    """Son 24 saat içinde aynı tipte alert varsa tekrar oluşturma."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=24)
    existing = db.query(models.Alert).filter(
        models.Alert.user_id == user_id,
        models.Alert.library_product_id == lp_id,
        models.Alert.alert_type == alert_type,
        models.Alert.created_at >= cutoff
    ).first()
    if existing:
        return
    alert = models.Alert(
        user_id=user_id,
        library_product_id=lp_id,
        alert_type=alert_type,
        title=title,
        message=message
    )
    db.add(alert)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        notify_user(user, title, message)


# --- Alert CRUD ---
def get_alerts(db: Session, user_id: int, unread_only: bool = False) -> List[models.Alert]:
    query = db.query(models.Alert).filter(models.Alert.user_id == user_id)
    if unread_only:
        query = query.filter(models.Alert.is_read == False)
    return query.order_by(models.Alert.created_at.desc()).limit(50).all()

def get_unread_alert_count(db: Session, user_id: int) -> int:
    return db.query(models.Alert).filter(
        models.Alert.user_id == user_id,
        models.Alert.is_read == False
    ).count()

def mark_alert_read(db: Session, alert_id: int, user_id: int) -> bool:
    alert = db.query(models.Alert).filter(
        models.Alert.id == alert_id,
        models.Alert.user_id == user_id
    ).first()
    if alert:
        alert.is_read = True
        db.commit()
        return True
    return False

def mark_all_alerts_read(db: Session, user_id: int) -> int:
    count = db.query(models.Alert).filter(
        models.Alert.user_id == user_id,
        models.Alert.is_read == False
    ).update({"is_read": True})
    db.commit()
    return count

def set_price_alert_threshold(db: Session, library_product_id: int, user_id: int, threshold: Optional[float]) -> bool:
    db_lib = db.query(models.LibraryProduct).filter(
        models.LibraryProduct.id == library_product_id,
        models.LibraryProduct.user_id == user_id
    ).first()
    if db_lib:
        db_lib.price_alert_threshold = threshold
        db.commit()
        return True
    return False


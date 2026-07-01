# -*- coding: utf-8 -*-
import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import urllib.parse
from contextlib import asynccontextmanager
import asyncio

logger = logging.getLogger("setprice.web")

from src.config_loader import ConfigLoader
from src.scraper import Scraper
from src.akakce import AkakceSearcher
from src.logger import setup_logger

from .database import engine, Base, get_db, run_lightweight_migrations, SessionLocal
from . import models, schemas, crud, tasks
from .category_utils import infer_category
from .set_templates import SET_TEMPLATES
from .benchmark_utils import seed_benchmark_entries

# Tabloları oluştur, sonra var olan tablolara eklenen yeni kolonları uygula
Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

with SessionLocal() as _seed_db:
    seed_benchmark_entries(_seed_db)

async def periodic_library_scan():
    while True:
        # 10 dakikada bir çalıştır (600 saniye)
        await asyncio.sleep(600)
        try:
            print("[Periodic] Otomatik kütüphane taraması başlatılıyor (10 dk)")
            await asyncio.to_thread(tasks.run_library_scan)
        except Exception as e:
            print(f"[Periodic] Tarama hatası: {e}")

USE_CELERY = os.environ.get("USE_CELERY", "false").lower() == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — USE_CELERY=true ise periyodik tarama Celery Beat'e devredilir
    # (bkz. tasks.py), burada tekrar başlatılmaz.
    task = None
    if not USE_CELERY:
        task = asyncio.create_task(periodic_library_scan())
    yield
    # Shutdown
    if task:
        task.cancel()

app = FastAPI(title="SetPrice API", version="1.0.0", lifespan=lifespan)

# CORS izinleri — env'den okunur, virgülle ayrılmış origin listesi.
# Belirtilmezse sadece yerel geliştirme sunucusuna izin verilir.
_cors_origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Ayarları — JWT_SECRET env'de yoksa process başına rastgele bir secret
# üretilir. Bu, repo içine sabit/tahmin edilebilir bir secret gömmekten daha
# güvenlidir; tek dezavantajı sunucu her yeniden başladığında mevcut
# token'ların geçersiz olmasıdır (dev/tek-instance kullanım için kabul edilebilir).
SECRET_KEY = os.environ.get("JWT_SECRET")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET ortam değişkeni ayarlanmamış! Process başına rastgele bir "
        "secret üretildi — sunucu yeniden başladığında tüm oturumlar geçersiz "
        "olacak. Kalıcı oturumlar için JWT_SECRET'i ortam değişkeni olarak ayarlayın."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 gün

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user


# --- AUTH ENDPOINTS ---
@app.post("/api/auth/register", response_model=schemas.UserResponse)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(status_code=400, detail="E-posta adresi zaten kullanımda")
    return crud.create_user(db, user=user_in)

@app.post("/api/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not crud.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı e-posta veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.put("/api/auth/telegram", response_model=schemas.UserResponse)
def update_telegram_settings(
    settings_in: schemas.TelegramSettingsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.update_telegram_chat_id(db, current_user, settings_in.telegram_chat_id)

@app.post("/api/auth/telegram/test")
def send_telegram_test(current_user: models.User = Depends(get_current_user)):
    from .notifiers import TelegramNotifier
    notifier = TelegramNotifier()
    if not notifier.is_configured():
        raise HTTPException(status_code=400, detail="Sunucuda TELEGRAM_BOT_TOKEN ayarlanmamış")
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Önce Telegram Chat ID'nizi kaydedin")
    ok = notifier.send(current_user, "SetPrice Test", "Telegram bildirimleri başarıyla bağlandı! 🎉")
    if not ok:
        raise HTTPException(status_code=502, detail="Telegram'a gönderilemedi — bot token veya chat ID'yi kontrol edin")
    return {"status": "success"}


# --- SETS ENDPOINTS ---
@app.get("/api/sets", response_model=List[schemas.ProductSetDetailed])
def read_sets(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.get_sets_by_user(db, user_id=current_user.id)

@app.post("/api/sets", response_model=schemas.ProductSetResponse)
def create_set(set_in: schemas.ProductSetCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.create_set(db, set_in=set_in, user_id=current_user.id)

@app.get("/api/sets/{set_id}", response_model=schemas.ProductSetDetailed)
def read_set(set_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    return db_set

@app.put("/api/sets/{set_id}", response_model=schemas.ProductSetResponse)
def update_set(set_id: int, set_update: schemas.ProductSetUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    return crud.update_set(db, db_set=db_set, set_update=set_update)

@app.delete("/api/sets/{set_id}")
def delete_set(set_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    crud.delete_set(db, set_id=set_id)
    return {"status": "success", "message": "Set başarıyla silindi"}


# --- SET TEMPLATES ---
@app.get("/api/set-templates", response_model=List[schemas.SetTemplateInfo])
def get_set_templates_route():
    return SET_TEMPLATES


# --- SET CATEGORIES ENDPOINTS ---
@app.get("/api/sets/{set_id}/categories", response_model=List[schemas.SetCategoryResponse])
def get_set_categories_route(set_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    return crud.get_set_categories(db, set_id=set_id)

@app.post("/api/sets/{set_id}/categories", response_model=schemas.SetCategoryResponse)
def add_set_category_route(set_id: int, cat_in: schemas.SetCategoryCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    return crud.add_set_category(db, set_id=set_id, name=cat_in.name.strip())

@app.put("/api/sets/{set_id}/categories/{category_id}", response_model=schemas.SetCategoryResponse)
def rename_set_category_route(set_id: int, category_id: int, cat_in: schemas.SetCategoryUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    db_cat = crud.rename_set_category(db, set_id=set_id, category_id=category_id, new_name=cat_in.name.strip())
    if not db_cat:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    return db_cat

@app.delete("/api/sets/{set_id}/categories/{category_id}")
def delete_set_category_route(set_id: int, category_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    ok = crud.delete_set_category(db, set_id=set_id, category_id=category_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    return {"status": "success"}


# --- LIBRARY PRODUCTS ENDPOINT ---
@app.get("/api/library/products", response_model=List[schemas.LibraryProductResponse])
def get_library_products(
    category: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if category:
        return crud.get_library_products_by_category(db, category=category, user_id=current_user.id)
    return crud.get_library_products(db, user_id=current_user.id)


@app.get("/api/library/categories", response_model=List[schemas.CategoryCount])
def get_library_categories_route(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.get_library_categories(db, user_id=current_user.id)

@app.delete("/api/library/products/{library_product_id}")
def delete_library_product_route(
    library_product_id: int, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    db_lib = crud.get_library_product_by_id(db, library_product_id)
    if not db_lib or db_lib.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Kütüphane ürünü bulunamadı")
    crud.delete_library_product(db, library_product_id, current_user.id)
    return {"status": "success", "message": "Ürün kütüphaneden silindi"}


@app.post("/api/library/products", response_model=schemas.LibraryProductResponse)
def add_product_to_library_directly(
    product_in: schemas.ProductCreate, 
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if not product_in.original_link:
        raise HTTPException(status_code=400, detail="original_link sağlanmalıdır")
        
    url = product_in.original_link
    
    # Zaten kütüphanede kayıtlı mı?
    db_lib = crud.get_library_product_by_link(db, url, current_user.id)
    if db_lib:
        return db_lib
        
    # Otomatik Ürün Bilgisi Çıkarma
    config_loader = ConfigLoader()
    config = config_loader.load()
    logger = setup_logger(config)
    
    site_configs = config_loader.load_site_configs()
    scraper = Scraper(config, site_configs, logger)
    domain = scraper._get_domain(url)
    site_cfg = site_configs.get(domain, {})
    
    product_name = "Analiz Ediliyor..."
    category = "Diğer"
    initial_price = None
    
    try:
        html = scraper._fetch_requests(url)
        if html == "403_FORBIDDEN" or not html:
            html = scraper._fetch_cloudscraper(url)
            
        if html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            og_title = soup.find("meta", property="og:title")
            h1_title = soup.find("h1")
            title_tag = soup.find("title")
            
            if og_title and og_title.get("content"):
                product_name = og_title.get("content").strip()
            elif h1_title and h1_title.text:
                product_name = h1_title.text.strip()
            elif title_tag and title_tag.text:
                raw_title = title_tag.text.strip()
                # Clean up known store suffixes
                clean_title = raw_title.split("|")[0].split("-")[0].replace("Amazon.com.tr", "").replace("Trendyol", "").strip()
                if clean_title:
                    product_name = clean_title
                else:
                    product_name = raw_title
            initial_price = scraper.extract_price(html, site_cfg)
    except Exception as e:
        logger.warning(f"Yeni ürün eklenirken link çözümlenemedi: {e}")
    finally:
        current_seller_val = scraper._infer_seller(url)
        scraper.close()
        
    category = product_in.category.strip() if product_in.category else infer_category(product_name)

    db_lib = crud.get_or_create_library_product(
        db,
        name=product_name[:80],
        category=category,
        original_link=url,
        user_id=current_user.id
    )

    if initial_price:
        db_lib.current_price = initial_price
        db_lib.current_seller = current_seller_val
        db_lib.status = "OK"
        db.commit()
        crud.add_price_history(db, db_lib.id, initial_price, db_lib.current_seller)
        
    background_tasks.add_task(tasks.run_library_scan, db_lib.id, current_user.id)
    return db_lib


# --- PRODUCTS ENDPOINTS ---
@app.post("/api/sets/{set_id}/products", response_model=schemas.ProductResponse)
def add_product_to_set(
    set_id: int, 
    product_in: schemas.ProductCreate, 
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")

    # Kütüphanedeki mevcut ürünü ekleme durumu
    if product_in.library_product_id is not None:
        db_lib = crud.get_library_product_by_id(db, product_in.library_product_id)
        if not db_lib or db_lib.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Kütüphane ürünü bulunamadı")
            
        # Sette mükerrer eklemeyi engelle
        existing = db.query(models.Product).filter(
            models.Product.set_id == set_id,
            models.Product.library_product_id == db_lib.id
        ).first()
        if existing:
            return existing
            
        db_product = crud.create_product(db, library_product_id=db_lib.id, set_id=set_id)
        background_tasks.add_task(tasks.run_set_scan, set_id)
        return db_product
        
    # Yeni linkten ekleme durumu
    if not product_in.original_link:
        raise HTTPException(status_code=400, detail="original_link veya library_product_id sağlanmalıdır")
        
    url = product_in.original_link
    
    # Zaten kütüphanede kayıtlı mı?
    db_lib = crud.get_library_product_by_link(db, url, current_user.id)
    if db_lib:
        existing = db.query(models.Product).filter(
            models.Product.set_id == set_id,
            models.Product.library_product_id == db_lib.id
        ).first()
        if existing:
            return existing
        db_product = crud.create_product(db, library_product_id=db_lib.id, set_id=set_id)
        background_tasks.add_task(tasks.run_set_scan, set_id)
        return db_product
        
    # Otomatik Ürün Bilgisi Çıkarma (Linkten Çözümleme)
    config_loader = ConfigLoader()
    config = config_loader.load()
    logger = setup_logger(config)
    
    site_configs = config_loader.load_site_configs()
    scraper = Scraper(config, site_configs, logger)
    domain = scraper._get_domain(url)
    site_cfg = site_configs.get(domain, {})
    
    product_name = "Analiz Ediliyor..."
    category = "Diğer"
    initial_price = None
    
    try:
        html = scraper._fetch_requests(url)
        if html == "403_FORBIDDEN" or not html:
            html = scraper._fetch_cloudscraper(url)
            
        if html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            og_title = soup.find("meta", property="og:title")
            h1_title = soup.find("h1")
            title_tag = soup.find("title")
            
            if og_title and og_title.get("content"):
                product_name = og_title.get("content").strip()
            elif h1_title and h1_title.text:
                product_name = h1_title.text.strip()
            elif title_tag and title_tag.text:
                raw_title = title_tag.text.strip()
                clean_title = raw_title.split("|")[0].split("-")[0].replace("Amazon.com.tr", "").replace("Trendyol", "").strip()
                if clean_title:
                    product_name = clean_title
                else:
                    product_name = raw_title
            initial_price = scraper.extract_price(html, site_cfg)
    except Exception as e:
        logger.warning(f"Yeni ürün eklenirken link çözümlenemedi: {e}")
    finally:
        scraper.close()
        
    # Kategori: kullanıcı verdiyse onu kullan; yoksa önce bu setin kendi
    # kategori listesiyle, bulamazsa genel elektronik sözlüğüyle tahmin et
    if product_in.category:
        category = product_in.category.strip()
    else:
        set_category_names = [c.name for c in crud.get_set_categories(db, set_id)]
        category = infer_category(product_name, known_categories=set_category_names)

    # Kütüphaneye kaydet
    db_lib = crud.get_or_create_library_product(
        db,
        name=product_name[:80],
        category=category,
        original_link=url,
        user_id=current_user.id
    )
    
    if initial_price:
        db_lib.current_price = initial_price
        db_lib.current_seller = scraper._infer_seller(url)
        db_lib.status = "OK"
        db.commit()
        crud.add_price_history(db, db_lib.id, initial_price, db_lib.current_seller)
        
    # Sete ekle
    db_product = crud.create_product(db, library_product_id=db_lib.id, set_id=set_id)
    background_tasks.add_task(tasks.run_set_scan, set_id)
    
    return db_product

@app.put("/api/products/{product_id}", response_model=schemas.ProductResponse)
def update_product(product_id: int, product_update: schemas.ProductUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_product = crud.get_product_by_id(db, product_id=product_id)
    if not db_product or db_product.product_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return crud.update_product(db, db_product=db_product, product_update=product_update)

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_product = crud.get_product_by_id(db, product_id=product_id)
    if not db_product or db_product.product_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    crud.delete_product(db, product_id=product_id)
    return {"status": "success", "message": "Ürün setten kaldırıldı"}


# --- SCAN ENDPOINT ---
@app.post("/api/sets/{set_id}/scan")
def scan_set(
    set_id: int, 
    background_tasks: BackgroundTasks, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    db_set = crud.get_set_by_id(db, set_id=set_id)
    if not db_set or db_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
        
    # Redis/Celery aktifse Celery task kullan, yoksa yerel BackgroundTasks
    use_celery = os.environ.get("USE_CELERY", "false").lower() == "true"
    if use_celery:
        tasks.scan_product_set_celery_task.delay(set_id)
        return {"status": "queued", "message": "Tarama görevi kuyruğa eklendi (Celery)"}
    else:
        background_tasks.add_task(tasks.run_set_scan, set_id)
        return {"status": "processing", "message": "Tarama işlemi arka planda başlatıldı"}

@app.post("/api/library/products/scan-all")
def scan_all_library_products(
    background_tasks: BackgroundTasks, 
    current_user: models.User = Depends(get_current_user)
):
    background_tasks.add_task(tasks.run_library_scan, None, current_user.id)
    return {"status": "processing", "message": "Kütüphane taraması başlatıldı"}

@app.post("/api/library/products/{library_product_id}/scan")
def scan_single_library_product(
    library_product_id: int, 
    background_tasks: BackgroundTasks, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    db_lib = crud.get_library_product_by_id(db, library_product_id)
    if not db_lib or db_lib.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Kütüphane ürünü bulunamadı")
    background_tasks.add_task(tasks.run_library_scan, library_product_id, current_user.id)
    return {"status": "processing", "message": "Ürün taraması başlatıldı"}


# --- HISTORY & COMPARISON ENDPOINTS ---
@app.get("/api/products/{product_id}/history", response_model=List[schemas.PriceHistoryResponse])
def get_product_history(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_product = crud.get_product_by_id(db, product_id=product_id)
    if not db_product or db_product.product_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return crud.get_history_by_product(db, product_id=product_id)

@app.get("/api/products/{product_id}/compare", response_model=List[schemas.AlternativeResponse])
def get_product_alternatives(product_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_product = crud.get_product_by_id(db, product_id=product_id)
    if not db_product or db_product.product_set.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return crud.get_alternatives_by_product(db, product_id=product_id)


# --- ALERT ENDPOINTS ---
@app.get("/api/alerts", response_model=List[schemas.AlertResponse])
def get_alerts(
    unread_only: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.get_alerts(db, user_id=current_user.id, unread_only=unread_only)

@app.get("/api/alerts/count")
def get_unread_alert_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    count = crud.get_unread_alert_count(db, user_id=current_user.id)
    return {"count": count}

@app.put("/api/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = crud.mark_alert_read(db, alert_id=alert_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert bulunamadı")
    return {"status": "success"}

@app.put("/api/alerts/read-all")
def mark_all_alerts_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    count = crud.mark_all_alerts_read(db, user_id=current_user.id)
    return {"status": "success", "count": count}

@app.put("/api/library/products/{library_product_id}/threshold")
def set_price_threshold(
    library_product_id: int,
    threshold_in: schemas.AlertThresholdUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = crud.set_price_alert_threshold(
        db, library_product_id=library_product_id,
        user_id=current_user.id,
        threshold=threshold_in.price_alert_threshold
    )
    if not success:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return {"status": "success"}


# --- SCRAPER HEALTH (Faz 5 — hafif gözlemlenebilirlik) ---
@app.get("/api/scraper-health", response_model=List[schemas.DomainHealthResponse])
def get_scraper_health(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.get_domain_health(db)


from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request
from fastapi.staticfiles import StaticFiles

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    # API yollarında standart 404 JSON dön, aksi halde SPA için index.html dön
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    # Ayrıca, statik dosyalara (js, css, png) istek gelmişse ve bulunamadıysa 404 dön
    if request.url.path.startswith("/assets/") or "." in request.url.path.split("/")[-1]:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return FileResponse("src/web_backend/static_build/index.html")

app.mount("/", StaticFiles(directory="src/web_backend/static_build", html=True), name="static")

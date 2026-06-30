# -*- coding: utf-8 -*-
import os
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

from src.config_loader import ConfigLoader
from src.scraper import Scraper
from src.akakce import AkakceSearcher
from src.logger import setup_logger

from .database import engine, Base, get_db
from . import models, schemas, crud, tasks

# Tabloları oluştur
Base.metadata.create_all(bind=engine)

async def periodic_library_scan():
    while True:
        # 10 dakikada bir çalıştır (600 saniye)
        await asyncio.sleep(600)
        try:
            print("[Periodic] Otomatik kütüphane taraması başlatılıyor (10 dk)")
            await asyncio.to_thread(tasks.run_library_scan)
        except Exception as e:
            print(f"[Periodic] Tarama hatası: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(periodic_library_scan())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="SetPrice API", version="1.0.0", lifespan=lifespan)

# CORS izinleri
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Ayarları
SECRET_KEY = os.environ.get("JWT_SECRET", "9f82d2a939f72b7a9e3a6c8e9d2b1f8c3e4a5d6e7f8a9b0c1d2e3f4a5b6c7d8e")
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
    
    product_name = "Yeni Ürün"
    category = "Diğer"
    initial_price = None
    
    try:
        html = scraper._fetch_requests(url)
        if html == "403_FORBIDDEN" or not html:
            html = scraper._fetch_cloudscraper(url)
            
        if html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            if title_tag and title_tag.text:
                product_name = title_tag.text.strip().split("|")[0].split("-")[0].strip()
                
            initial_price = scraper.extract_price(html, site_cfg)
    except Exception as e:
        logger.warning(f"Yeni ürün eklenirken link çözümlenemedi: {e}")
    finally:
        current_seller_val = scraper._infer_seller(url)
        scraper.close()
        
    category_mapping = {
        "kulaklık": "Kulaklık", "headset": "Kulaklık", "earphone": "Kulaklık",
        "mouse": "Mouse", "fare": "Mouse",
        "klavye": "Klavye", "keyboard": "Klavye",
        "anakart": "Anakart", "motherboard": "Anakart", "mainboard": "Anakart",
        "işlemci": "İşlemci", "islemci": "İşlemci", "cpu": "İşlemci",
        "ekran kartı": "Ekran Kartı", "ekran karti": "Ekran Kartı", "vga": "Ekran Kartı", "gpu": "Ekran Kartı", "graphics card": "Ekran Kartı",
        "ram": "RAM", "bellek": "RAM", "memory": "RAM",
        "ssd": "Depolama", "hdd": "Depolama", "harddisk": "Depolama", "depolama": "Depolama",
        "kasa": "Kasa", "case": "Kasa",
        "güç kaynağı": "Güç Kaynağı", "guc kaynagi": "Güç Kaynağı", "psu": "Güç Kaynağı", "power supply": "Güç Kaynağı",
        "soğutma": "Soğutma", "sogutma": "Soğutma", "soğutucu": "Soğutma", "sogutucu": "Soğutma", "cooler": "Soğutma"
    }
    
    lower_name = product_name.lower()
    for keyword, normalized_cat in category_mapping.items():
        if keyword in lower_name:
            category = normalized_cat
            break
            
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
    
    product_name = "Yeni Ürün"
    category = "Diğer"
    initial_price = None
    
    try:
        html = scraper._fetch_requests(url)
        if html == "403_FORBIDDEN" or not html:
            html = scraper._fetch_cloudscraper(url)
            
        if html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            if title_tag and title_tag.text:
                product_name = title_tag.text.strip().split("|")[0].split("-")[0].strip()
                
            initial_price = scraper.extract_price(html, site_cfg)
    except Exception as e:
        logger.warning(f"Yeni ürün eklenirken link çözümlenemedi: {e}")
    finally:
        scraper.close()
        
    # Kategori tahmini ve normalizasyon
    category_mapping = {
        "kulaklık": "Kulaklık", "headset": "Kulaklık", "earphone": "Kulaklık",
        "mouse": "Mouse", "fare": "Mouse",
        "klavye": "Klavye", "keyboard": "Klavye",
        "anakart": "Anakart", "motherboard": "Anakart", "mainboard": "Anakart",
        "işlemci": "İşlemci", "islemci": "İşlemci", "cpu": "İşlemci",
        "ekran kartı": "Ekran Kartı", "ekran karti": "Ekran Kartı", "vga": "Ekran Kartı", "gpu": "Ekran Kartı", "graphics card": "Ekran Kartı",
        "ram": "RAM", "bellek": "RAM", "memory": "RAM",
        "ssd": "Depolama", "hdd": "Depolama", "harddisk": "Depolama", "depolama": "Depolama",
        "kasa": "Kasa", "case": "Kasa",
        "güç kaynağı": "Güç Kaynağı", "guc kaynagi": "Güç Kaynağı", "psu": "Güç Kaynağı", "power supply": "Güç Kaynağı",
        "soğutma": "Soğutma", "sogutma": "Soğutma", "soğutucu": "Soğutma", "sogutucu": "Soğutma", "cooler": "Soğutma"
    }
    
    lower_name = product_name.lower()
    for keyword, normalized_cat in category_mapping.items():
        if keyword in lower_name:
            category = normalized_cat
            break
            
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

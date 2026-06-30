# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from src.web_backend.database import Base, get_db
from src.web_backend.main import app
from src.web_backend import models, crud, schemas

import os

# Test için geçici dosya tabanlı veritabanı kullan (in-memory connection paylaşım sorununu çözmek için)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_temp.db"
if os.path.exists("./test_temp.db"):
    try: os.remove("./test_temp.db")
    except: pass

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Veritabanını baştan oluştur
Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="module", autouse=True)
def cleanup(request):
    def remove_test_db():
        if os.path.exists("./test_temp.db"):
            try: os.remove("./test_temp.db")
            except: pass
    request.addfinalizer(remove_test_db)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# get_db bağımlılığını override et
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_static_index():
    """Mount edilen statik anasayfanın başarıyla yüklendiğini test eder."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_user_registration_and_login():
    """Kullanıcı kaydı ve JWT login işlemlerini test eder."""
    # Kayıt ol
    reg_response = client.post(
        "/api/auth/register",
        json={"email": "testuser@setprice.com", "password": "password123"}
    )
    assert reg_response.status_code == 200
    data = reg_response.json()
    assert data["email"] == "testuser@setprice.com"
    assert "id" in data
    
    # Giriş yap (OAuth2 form-data yapısında olmalı)
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser@setprice.com", "password": "password123"}
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

def test_product_set_crud():
    """Set oluşturma, listeleme ve silme işlemlerini test eder."""
    # Önce giriş yap ve token al
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser@setprice.com", "password": "password123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Set oluştur
    create_response = client.post(
        "/api/sets",
        json={"name": "Test Seti", "target_budget": 5000.0},
        headers=headers
    )
    assert create_response.status_code == 200
    set_data = create_response.json()
    assert set_data["name"] == "Test Seti"
    assert set_data["target_budget"] == 5000.0
    set_id = set_data["id"]
    
    # Setleri listele
    list_response = client.get("/api/sets", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1
    
    # Set detayını oku
    detail_response = client.get(f"/api/sets/{set_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "Test Seti"
    
    # Seti sil
    del_response = client.delete(f"/api/sets/{set_id}", headers=headers)
    assert del_response.status_code == 200
    assert del_response.json()["status"] == "success"

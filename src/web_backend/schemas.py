from pydantic import BaseModel, EmailStr, model_validator
from typing import List, Optional
from datetime import datetime
# --- Category Schemas ---
class CategoryCount(BaseModel):
    name: str
    count: int

# --- Alternative Schemas ---
class AlternativeBase(BaseModel):
    title: str
    price: float
    seller: Optional[str] = None
    link: str

class AlternativeResponse(AlternativeBase):
    id: int
    library_product_id: int
    updated_at: datetime

    class Config:
        from_attributes = True


# --- PriceHistory Schemas ---
class PriceHistoryResponse(BaseModel):
    id: int
    library_product_id: int
    price: float
    seller: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True


# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str
    category: str
    original_link: str
    locked_price: Optional[float] = None
    is_active: Optional[bool] = True
    is_locked: Optional[bool] = False

class ProductCreate(BaseModel):
    original_link: Optional[str] = None
    library_product_id: Optional[int] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    locked_price: Optional[float] = None
    is_active: Optional[bool] = None
    is_locked: Optional[bool] = None

class ProductResponse(ProductBase):
    id: int
    set_id: int
    library_product_id: int
    current_price: Optional[float] = None
    current_seller: Optional[str] = None
    current_installment: Optional[str] = None
    status: str
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def flatten_library_product(cls, data):
        if hasattr(data, "library_product") and data.library_product:
            lib = data.library_product
            # attributes fallback to database if they were overwritten on set level, otherwise library values
            name = getattr(data, "name", None) or getattr(lib, "name", "Bilinmeyen Ürün")
            category = getattr(data, "category", None) or getattr(lib, "category", "Diğer")
            original_link = getattr(data, "original_link", None) or getattr(lib, "original_link", "")
            
            return {
                "id": data.id,
                "set_id": data.set_id,
                "library_product_id": data.library_product_id,
                "locked_price": data.locked_price,
                "is_active": data.is_active,
                "is_locked": data.is_locked,
                "updated_at": data.updated_at,
                "name": name,
                "category": category,
                "original_link": original_link,
                "current_price": lib.current_price,
                "current_seller": lib.current_seller,
                "current_installment": lib.current_installment,
                "status": lib.status,
            }
        return data

    class Config:
        from_attributes = True


# --- LibraryProduct Schemas ---
class LibraryProductResponse(BaseModel):
    id: int
    name: str
    category: str
    original_link: str
    current_price: Optional[float] = None
    current_seller: Optional[str] = None
    current_installment: Optional[str] = None
    status: str
    updated_at: datetime

    class Config:
        from_attributes = True


# --- ProductSet Schemas ---
class ProductSetBase(BaseModel):
    name: str
    target_budget: Optional[float] = 0.0

class ProductSetCreate(ProductSetBase):
    pass

class ProductSetUpdate(BaseModel):
    name: Optional[str] = None
    target_budget: Optional[float] = None

class ProductSetResponse(ProductSetBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ProductSetDetailed(ProductSetResponse):
    products: List[ProductResponse] = []

    class Config:
        from_attributes = True


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr

from pydantic import BaseModel, EmailStr, model_validator, Field

# ... existing code up to UserCreate ...
class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

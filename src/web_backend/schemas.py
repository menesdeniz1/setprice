from pydantic import BaseModel, EmailStr, model_validator, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
# --- Category Schemas ---
class CategoryCount(BaseModel):
    name: str
    count: int

# --- Scraper Health Schema ---
class DomainHealthResponse(BaseModel):
    domain: str
    success_count: int
    failure_count: int
    last_status: Optional[str] = None
    last_checked_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Alternative Schemas ---
class AlternativeBase(BaseModel):
    title: str
    price: float
    seller: Optional[str] = None
    link: str
    match_type: Optional[str] = "similar"  # 'same_product' | 'similar'
    match_confidence: Optional[float] = None

class AlternativeResponse(AlternativeBase):
    id: int
    library_product_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- PriceHistory Schemas ---
class PriceHistoryResponse(BaseModel):
    id: int
    library_product_id: int
    price: float
    seller: Optional[str] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    category: Optional[str] = None  # verilirse otomatik tahmini geçersiz kılar

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
    ticker: Optional[str] = None
    value_score: Optional[float] = None
    satisfaction_score: Optional[float] = None
    performance_score: Optional[float] = None
    benchmark_match_name: Optional[str] = None
    decision_signal: Optional[str] = "WAIT"
    decision_reasoning: Optional[str] = None
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
                "ticker": lib.ticker,
                "value_score": lib.value_score,
                "satisfaction_score": lib.satisfaction_score,
                "performance_score": lib.performance_score,
                "benchmark_match_name": lib.benchmark_match_name,
                "decision_signal": lib.decision_signal,
                "decision_reasoning": lib.decision_reasoning,
            }
        return data

    model_config = ConfigDict(from_attributes=True)


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
    ticker: Optional[str] = None
    value_score: Optional[float] = None
    satisfaction_score: Optional[float] = None
    performance_score: Optional[float] = None
    benchmark_match_name: Optional[str] = None
    decision_signal: Optional[str] = "WAIT"
    decision_reasoning: Optional[str] = None
    benchmark_price: Optional[float] = None
    price_alert_threshold: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Set Category Schemas ---
class SetCategoryResponse(BaseModel):
    id: int
    set_id: int
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)

class SetCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)

class SetCategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


# --- Set Template Schemas ---
class SetTemplateInfo(BaseModel):
    key: str
    name: str
    categories: List[str]


# --- ProductSet Schemas ---
class ProductSetBase(BaseModel):
    name: str
    target_budget: Optional[float] = 0.0

class ProductSetCreate(ProductSetBase):
    template_key: Optional[str] = None

class ProductSetUpdate(BaseModel):
    name: Optional[str] = None
    target_budget: Optional[float] = None

class ProductSetResponse(ProductSetBase):
    id: int
    user_id: int
    template_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductSetDetailed(ProductSetResponse):
    products: List[ProductResponse] = []
    categories: List[SetCategoryResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    id: int
    telegram_chat_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TelegramSettingsUpdate(BaseModel):
    telegram_chat_id: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


# --- Alert Schemas ---
class AlertResponse(BaseModel):
    id: int
    user_id: int
    library_product_id: int
    alert_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AlertThresholdUpdate(BaseModel):
    price_alert_threshold: Optional[float] = None

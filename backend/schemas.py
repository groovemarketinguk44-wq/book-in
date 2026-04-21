from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    business_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Business ──────────────────────────────────────────────────────────────────

class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    logo_url: Optional[str]
    timezone: str
    subscription_status: str
    trial_ends_at: Optional[datetime]
    onboarding_complete: bool
    primary_color: Optional[str]
    email_confirmations: bool
    email_reminders: bool
    sms_reminders: bool


# ── Onboarding ────────────────────────────────────────────────────────────────

class OnboardingStep1(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None


# ── Category ─────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    image_url: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    image_url: Optional[str] = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_url: Optional[str]
    business_id: int


# ── Service ───────────────────────────────────────────────────────────────────

class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    duration_minutes: int
    image_url: Optional[str] = None
    category_id: Optional[int] = None


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    duration_minutes: Optional[int] = None
    image_url: Optional[str] = None
    category_id: Optional[int] = None
    active: Optional[bool] = None


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    price: Decimal
    duration_minutes: int
    image_url: Optional[str]
    category_id: Optional[int]
    business_id: int
    active: bool


# ── Booking ───────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    customer_name: str
    customer_email: EmailStr
    customer_phone: Optional[str] = None
    service_id: int
    start_time: datetime
    notes: Optional[str] = None


class BookingUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    customer_email: str
    customer_phone: Optional[str]
    service_id: int
    start_time: datetime
    end_time: datetime
    status: str
    business_id: int
    notes: Optional[str]
    created_at: datetime


class BookingWithService(BookingResponse):
    service_name: Optional[str] = None
    service_price: Optional[Decimal] = None
    service_duration: Optional[int] = None


# ── Slots ─────────────────────────────────────────────────────────────────────

class SlotResponse(BaseModel):
    time: str
    datetime: str


# ── Financials ────────────────────────────────────────────────────────────────

class FinancialsResponse(BaseModel):
    total_revenue: float
    booking_count: int
    avg_booking_value: float
    daily_revenue: float
    weekly_revenue: float
    monthly_revenue: float
    chart_labels: list[str]
    chart_data: list[float]


# ── Settings ─────────────────────────────────────────────────────────────────

class NotificationSettings(BaseModel):
    email_confirmations: bool
    email_reminders: bool
    sms_reminders: bool


# ── Email Account ─────────────────────────────────────────────────────────────

class EmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    email_address: str
    token_expiry: Optional[datetime]

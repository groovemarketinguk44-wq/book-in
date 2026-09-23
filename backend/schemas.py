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
    is_platform_admin: bool = False


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
    whatsapp_reminders: bool
    sms_confirmations: bool
    whatsapp_confirmations: bool
    reminder_2h: bool
    google_review_link: Optional[str]
    tracking_phone_number: Optional[str]
    plan: Optional[str]


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
    staff_id: Optional[int] = None
    start_time: datetime
    notes: Optional[str] = None
    source: Optional[str] = None


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
    staff_id: Optional[int]
    notes: Optional[str]
    created_at: datetime


class BookingWithService(BookingResponse):
    service_name: Optional[str] = None
    service_price: Optional[Decimal] = None
    service_duration: Optional[int] = None
    staff_name: Optional[str] = None


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
    whatsapp_reminders: bool
    sms_confirmations: bool
    whatsapp_confirmations: bool
    reminder_2h: bool


# ── Staff ─────────────────────────────────────────────────────────────────────

class StaffCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    color: Optional[str] = "#6366f1"


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


class StaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    color: str
    is_active: bool


# ── Business Hours ────────────────────────────────────────────────────────────

class BusinessHoursEntry(BaseModel):
    day_of_week: int
    is_open: bool
    open_time: str
    close_time: str


class BusinessHoursUpdate(BaseModel):
    hours: list[BusinessHoursEntry]


class BusinessHoursResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_of_week: int
    is_open: bool
    open_time: str
    close_time: str


# ── Email Account ─────────────────────────────────────────────────────────────

class EmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    email_address: str
    token_expiry: Optional[datetime]


# ── Reminder Log ──────────────────────────────────────────────────────────────

class ReminderLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: Optional[int]
    channel: str
    trigger: str
    status: str
    error_message: Optional[str]
    created_at: datetime


# ── Usage ─────────────────────────────────────────────────────────────────────

class UsageResponse(BaseModel):
    month: str
    whatsapp_count: int
    sms_count: int
    email_count: int
    whatsapp_cost: float
    sms_cost: float
    base_cost: float
    total_estimated: float
    recent_logs: list[ReminderLogResponse]


# ── Business settings additions ────────────────────────────────────────────────

class BusinessLinkUpdate(BaseModel):
    google_review_link: Optional[str] = None
    tracking_phone_number: Optional[str] = None


# ── Automation Settings ────────────────────────────────────────────────────────

class AutomationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    missed_call_recovery: bool
    missed_call_message: Optional[str]
    followup_enabled: bool
    followup_message: Optional[str]
    review_requests_enabled: bool
    review_request_channel: str
    review_request_message: Optional[str]
    whatsapp_reminder_template: Optional[str]
    reminder_timing_hours: int
    receptionist_enabled: bool
    receptionist_greeting: Optional[str]


class AutomationSettingsUpdate(BaseModel):
    missed_call_recovery: Optional[bool] = None
    missed_call_message: Optional[str] = None
    followup_enabled: Optional[bool] = None
    followup_message: Optional[str] = None
    review_requests_enabled: Optional[bool] = None
    review_request_channel: Optional[str] = None
    review_request_message: Optional[str] = None
    whatsapp_reminder_template: Optional[str] = None
    reminder_timing_hours: Optional[int] = None
    receptionist_enabled: Optional[bool] = None
    receptionist_greeting: Optional[str] = None


# ── Missed Call ────────────────────────────────────────────────────────────────

class MissedCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caller_number: str
    called_at: datetime
    call_status: str
    recovery_sent: bool
    recovery_sent_at: Optional[datetime]
    followup_sent: bool
    followup_sent_at: Optional[datetime]
    booking_id: Optional[int]


# ── Review Request ─────────────────────────────────────────────────────────────

class ReviewRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    channel: str
    status: str
    error_message: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime


# ── Callback Request ───────────────────────────────────────────────────────────

class CallbackRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caller_number: str
    requested_at: datetime
    status: str
    notes: Optional[str]
    missed_call_id: Optional[int]


class CallbackStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


# ── Voicemail ──────────────────────────────────────────────────────────────────

class VoicemailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caller_number: str
    recording_url: Optional[str]
    duration_seconds: Optional[int]
    transcription: Optional[str]
    ai_summary: Optional[str]
    ai_category: Optional[str]
    created_at: datetime
    missed_call_id: Optional[int]


# ── Automation Stats ───────────────────────────────────────────────────────────

class AutomationStatsResponse(BaseModel):
    missed_calls_month: int
    recovery_sent_month: int
    recovered_bookings_month: int
    review_requests_month: int
    callbacks_pending: int
    voicemails_unread: int
    failed_messages_month: int

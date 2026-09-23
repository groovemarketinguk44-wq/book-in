from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text
)
from .database import Base

DEFAULT_MISSED_CALL_MSG = (
    "Sorry we missed your call — we were busy with clients. "
    "You can book online here: {{booking_link}} or reply to this message and we'll get back to you."
)
DEFAULT_FOLLOWUP_MSG = (
    "Just checking in — did you still want to book an appointment with {{salon_name}}? "
    "You can book here: {{booking_link}}"
)
DEFAULT_REVIEW_MSG = (
    "Thanks for visiting {{salon_name}}. We'd really appreciate a quick review if you were "
    "happy with your appointment: {{google_review_link}}"
)
DEFAULT_WA_REMINDER_TEMPLATE = (
    "Hi {{customer_name}} \U0001f44b\n\n"
    "Just a reminder that your *{{service_name}}* appointment at *{{salon_name}}* "
    "is {{timing}} at *{{time}}*.\n\nSee you then!"
)
DEFAULT_RECEPTIONIST_GREETING = (
    "Sorry, we're busy with clients right now. "
    "Press 1 to receive a booking link. "
    "Press 2 to leave a message. "
    "Press 3 to request a callback."
)


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=False)
    phone = Column(String)
    address = Column(Text)
    logo_url = Column(String)
    timezone = Column(String, default="Europe/London")
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)
    subscription_status = Column(String, default="trial")  # trial, active, cancelled, expired
    trial_ends_at = Column(DateTime)
    onboarding_complete = Column(Boolean, default=False)
    primary_color = Column(String, default="#111827")
    email_confirmations = Column(Boolean, default=True)
    email_reminders = Column(Boolean, default=True)
    sms_reminders = Column(Boolean, default=False)
    whatsapp_reminders = Column(Boolean, default=False)
    sms_confirmations = Column(Boolean, default=False)
    whatsapp_confirmations = Column(Boolean, default=False)
    reminder_2h = Column(Boolean, default=True)
    stripe_whatsapp_item_id = Column(String)
    stripe_sms_item_id = Column(String)
    plan = Column(String, default="pro")   # pro, ultra
    google_review_link = Column(String)
    tracking_phone_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    role = Column(String, default="admin")
    is_platform_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    image_url = Column(String)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    image_url = Column(String)
    category_id = Column(Integer, ForeignKey("categories.id"))
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    active = Column(Boolean, default=True)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_phone = Column(String)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, default="confirmed")  # confirmed, cancelled, completed
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    reminder_sent = Column(Boolean, default=False)
    reminder_2h_sent = Column(Boolean, default=False)
    review_request_sent = Column(Boolean, default=False)
    source = Column(String)  # instagram, facebook, google, tiktok, direct, etc.
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String)
    phone = Column(String)
    color = Column(String, default="#6366f1")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StaffService(Base):
    __tablename__ = "staff_services"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)


class StaffHours(Base):
    __tablename__ = "staff_hours"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Mon … 6=Sun
    is_open = Column(Boolean, default=True)
    open_time = Column(String, default="09:00")
    close_time = Column(String, default="18:00")


class BusinessHours(Base):
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Mon … 6=Sun
    is_open = Column(Boolean, default=True)
    open_time = Column(String, default="09:00")
    close_time = Column(String, default="18:00")


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    channel = Column(String, nullable=False)   # email, sms, whatsapp
    trigger = Column(String, nullable=False)   # confirmation, 24h, 2h
    status = Column(String, default="sent")    # sent, failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, unique=True)
    provider = Column(String, nullable=False)  # gmail, outlook
    email_address = Column(String, nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expiry = Column(DateTime)


class AutomationSettings(Base):
    __tablename__ = "automation_settings"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, unique=True)
    missed_call_recovery = Column(Boolean, default=False)
    missed_call_message = Column(Text)
    followup_enabled = Column(Boolean, default=False)
    followup_message = Column(Text)
    review_requests_enabled = Column(Boolean, default=False)
    review_request_channel = Column(String, default="whatsapp")  # sms, whatsapp
    review_request_message = Column(Text)
    whatsapp_reminder_template = Column(Text)
    reminder_timing_hours = Column(Integer, default=24)
    receptionist_enabled = Column(Boolean, default=False)
    receptionist_greeting = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MissedCall(Base):
    __tablename__ = "missed_calls"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    caller_number = Column(String, nullable=False)
    called_at = Column(DateTime, default=datetime.utcnow)
    call_status = Column(String, default="missed")  # missed, recovered
    recovery_sent = Column(Boolean, default=False)
    recovery_sent_at = Column(DateTime)
    followup_sent = Column(Boolean, default=False)
    followup_sent_at = Column(DateTime)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    call_sid = Column(String)


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    to_number = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # sms, whatsapp
    message_type = Column(String, nullable=False)  # missed_call_recovery, followup, review_request
    status = Column(String, default="pending")  # pending, sent, failed
    message_body = Column(Text)
    error_message = Column(Text)
    reference_id = Column(Integer)
    reference_type = Column(String)  # missed_call, booking
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    channel = Column(String, nullable=False)  # sms, whatsapp
    status = Column(String, default="pending")  # pending, sent, failed
    error_message = Column(Text)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class CallbackRequest(Base):
    __tablename__ = "callback_requests"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    caller_number = Column(String, nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, completed
    notes = Column(Text)
    missed_call_id = Column(Integer, ForeignKey("missed_calls.id"), nullable=True)


class Voicemail(Base):
    __tablename__ = "voicemails"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    caller_number = Column(String, nullable=False)
    recording_url = Column(String)
    recording_sid = Column(String)
    duration_seconds = Column(Integer)
    transcription = Column(Text)
    ai_summary = Column(Text)
    ai_category = Column(String)  # booking, pricing, cancellation, complaint, general
    created_at = Column(DateTime, default=datetime.utcnow)
    missed_call_id = Column(Integer, ForeignKey("missed_calls.id"), nullable=True)

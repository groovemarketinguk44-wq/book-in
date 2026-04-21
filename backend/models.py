from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text
)
from .database import Base


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
    email_confirmations = Column(Boolean, default=True)
    email_reminders = Column(Boolean, default=True)
    sms_reminders = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    role = Column(String, default="admin")
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
    reminder_sent = Column(Boolean, default=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    amount = Column(Numeric(10, 2), nullable=False)
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

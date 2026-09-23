"""Public client-facing booking API — no auth required."""
import time
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

import pytz
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Booking, Business, BusinessHours, Category, Service, Staff, StaffService, Transaction
from ..schemas import BookingCreate, BookingResponse, CategoryResponse, ServiceResponse

router = APIRouter(prefix="/api/client", tags=["client"])

# In-memory rate limiter: max 5 booking attempts per IP per 60 seconds
_ip_attempts: dict[str, list[float]] = defaultdict(list)
_ip_lock = Lock()
_WINDOW = 60   # seconds
_MAX_ATTEMPTS = 5


def _check_ip_rate(ip: str):
    now = time.monotonic()
    with _ip_lock:
        times = _ip_attempts[ip]
        times[:] = [t for t in times if now - t < _WINDOW]
        if len(times) >= _MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many booking attempts. Please wait a moment.")
        times.append(now)


def _get_business(slug: str, db: Session) -> Business:
    biz = db.query(Business).filter(Business.slug == slug).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    return biz


@router.get("/{slug}")
def get_business_info(slug: str, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)
    return {
        "id": biz.id,
        "name": biz.name,
        "slug": biz.slug,
        "phone": biz.phone,
        "address": biz.address,
        "logo_url": biz.logo_url,
        "timezone": biz.timezone,
        "primary_color": biz.primary_color or "#111827",
    }


@router.get("/{slug}/categories", response_model=List[CategoryResponse])
def get_categories(slug: str, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)
    return db.query(Category).filter(Category.business_id == biz.id).all()


@router.get("/{slug}/services", response_model=List[ServiceResponse])
def get_services(slug: str, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)
    return (
        db.query(Service)
        .filter(Service.business_id == biz.id, Service.active == True)
        .all()
    )


@router.get("/{slug}/staff")
def get_business_staff(slug: str, service_id: int = None, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)
    q = db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True)
    staff_list = q.all()
    if service_id:
        # Only return staff who have this service assigned (or if staff has no services assigned, include them)
        assigned = {r.staff_id for r in db.query(StaffService).filter(StaffService.service_id == service_id).all()}
        # Staff with no service assignments are assumed to do everything
        no_assignments = {s.id for s in staff_list if not db.query(StaffService).filter(StaffService.staff_id == s.id).first()}
        staff_list = [s for s in staff_list if s.id in assigned or s.id in no_assignments]
    return [{"id": s.id, "name": s.name, "color": s.color} for s in staff_list]


@router.get("/{slug}/hours")
def get_business_hours(slug: str, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)
    rows = db.query(BusinessHours).filter(BusinessHours.business_id == biz.id).order_by(BusinessHours.day_of_week).all()
    if not rows:
        # Default: Mon-Fri open, Sat-Sun closed
        return [{"day_of_week": i, "is_open": i < 5, "open_time": "09:00", "close_time": "18:00"} for i in range(7)]
    return [{"day_of_week": r.day_of_week, "is_open": r.is_open, "open_time": r.open_time, "close_time": r.close_time} for r in rows]


@router.get("/{slug}/services/by-category/{category_id}", response_model=List[ServiceResponse])
def get_services_by_category(slug: str, category_id: int, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)
    return (
        db.query(Service)
        .filter(
            Service.business_id == biz.id,
            Service.category_id == category_id,
            Service.active == True,
        )
        .all()
    )


@router.post("/{slug}/book", response_model=BookingResponse, status_code=201)
def create_booking(slug: str, body: BookingCreate, request: Request, db: Session = Depends(get_db)):
    # IP rate limit — blocks bots hammering the endpoint
    client_ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    _check_ip_rate(client_ip)

    biz = _get_business(slug, db)

    # Per-phone guard — same number can't create more than 3 bookings in 24h
    if body.customer_phone:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_phone = db.query(Booking).filter(
            Booking.customer_phone == body.customer_phone,
            Booking.business_id == biz.id,
            Booking.created_at >= cutoff,
        ).count()
        if recent_phone >= 3:
            raise HTTPException(status_code=429, detail="Too many bookings from this phone number today.")

    svc = db.query(Service).filter(
        Service.id == body.service_id,
        Service.business_id == biz.id,
        Service.active == True,
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    start_utc = body.start_time.replace(tzinfo=None)
    end_utc = start_utc + timedelta(minutes=svc.duration_minutes)

    # Prevent overlaps
    overlap = db.query(Booking).filter(
        Booking.business_id == biz.id,
        Booking.status != "cancelled",
        Booking.start_time < end_utc,
        Booking.end_time > start_utc,
    ).first()
    if overlap:
        raise HTTPException(status_code=409, detail="Time slot no longer available")

    booking = Booking(
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        service_id=body.service_id,
        staff_id=body.staff_id,
        start_time=start_utc,
        end_time=end_utc,
        business_id=biz.id,
        notes=body.notes,
        source=body.source,
    )
    db.add(booking)
    db.flush()

    # Record transaction
    txn = Transaction(
        business_id=biz.id,
        booking_id=booking.id,
        amount=svc.price,
    )
    db.add(txn)
    db.commit()
    db.refresh(booking)

    # Send confirmations (non-blocking)
    try:
        from ..services.reminder_worker import send_booking_confirmations
        send_booking_confirmations(booking, svc, biz, db)
        db.commit()
    except Exception as e:
        print(f"[confirmation] failed: {e}")

    return booking

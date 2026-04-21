"""Public client-facing booking API — no auth required."""
from datetime import datetime, timedelta

import pytz
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Booking, Business, Category, Service, Transaction
from ..schemas import BookingCreate, BookingResponse, CategoryResponse, ServiceResponse

router = APIRouter(prefix="/api/client", tags=["client"])


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
def create_booking(slug: str, body: BookingCreate, db: Session = Depends(get_db)):
    biz = _get_business(slug, db)

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
        start_time=start_utc,
        end_time=end_utc,
        business_id=biz.id,
        notes=body.notes,
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

    # Send confirmation (non-blocking)
    try:
        from ..services.email_service import send_booking_confirmation
        send_booking_confirmation(booking, svc, biz, db)
    except Exception:
        pass

    return booking

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Booking, Business, Service, Staff, Transaction
from ..schemas import BookingResponse, BookingUpdate, BookingWithService

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("", response_model=List[BookingWithService])
def list_bookings(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    q = db.query(Booking).filter(Booking.business_id == business.id)
    if status:
        q = q.filter(Booking.status == status)
    if date_from:
        q = q.filter(Booking.start_time >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Booking.start_time <= datetime.fromisoformat(date_to))
    bookings = q.order_by(Booking.start_time.desc()).all()

    result = []
    for b in bookings:
        svc = db.query(Service).filter(Service.id == b.service_id).first()
        item = BookingWithService.model_validate(b)
        if svc:
            item.service_name = svc.name
            item.service_price = svc.price
            item.service_duration = svc.duration_minutes
        if b.staff_id:
            s = db.query(Staff).filter(Staff.id == b.staff_id).first()
            if s:
                item.staff_name = s.name
        result.append(item)
    return result


@router.get("/{booking_id}", response_model=BookingWithService)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    b = db.query(Booking).filter(
        Booking.id == booking_id, Booking.business_id == business.id
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    svc = db.query(Service).filter(Service.id == b.service_id).first()
    item = BookingWithService.model_validate(b)
    if svc:
        item.service_name = svc.name
        item.service_price = svc.price
        item.service_duration = svc.duration_minutes
    return item


@router.patch("/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: int,
    body: BookingUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    b = db.query(Booking).filter(
        Booking.id == booking_id, Booking.business_id == business.id
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if body.status:
        b.status = body.status
    if body.notes is not None:
        b.notes = body.notes
    db.commit()
    db.refresh(b)
    return b


@router.delete("/{booking_id}", status_code=204)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    b = db.query(Booking).filter(
        Booking.id == booking_id, Booking.business_id == business.id
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    b.status = "cancelled"
    db.commit()

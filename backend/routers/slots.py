from datetime import datetime, timedelta, date
from typing import List

import pytz
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_business, get_client_business
from ..models import Booking, Business, Service
from ..schemas import SlotResponse

router = APIRouter(prefix="/api/slots", tags=["slots"])

BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 18
SLOT_INTERVAL_MINUTES = 15


def _generate_slots(
    target_date: date,
    duration: int,
    business: Business,
    db: Session,
) -> List[dict]:
    tz = pytz.timezone(business.timezone or "Europe/London")

    day_start = tz.localize(
        datetime(target_date.year, target_date.month, target_date.day, BUSINESS_START_HOUR, 0)
    )
    day_end = tz.localize(
        datetime(target_date.year, target_date.month, target_date.day, BUSINESS_END_HOUR, 0)
    )

    # Fetch confirmed bookings for that day (UTC range)
    utc_start = day_start.astimezone(pytz.utc).replace(tzinfo=None)
    utc_end = day_end.astimezone(pytz.utc).replace(tzinfo=None)

    existing = (
        db.query(Booking)
        .filter(
            Booking.business_id == business.id,
            Booking.status != "cancelled",
            Booking.start_time < utc_end,
            Booking.end_time > utc_start,
        )
        .all()
    )

    slots = []
    current = day_start
    while current + timedelta(minutes=duration) <= day_end:
        slot_end = current + timedelta(minutes=duration)

        # Convert to UTC for overlap check
        cur_utc = current.astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = slot_end.astimezone(pytz.utc).replace(tzinfo=None)

        overlaps = any(
            not (end_utc <= b.start_time or cur_utc >= b.end_time) for b in existing
        )

        if not overlaps and current > datetime.now(tz):
            slots.append(
                {
                    "time": current.strftime("%H:%M"),
                    "datetime": current.isoformat(),
                }
            )

        current += timedelta(minutes=SLOT_INTERVAL_MINUTES)

    return slots


@router.get("/client/{slug}/{service_id}")
def client_slots(
    slug: str,
    service_id: int,
    date: str = Query(...),
    db: Session = Depends(get_db),
):
    from ..models import Business as Biz

    business = db.query(Biz).filter(Biz.slug == slug).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    svc = db.query(Service).filter(
        Service.id == service_id, Service.business_id == business.id, Service.active == True
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    try:
        target = datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    return _generate_slots(target, svc.duration_minutes, business, db)


@router.get("/admin/{service_id}")
def admin_slots(
    service_id: int,
    date: str = Query(...),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    svc = db.query(Service).filter(
        Service.id == service_id, Service.business_id == business.id
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    try:
        target = datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    return _generate_slots(target, svc.duration_minutes, business, db)

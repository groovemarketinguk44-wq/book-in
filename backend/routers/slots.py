from datetime import datetime, timedelta, date
from typing import List

import pytz
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_business, get_client_business
from ..models import Booking, Business, BusinessHours, Service, StaffHours
from ..schemas import SlotResponse

router = APIRouter(prefix="/api/slots", tags=["slots"])

SLOT_INTERVAL_MINUTES = 15


def _get_hours(business_id: int, day_of_week: int, db: Session, staff_id: int = None):
    if staff_id:
        row = db.query(StaffHours).filter(
            StaffHours.staff_id == staff_id,
            StaffHours.day_of_week == day_of_week,
        ).first()
    else:
        row = db.query(BusinessHours).filter(
            BusinessHours.business_id == business_id,
            BusinessHours.day_of_week == day_of_week,
        ).first()
    if not row:
        return True, "09:00", "18:00"
    return row.is_open, row.open_time, row.close_time


def _generate_slots(
    target_date: date,
    duration: int,
    business: Business,
    db: Session,
    staff_id: int = None,
) -> List[dict]:
    tz = pytz.timezone(business.timezone or "Europe/London")
    dow = target_date.weekday()

    is_open, open_time, close_time = _get_hours(business.id, dow, db, staff_id)
    if not is_open:
        return []

    open_h, open_m = map(int, open_time.split(":"))
    close_h, close_m = map(int, close_time.split(":"))

    day_start = tz.localize(
        datetime(target_date.year, target_date.month, target_date.day, open_h, open_m)
    )
    day_end = tz.localize(
        datetime(target_date.year, target_date.month, target_date.day, close_h, close_m)
    )

    # Fetch confirmed bookings for that day (UTC range)
    utc_start = day_start.astimezone(pytz.utc).replace(tzinfo=None)
    utc_end = day_end.astimezone(pytz.utc).replace(tzinfo=None)

    q = db.query(Booking).filter(
        Booking.business_id == business.id,
        Booking.status != "cancelled",
        Booking.start_time < utc_end,
        Booking.end_time > utc_start,
    )
    if staff_id:
        q = q.filter(Booking.staff_id == staff_id)
    existing = (
        q
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
    staff_id: int = Query(None),
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

    return _generate_slots(target, svc.duration_minutes, business, db, staff_id)


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

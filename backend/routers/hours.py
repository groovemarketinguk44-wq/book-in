from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, BusinessHours
from ..schemas import BusinessHoursResponse, BusinessHoursUpdate

router = APIRouter(prefix="/api/hours", tags=["hours"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_HOURS = [
    {"day_of_week": i, "is_open": i < 5, "open_time": "09:00", "close_time": "18:00"}
    for i in range(7)
]


def ensure_hours(business_id: int, db: Session) -> list:
    existing = db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()
    if len(existing) == 7:
        return existing

    existing_days = {h.day_of_week for h in existing}
    for d in DEFAULT_HOURS:
        if d["day_of_week"] not in existing_days:
            db.add(BusinessHours(business_id=business_id, **d))
    db.commit()
    return db.query(BusinessHours).filter(BusinessHours.business_id == business_id).order_by(BusinessHours.day_of_week).all()


@router.get("", response_model=List[BusinessHoursResponse])
def get_hours(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    return ensure_hours(business.id, db)


@router.put("")
def update_hours(
    body: BusinessHoursUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    ensure_hours(business.id, db)
    for entry in body.hours:
        row = db.query(BusinessHours).filter(
            BusinessHours.business_id == business.id,
            BusinessHours.day_of_week == entry.day_of_week,
        ).first()
        if row:
            row.is_open = entry.is_open
            row.open_time = entry.open_time
            row.close_time = entry.close_time
    db.commit()
    return {"ok": True}

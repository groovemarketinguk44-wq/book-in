from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, Service, Staff, StaffHours, StaffService
from ..schemas import BusinessHoursEntry, BusinessHoursUpdate, StaffCreate, StaffResponse, StaffUpdate

router = APIRouter(prefix="/api/staff", tags=["staff"])

DEFAULT_HOURS = [
    {"day_of_week": i, "is_open": i < 5, "open_time": "09:00", "close_time": "18:00"}
    for i in range(7)
]


def _ensure_staff_hours(staff_id: int, db: Session):
    existing = db.query(StaffHours).filter(StaffHours.staff_id == staff_id).all()
    if len(existing) == 7:
        return existing
    existing_days = {h.day_of_week for h in existing}
    for d in DEFAULT_HOURS:
        if d["day_of_week"] not in existing_days:
            db.add(StaffHours(staff_id=staff_id, **d))
    db.commit()
    return db.query(StaffHours).filter(StaffHours.staff_id == staff_id).order_by(StaffHours.day_of_week).all()


@router.get("", response_model=List[StaffResponse])
def list_staff(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    return db.query(Staff).filter(Staff.business_id == business.id, Staff.is_active == True).all()


@router.post("", response_model=StaffResponse, status_code=201)
def create_staff(
    body: StaffCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = Staff(business_id=business.id, **body.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    _ensure_staff_hours(member.id, db)
    return member


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: int,
    body: StaffUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{staff_id}", status_code=204)
def delete_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    member.is_active = False
    db.commit()


# ── Hours ──────────────────────────────────────────────────────────────────────

@router.get("/{staff_id}/hours")
def get_staff_hours(
    staff_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    rows = _ensure_staff_hours(staff_id, db)
    return [{"day_of_week": r.day_of_week, "is_open": r.is_open, "open_time": r.open_time, "close_time": r.close_time} for r in rows]


@router.put("/{staff_id}/hours")
def update_staff_hours(
    staff_id: int,
    body: BusinessHoursUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    _ensure_staff_hours(staff_id, db)
    for entry in body.hours:
        row = db.query(StaffHours).filter(
            StaffHours.staff_id == staff_id,
            StaffHours.day_of_week == entry.day_of_week,
        ).first()
        if row:
            row.is_open = entry.is_open
            row.open_time = entry.open_time
            row.close_time = entry.close_time
    db.commit()
    return {"ok": True}


# ── Services ───────────────────────────────────────────────────────────────────

@router.get("/{staff_id}/services")
def get_staff_services(
    staff_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    rows = db.query(StaffService).filter(StaffService.staff_id == staff_id).all()
    return {"service_ids": [r.service_id for r in rows]}


@router.put("/{staff_id}/services")
def update_staff_services(
    staff_id: int,
    body: dict,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    member = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Staff member not found")

    service_ids: list[int] = body.get("service_ids", [])

    # Verify services belong to this business
    valid = {s.id for s in db.query(Service).filter(
        Service.business_id == business.id,
        Service.id.in_(service_ids),
    ).all()}

    db.query(StaffService).filter(StaffService.staff_id == staff_id).delete()
    for sid in service_ids:
        if sid in valid:
            db.add(StaffService(staff_id=staff_id, service_id=sid))
    db.commit()
    return {"ok": True}

"""Platform admin API — only accessible to users with is_platform_admin=True."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_platform_admin
from ..models import Booking, Business, ReminderLog, Transaction, User

router = APIRouter(prefix="/api/admin", tags=["admin"])

PLAN_MRR = {"pro": 14.99, "ultra": 39.99}


def _exclude_platform(db: Session):
    """Return a Business query that excludes the internal platform business."""
    admin_biz_ids = (
        db.query(User.business_id).filter(User.is_platform_admin == True).subquery()
    )
    return db.query(Business).filter(~Business.id.in_(admin_biz_ids))


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _=Depends(require_platform_admin),
):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    businesses = _exclude_platform(db).all()
    total = len(businesses)
    active = sum(1 for b in businesses if b.subscription_status == "active")
    trial = sum(1 for b in businesses if b.subscription_status == "trial")
    cancelled = sum(1 for b in businesses if b.subscription_status in ("cancelled", "expired"))
    mrr = sum(PLAN_MRR.get(b.plan or "pro", 14.99) for b in businesses if b.subscription_status == "active")

    total_bookings = db.query(Booking).count()
    bookings_month = db.query(Booking).filter(Booking.start_time >= month_start).count()

    # Signups this month
    signups_month = sum(1 for b in businesses if b.created_at and b.created_at >= month_start)

    # Trials expiring in next 3 days
    in_3_days = now + timedelta(days=3)
    expiring_soon = sum(
        1 for b in businesses
        if b.subscription_status == "trial" and b.trial_ends_at and b.trial_ends_at <= in_3_days and b.trial_ends_at > now
    )

    return {
        "total_clients": total,
        "active": active,
        "trial": trial,
        "cancelled": cancelled,
        "mrr": round(mrr, 2),
        "total_bookings": total_bookings,
        "bookings_month": bookings_month,
        "signups_month": signups_month,
        "expiring_soon": expiring_soon,
    }


@router.get("/businesses")
def admin_businesses(
    db: Session = Depends(get_db),
    _=Depends(require_platform_admin),
):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    businesses = _exclude_platform(db).order_by(Business.created_at.desc()).all()

    # Preload user emails
    user_map = {u.business_id: u.email for u in db.query(User).filter(User.is_platform_admin == False).all()}

    # Preload booking counts (this month)
    booking_counts = {
        r[0]: r[1]
        for r in db.query(Booking.business_id, func.count(Booking.id))
        .filter(Booking.start_time >= month_start)
        .group_by(Booking.business_id)
        .all()
    }

    # Preload total bookings
    total_booking_counts = {
        r[0]: r[1]
        for r in db.query(Booking.business_id, func.count(Booking.id))
        .group_by(Booking.business_id)
        .all()
    }

    # Preload monthly revenue
    monthly_revenue = {
        r[0]: float(r[1] or 0)
        for r in db.query(Transaction.business_id, func.sum(Transaction.amount))
        .filter(Transaction.created_at >= month_start)
        .group_by(Transaction.business_id)
        .all()
    }

    # SMS/WhatsApp this month
    sms_counts = {
        r[0]: r[1]
        for r in db.query(ReminderLog.business_id, func.count(ReminderLog.id))
        .filter(ReminderLog.channel == "sms", ReminderLog.created_at >= month_start)
        .group_by(ReminderLog.business_id)
        .all()
    }
    wa_counts = {
        r[0]: r[1]
        for r in db.query(ReminderLog.business_id, func.count(ReminderLog.id))
        .filter(ReminderLog.channel == "whatsapp", ReminderLog.created_at >= month_start)
        .group_by(ReminderLog.business_id)
        .all()
    }

    results = []
    for b in businesses:
        days_left = None
        if b.subscription_status == "trial" and b.trial_ends_at:
            days_left = max(0, (b.trial_ends_at - now).days)
        results.append({
            "id": b.id,
            "name": b.name,
            "slug": b.slug,
            "email": user_map.get(b.id, b.email),
            "plan": b.plan or "pro",
            "subscription_status": b.subscription_status,
            "trial_ends_at": b.trial_ends_at.isoformat() if b.trial_ends_at else None,
            "trial_days_left": days_left,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "mrr": PLAN_MRR.get(b.plan or "pro", 14.99) if b.subscription_status == "active" else 0,
            "bookings_month": booking_counts.get(b.id, 0),
            "total_bookings": total_booking_counts.get(b.id, 0),
            "revenue_month": monthly_revenue.get(b.id, 0),
            "sms_month": sms_counts.get(b.id, 0),
            "wa_month": wa_counts.get(b.id, 0),
        })

    return results

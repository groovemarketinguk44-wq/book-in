from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Booking, Business, Staff, Transaction

router = APIRouter(prefix="/api/financials", tags=["financials"])


def _sum(db, business_id, start, end) -> float:
    result = db.query(func.sum(Transaction.amount)).filter(
        Transaction.business_id == business_id,
        Transaction.created_at >= start,
        Transaction.created_at < end,
    ).scalar()
    return float(result or 0)


def _count(db, business_id, start, end) -> int:
    return db.query(Transaction).filter(
        Transaction.business_id == business_id,
        Transaction.created_at >= start,
        Transaction.created_at < end,
    ).count()


@router.get("")
def get_financials(
    period: str = Query("this_month", enum=["this_week", "last_week", "this_month"]),
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=today.weekday())

    if period == "this_week":
        range_start = week_start
        range_end = week_start + timedelta(days=7)
        labels = [(week_start + timedelta(days=i)).strftime("%a") for i in range(7)]
        data = [
            _sum(db, business.id, week_start + timedelta(days=i), week_start + timedelta(days=i + 1))
            for i in range(7)
        ]
    elif period == "last_week":
        range_start = week_start - timedelta(days=7)
        range_end = week_start
        labels = [(range_start + timedelta(days=i)).strftime("%a") for i in range(7)]
        data = [
            _sum(db, business.id, range_start + timedelta(days=i), range_start + timedelta(days=i + 1))
            for i in range(7)
        ]
    else:  # this_month
        range_start = today.replace(day=1)
        if today.month == 12:
            range_end = today.replace(year=today.year + 1, month=1, day=1)
        else:
            range_end = today.replace(month=today.month + 1, day=1)
        days_in_range = (range_end - range_start).days
        labels = [(range_start + timedelta(days=i)).strftime("%-d") for i in range(days_in_range)]
        data = [
            _sum(db, business.id, range_start + timedelta(days=i), range_start + timedelta(days=i + 1))
            for i in range(days_in_range)
        ]

    total = _sum(db, business.id, datetime(2000, 1, 1), now + timedelta(days=1))
    total_count = _count(db, business.id, datetime(2000, 1, 1), now + timedelta(days=1))
    daily = _sum(db, business.id, today, today + timedelta(days=1))
    weekly = _sum(db, business.id, week_start, week_start + timedelta(days=7))
    monthly = _sum(db, business.id, today.replace(day=1), now + timedelta(days=1))

    return {
        "total_revenue": total,
        "booking_count": total_count,
        "avg_booking_value": round(total / total_count, 2) if total_count else 0,
        "daily_revenue": daily,
        "weekly_revenue": weekly,
        "monthly_revenue": monthly,
        "chart_labels": labels,
        "chart_data": data,
    }


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=today.weekday())

    # Month range
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1)

    # Booking stats this month
    month_bookings = (
        db.query(Booking)
        .filter(
            Booking.business_id == business.id,
            Booking.start_time >= month_start,
            Booking.start_time < month_end,
        )
        .all()
    )
    month_revenue = _sum(db, business.id, month_start, month_end)

    # Weekly revenue (Mon–Sun current week)
    weekly_labels = [(week_start + timedelta(days=i)).strftime("%a") for i in range(7)]
    weekly_data = [
        _sum(db, business.id, week_start + timedelta(days=i), week_start + timedelta(days=i + 1))
        for i in range(7)
    ]

    # 12-week trend
    twelve_weeks_ago = week_start - timedelta(weeks=11)
    trend_labels = []
    trend_data = []
    for i in range(12):
        wk_start = twelve_weeks_ago + timedelta(weeks=i)
        wk_end = wk_start + timedelta(weeks=1)
        trend_labels.append(wk_start.strftime("%-d %b"))
        trend_data.append(_sum(db, business.id, wk_start, wk_end))

    # Staff revenue (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    staff_rows = (
        db.query(Staff.name, func.sum(Transaction.amount))
        .join(Booking, Booking.staff_id == Staff.id)
        .join(Transaction, Transaction.booking_id == Booking.id)
        .filter(
            Transaction.business_id == business.id,
            Transaction.created_at >= thirty_days_ago,
        )
        .group_by(Staff.id, Staff.name)
        .all()
    )
    staff_revenue = [{"name": name, "revenue": float(amt or 0)} for name, amt in staff_rows]

    # Customer sources
    source_rows = (
        db.query(Booking.source, func.count(Booking.id))
        .filter(Booking.business_id == business.id)
        .group_by(Booking.source)
        .all()
    )
    sources = [
        {"source": (src or "direct").lower(), "count": cnt}
        for src, cnt in source_rows
    ]

    return {
        "booking_stats": {
            "total_month": len(month_bookings),
            "completed_month": sum(1 for b in month_bookings if b.status == "completed"),
            "cancelled_month": sum(1 for b in month_bookings if b.status == "cancelled"),
            "confirmed_month": sum(1 for b in month_bookings if b.status == "confirmed"),
            "revenue_month": month_revenue,
        },
        "weekly_revenue": {
            "labels": weekly_labels,
            "data": weekly_data,
        },
        "weekly_trend": {
            "labels": trend_labels,
            "data": trend_data,
        },
        "staff_revenue": staff_revenue,
        "sources": sources,
    }

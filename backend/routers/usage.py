from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, ReminderLog
from ..schemas import ReminderLogResponse, UsageResponse

router = APIRouter(prefix="/api/usage", tags=["usage"])

WHATSAPP_RATE = 0.05
SMS_RATE = 0.10
BASE_COST = 9.99


@router.get("", response_model=UsageResponse)
def get_usage(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    logs = (
        db.query(ReminderLog)
        .filter(
            ReminderLog.business_id == business.id,
            ReminderLog.created_at >= month_start,
        )
        .order_by(ReminderLog.created_at.desc())
        .all()
    )

    sent = [l for l in logs if l.status == "sent"]
    whatsapp_count = sum(1 for l in sent if l.channel == "whatsapp")
    sms_count = sum(1 for l in sent if l.channel == "sms")
    email_count = sum(1 for l in sent if l.channel == "email")

    whatsapp_cost = round(whatsapp_count * WHATSAPP_RATE, 2)
    sms_cost = round(sms_count * SMS_RATE, 2)
    total = round(BASE_COST + whatsapp_cost + sms_cost, 2)

    recent = logs[:50]

    return UsageResponse(
        month=now.strftime("%B %Y"),
        whatsapp_count=whatsapp_count,
        sms_count=sms_count,
        email_count=email_count,
        whatsapp_cost=whatsapp_cost,
        sms_cost=sms_cost,
        base_cost=BASE_COST,
        total_estimated=total,
        recent_logs=recent,
    )

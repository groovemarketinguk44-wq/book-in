from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, EmailAccount
from ..schemas import BusinessResponse, BusinessUpdate, EmailAccountResponse, NotificationSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=BusinessResponse)
def get_settings(business: Business = Depends(get_current_business)):
    return business


@router.patch("", response_model=BusinessResponse)
def update_settings(
    body: BusinessUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return business


@router.patch("/notifications", response_model=BusinessResponse)
def update_notifications(
    body: NotificationSettings,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    business.email_confirmations = body.email_confirmations
    business.email_reminders = body.email_reminders
    business.sms_reminders = body.sms_reminders
    db.commit()
    db.refresh(business)
    return business


@router.get("/email-account", response_model=EmailAccountResponse | None)
def get_email_account(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    return db.query(EmailAccount).filter(EmailAccount.business_id == business.id).first()


@router.delete("/email-account", status_code=204)
def disconnect_email(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    account = db.query(EmailAccount).filter(EmailAccount.business_id == business.id).first()
    if account:
        db.delete(account)
        db.commit()

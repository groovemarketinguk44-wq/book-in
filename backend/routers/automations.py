from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_business
from ..models import (
    AutomationSettings, Business, Booking, MissedCall,
    OutboundMessage, ReviewRequest, CallbackRequest, Voicemail,
    DEFAULT_MISSED_CALL_MSG, DEFAULT_FOLLOWUP_MSG,
    DEFAULT_REVIEW_MSG, DEFAULT_WA_REMINDER_TEMPLATE,
    DEFAULT_RECEPTIONIST_GREETING,
)
from ..schemas import (
    AutomationSettingsResponse, AutomationSettingsUpdate,
    BusinessLinkUpdate, BusinessResponse,
    MissedCallResponse, ReviewRequestResponse,
    CallbackRequestResponse, CallbackStatusUpdate,
    VoicemailResponse, AutomationStatsResponse,
)

router = APIRouter(prefix="/api/automations", tags=["automations"])


def _get_or_create_settings(business_id: int, db: Session) -> AutomationSettings:
    s = db.query(AutomationSettings).filter(
        AutomationSettings.business_id == business_id
    ).first()
    if not s:
        s = AutomationSettings(business_id=business_id)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _fill_defaults(s: AutomationSettings) -> AutomationSettings:
    if not s.missed_call_message:
        s.missed_call_message = DEFAULT_MISSED_CALL_MSG
    if not s.followup_message:
        s.followup_message = DEFAULT_FOLLOWUP_MSG
    if not s.review_request_message:
        s.review_request_message = DEFAULT_REVIEW_MSG
    if not s.whatsapp_reminder_template:
        s.whatsapp_reminder_template = DEFAULT_WA_REMINDER_TEMPLATE
    if not s.receptionist_greeting:
        s.receptionist_greeting = DEFAULT_RECEPTIONIST_GREETING
    return s


# ── Automation settings ───────────────────────────────────────────────────────

@router.get("/settings", response_model=AutomationSettingsResponse)
def get_settings(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    s = _get_or_create_settings(business.id, db)
    return _fill_defaults(s)


@router.put("/settings", response_model=AutomationSettingsResponse)
def update_settings(
    body: AutomationSettingsUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    s = _get_or_create_settings(business.id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return _fill_defaults(s)


# ── Business link settings ────────────────────────────────────────────────────

@router.patch("/links", response_model=BusinessResponse)
def update_links(
    body: BusinessLinkUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return business


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AutomationStatsResponse)
def get_stats(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    missed_calls_month = db.query(MissedCall).filter(
        MissedCall.business_id == business.id,
        MissedCall.called_at >= month_start,
    ).count()

    recovery_sent_month = db.query(MissedCall).filter(
        MissedCall.business_id == business.id,
        MissedCall.called_at >= month_start,
        MissedCall.recovery_sent == True,
    ).count()

    recovered_bookings_month = db.query(MissedCall).filter(
        MissedCall.business_id == business.id,
        MissedCall.called_at >= month_start,
        MissedCall.booking_id != None,
    ).count()

    review_requests_month = db.query(ReviewRequest).filter(
        ReviewRequest.business_id == business.id,
        ReviewRequest.created_at >= month_start,
        ReviewRequest.status == "sent",
    ).count()

    callbacks_pending = db.query(CallbackRequest).filter(
        CallbackRequest.business_id == business.id,
        CallbackRequest.status == "pending",
    ).count()

    voicemails_unread = db.query(Voicemail).filter(
        Voicemail.business_id == business.id,
    ).count()

    failed_messages_month = db.query(OutboundMessage).filter(
        OutboundMessage.business_id == business.id,
        OutboundMessage.created_at >= month_start,
        OutboundMessage.status == "failed",
    ).count()

    return AutomationStatsResponse(
        missed_calls_month=missed_calls_month,
        recovery_sent_month=recovery_sent_month,
        recovered_bookings_month=recovered_bookings_month,
        review_requests_month=review_requests_month,
        callbacks_pending=callbacks_pending,
        voicemails_unread=voicemails_unread,
        failed_messages_month=failed_messages_month,
    )


# ── Missed calls ──────────────────────────────────────────────────────────────

@router.get("/missed-calls", response_model=List[MissedCallResponse])
def list_missed_calls(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return (
        db.query(MissedCall)
        .filter(MissedCall.business_id == business.id)
        .order_by(MissedCall.called_at.desc())
        .limit(200)
        .all()
    )


# ── Review requests ───────────────────────────────────────────────────────────

@router.get("/review-requests", response_model=List[ReviewRequestResponse])
def list_review_requests(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return (
        db.query(ReviewRequest)
        .filter(ReviewRequest.business_id == business.id)
        .order_by(ReviewRequest.created_at.desc())
        .limit(200)
        .all()
    )


# ── Callback requests ─────────────────────────────────────────────────────────

@router.get("/callbacks", response_model=List[CallbackRequestResponse])
def list_callbacks(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return (
        db.query(CallbackRequest)
        .filter(CallbackRequest.business_id == business.id)
        .order_by(CallbackRequest.requested_at.desc())
        .limit(200)
        .all()
    )


@router.patch("/callbacks/{callback_id}", response_model=CallbackRequestResponse)
def update_callback(
    callback_id: int,
    body: CallbackStatusUpdate,
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    cb = db.query(CallbackRequest).filter(
        CallbackRequest.id == callback_id,
        CallbackRequest.business_id == business.id,
    ).first()
    if not cb:
        raise HTTPException(status_code=404, detail="Callback not found")
    cb.status = body.status
    if body.notes is not None:
        cb.notes = body.notes
    db.commit()
    db.refresh(cb)
    return cb


# ── Voicemails ────────────────────────────────────────────────────────────────

@router.get("/voicemails", response_model=List[VoicemailResponse])
def list_voicemails(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    return (
        db.query(Voicemail)
        .filter(Voicemail.business_id == business.id)
        .order_by(Voicemail.created_at.desc())
        .limit(200)
        .all()
    )


# ── Failed messages ───────────────────────────────────────────────────────────

@router.get("/failed-messages")
def list_failed_messages(
    business: Business = Depends(get_current_business),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(OutboundMessage)
        .filter(
            OutboundMessage.business_id == business.id,
            OutboundMessage.status == "failed",
        )
        .order_by(OutboundMessage.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "to_number": r.to_number,
            "channel": r.channel,
            "message_type": r.message_type,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

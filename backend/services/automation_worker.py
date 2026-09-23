"""Automation background jobs — follow-ups and review requests."""
from datetime import datetime, timedelta

from ..database import SessionLocal
from ..models import (
    AutomationSettings, Booking, Business, MissedCall,
    OutboundMessage, ReviewRequest, Service,
    DEFAULT_FOLLOWUP_MSG, DEFAULT_REVIEW_MSG,
)
from ..utils import render_template
from ..config import settings as app_settings


def _booking_link(business: Business) -> str:
    return f"{app_settings.APP_URL}/book/{business.slug}"


def process_followups():
    """Send one follow-up to missed callers who haven't booked after 24h."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        candidates = (
            db.query(MissedCall)
            .filter(
                MissedCall.recovery_sent == True,
                MissedCall.followup_sent == False,
                MissedCall.booking_id == None,
                MissedCall.called_at <= cutoff,
            )
            .all()
        )

        for mc in candidates:
            business = db.query(Business).filter(Business.id == mc.business_id).first()
            if not business:
                continue

            auto = db.query(AutomationSettings).filter(
                AutomationSettings.business_id == business.id
            ).first()

            if not auto or not auto.followup_enabled:
                continue

            template = auto.followup_message or DEFAULT_FOLLOWUP_MSG
            message = render_template(template, {
                "salon_name": business.name,
                "booking_link": _booking_link(business),
            })

            ok, err = _send_message(mc.caller_number, message)
            channel = "whatsapp" if ok else "sms"

            outbound = OutboundMessage(
                business_id=business.id,
                to_number=mc.caller_number,
                channel=channel,
                message_type="followup",
                status="sent" if ok else "failed",
                message_body=message,
                error_message=err if not ok else None,
                reference_id=mc.id,
                reference_type="missed_call",
                sent_at=datetime.utcnow() if ok else None,
            )
            db.add(outbound)

            mc.followup_sent = True
            mc.followup_sent_at = datetime.utcnow()
            try:
                db.commit()
            except Exception as e:
                print(f"[followup] commit error for missed_call {mc.id}: {e}")
                db.rollback()

    finally:
        db.close()


def process_review_requests():
    """Send review request after a booking is marked completed."""
    db = SessionLocal()
    try:
        completed_bookings = (
            db.query(Booking)
            .filter(
                Booking.status == "completed",
                Booking.review_request_sent == False,
            )
            .all()
        )

        for booking in completed_bookings:
            business = db.query(Business).filter(Business.id == booking.business_id).first()
            if not business:
                continue

            auto = db.query(AutomationSettings).filter(
                AutomationSettings.business_id == business.id
            ).first()

            if not auto or not auto.review_requests_enabled:
                continue

            if not business.google_review_link:
                continue

            if not booking.customer_phone:
                continue

            service = db.query(Service).filter(Service.id == booking.service_id).first()
            template = auto.review_request_message or DEFAULT_REVIEW_MSG
            message = render_template(template, {
                "salon_name": business.name,
                "google_review_link": business.google_review_link,
                "customer_name": booking.customer_name,
                "service_name": service.name if service else "",
            })

            channel = auto.review_request_channel or "whatsapp"
            if channel == "whatsapp":
                from .sms_service import send_whatsapp
                ok, err = send_whatsapp(booking.customer_phone, message)
            else:
                from .sms_service import send_sms
                ok, err = send_sms(booking.customer_phone, message)

            review = ReviewRequest(
                business_id=business.id,
                booking_id=booking.id,
                channel=channel,
                status="sent" if ok else "failed",
                error_message=err if not ok else None,
                sent_at=datetime.utcnow() if ok else None,
            )
            db.add(review)

            outbound = OutboundMessage(
                business_id=business.id,
                to_number=booking.customer_phone,
                channel=channel,
                message_type="review_request",
                status="sent" if ok else "failed",
                message_body=message,
                error_message=err if not ok else None,
                reference_id=booking.id,
                reference_type="booking",
                sent_at=datetime.utcnow() if ok else None,
            )
            db.add(outbound)

            booking.review_request_sent = True
            try:
                db.commit()
            except Exception as e:
                print(f"[review_request] commit error for booking {booking.id}: {e}")
                db.rollback()

    finally:
        db.close()


def _send_message(to_number: str, message: str) -> tuple[bool, str]:
    """Try WhatsApp first, fall back to SMS."""
    from .sms_service import send_whatsapp, send_sms
    ok, err = send_whatsapp(to_number, message)
    if ok:
        return ok, err
    return send_sms(to_number, message)

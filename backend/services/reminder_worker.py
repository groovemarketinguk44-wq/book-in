"""Background worker — runs every minute, sends reminders at configured timing."""
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from ..database import SessionLocal
from ..models import AutomationSettings, Booking, Business, ReminderLog, Service
from ..config import settings
from ..utils import render_template
from ..models import DEFAULT_WA_REMINDER_TEMPLATE

# Max outbound SMS+WhatsApp messages per business per 24h window
_DAILY_MSG_CAP = 200


def _under_daily_cap(db, business_id: int) -> bool:
    """Return True if this business is still under the daily outbound message cap."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    sent_today = db.query(ReminderLog).filter(
        ReminderLog.business_id == business_id,
        ReminderLog.channel.in_(["sms", "whatsapp"]),
        ReminderLog.status == "sent",
        ReminderLog.created_at >= cutoff,
    ).count()
    return sent_today < _DAILY_MSG_CAP


def _report_stripe_usage(business, channel: str):
    """Report one metered usage unit to Stripe."""
    if not settings.STRIPE_SECRET_KEY:
        return
    item_id = (
        business.stripe_whatsapp_item_id if channel == "whatsapp"
        else business.stripe_sms_item_id
    )
    if not item_id:
        return
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.SubscriptionItem.create_usage_record(
            item_id,
            quantity=1,
            action="increment",
        )
    except Exception as e:
        print(f"[stripe usage] Failed to report {channel}: {e}")


def _log(db, booking_id, business_id, channel, trigger, success, error=""):
    log = ReminderLog(
        booking_id=booking_id,
        business_id=business_id,
        channel=channel,
        trigger=trigger,
        status="sent" if success else "failed",
        error_message=error or None,
    )
    db.add(log)


def _reminder_timing_hours(business_id: int, db) -> int:
    """Return the advance reminder hours configured for this business."""
    auto = db.query(AutomationSettings).filter(
        AutomationSettings.business_id == business_id
    ).first()
    if auto and auto.reminder_timing_hours:
        return max(1, auto.reminder_timing_hours)
    return 24


def process_reminders():
    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # Gather all businesses with pending reminder bookings (group by business later)
        upcoming_bookings = (
            db.query(Booking)
            .filter(
                Booking.status == "confirmed",
                Booking.reminder_sent == False,
                Booking.start_time >= now + timedelta(hours=1),
                Booking.start_time <= now + timedelta(hours=72),
            )
            .all()
        )

        for booking in upcoming_bookings:
            hours = _reminder_timing_hours(booking.business_id, db)
            window_start = now + timedelta(hours=hours - 1)
            window_end = now + timedelta(hours=hours + 1)
            if not (window_start <= booking.start_time < window_end):
                continue
            _send_reminders(db, booking, f"{hours}h")
            booking.reminder_sent = True
            try:
                db.commit()
            except Exception as e:
                print(f"[reminder] commit failed booking {booking.id}: {e}")
                db.rollback()

        # ── 2h reminders ──────────────────────────────────────────────────────
        w2_start = now + timedelta(hours=1, minutes=45)
        w2_end = now + timedelta(hours=2, minutes=15)

        bookings_2h = (
            db.query(Booking)
            .filter(
                Booking.status == "confirmed",
                Booking.reminder_2h_sent == False,
                Booking.start_time >= w2_start,
                Booking.start_time < w2_end,
            )
            .all()
        )

        for booking in bookings_2h:
            _send_reminders(db, booking, "2h")
            booking.reminder_2h_sent = True
            try:
                db.commit()
            except Exception as e:
                print(f"[reminder] commit failed booking {booking.id}: {e}")
                db.rollback()

    finally:
        db.close()


def _build_wa_reminder_message(booking, service, business, trigger: str, db) -> str:
    """Build the WhatsApp reminder message using the editable template."""
    auto = db.query(AutomationSettings).filter(
        AutomationSettings.business_id == business.id
    ).first()
    template = (auto.whatsapp_reminder_template if auto and auto.whatsapp_reminder_template
                else DEFAULT_WA_REMINDER_TEMPLATE)

    if trigger == "2h":
        timing = "in *2 hours*"
    else:
        timing = "tomorrow"

    return render_template(template, {
        "customer_name": booking.customer_name,
        "service_name": service.name if service else "",
        "salon_name": business.name,
        "timing": timing,
        "time": booking.start_time.strftime("%H:%M"),
        "date": booking.start_time.strftime("%A, %d %B"),
    })


def _send_reminders(db, booking, trigger: str):
    """Send all enabled reminders for a booking and log each."""
    service = db.query(Service).filter(Service.id == booking.service_id).first()
    business = db.query(Business).filter(Business.id == booking.business_id).first()
    if not service or not business:
        return

    # Email
    if business.email_reminders:
        try:
            from .email_service import send_booking_reminder
            send_booking_reminder(booking, service, business)
            _log(db, booking.id, business.id, "email", trigger, True)
        except Exception as e:
            _log(db, booking.id, business.id, "email", trigger, False, str(e))

    # SMS
    if business.sms_reminders:
        if not _under_daily_cap(db, business.id):
            print(f"[reminder] daily SMS/WA cap reached for business {business.id} — skipping SMS")
        else:
            try:
                if trigger == "2h":
                    from .sms_service import send_reminder_sms_2h
                    ok, err = send_reminder_sms_2h(booking, service, business)
                else:
                    from .sms_service import send_reminder_sms
                    ok, err = send_reminder_sms(booking, service, business)
                _log(db, booking.id, business.id, "sms", trigger, ok, err)
                if ok:
                    _report_stripe_usage(business, "sms")
            except Exception as e:
                _log(db, booking.id, business.id, "sms", trigger, False, str(e))

    # WhatsApp (uses editable template)
    if business.whatsapp_reminders:
        if not _under_daily_cap(db, business.id):
            print(f"[reminder] daily SMS/WA cap reached for business {business.id} — skipping WhatsApp")
        else:
            try:
                from .sms_service import send_whatsapp
                if not booking.customer_phone:
                    raise ValueError("no phone")
                message = _build_wa_reminder_message(booking, service, business, trigger, db)
                ok, err = send_whatsapp(booking.customer_phone, message)
                _log(db, booking.id, business.id, "whatsapp", trigger, ok, err)
                if ok:
                    _report_stripe_usage(business, "whatsapp")
            except Exception as e:
                _log(db, booking.id, business.id, "whatsapp", trigger, False, str(e))


def send_booking_confirmations(booking, service, business, db):
    """Instant confirmations sent when a booking is created."""
    if business.email_confirmations:
        try:
            from .email_service import send_booking_confirmation
            send_booking_confirmation(booking, service, business)
            _log(db, booking.id, business.id, "email", "confirmation", True)
        except Exception as e:
            _log(db, booking.id, business.id, "email", "confirmation", False, str(e))

    if business.sms_confirmations:
        if not _under_daily_cap(db, business.id):
            print(f"[confirmation] daily cap reached for business {business.id} — skipping SMS")
        else:
            try:
                from .sms_service import send_confirmation_sms
                ok, err = send_confirmation_sms(booking, service, business)
                _log(db, booking.id, business.id, "sms", "confirmation", ok, err)
                if ok:
                    _report_stripe_usage(business, "sms")
            except Exception as e:
                _log(db, booking.id, business.id, "sms", "confirmation", False, str(e))

    if business.whatsapp_confirmations:
        if not _under_daily_cap(db, business.id):
            print(f"[confirmation] daily cap reached for business {business.id} — skipping WhatsApp")
        else:
            try:
                from .sms_service import send_confirmation_whatsapp
                ok, err = send_confirmation_whatsapp(booking, service, business)
                _log(db, booking.id, business.id, "whatsapp", "confirmation", ok, err)
                if ok:
                    _report_stripe_usage(business, "whatsapp")
            except Exception as e:
                _log(db, booking.id, business.id, "whatsapp", "confirmation", False, str(e))


def start_reminder_scheduler():
    from .automation_worker import process_followups, process_review_requests
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_reminders, "interval", minutes=1, id="reminders")
    scheduler.add_job(process_followups, "interval", minutes=15, id="followups")
    scheduler.add_job(process_review_requests, "interval", minutes=5, id="review_requests")
    scheduler.start()
    return scheduler

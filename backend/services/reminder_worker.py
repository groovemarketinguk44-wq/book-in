"""Background worker — runs every minute, sends 24h reminders."""
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from ..database import SessionLocal
from ..models import Booking, Business, Service


def process_reminders():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        bookings = (
            db.query(Booking)
            .filter(
                Booking.status == "confirmed",
                Booking.reminder_sent == False,
                Booking.start_time >= window_start,
                Booking.start_time < window_end,
            )
            .all()
        )

        for booking in bookings:
            try:
                service = db.query(Service).filter(Service.id == booking.service_id).first()
                business = db.query(Business).filter(Business.id == booking.business_id).first()
                if not service or not business:
                    continue

                if business.email_reminders:
                    from .email_service import send_booking_reminder
                    send_booking_reminder(booking, service, business, db)

                if business.sms_reminders:
                    from .sms_service import send_reminder_sms
                    send_reminder_sms(booking, service, business)

                booking.reminder_sent = True
                db.commit()
            except Exception as e:
                print(f"Reminder failed for booking {booking.id}: {e}")
                db.rollback()
    finally:
        db.close()


def start_reminder_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_reminders, "interval", minutes=1, id="reminders")
    scheduler.start()
    return scheduler

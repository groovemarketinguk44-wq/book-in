"""All emails sent via Book-In's SendGrid account."""
import requests
from ..config import settings


def _send_via_sendgrid(to_email: str, subject: str, html: str):
    if not settings.SENDGRID_API_KEY:
        print(f"[email] SendGrid not configured — skipping email to {to_email}")
        return
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": settings.SENDGRID_FROM_EMAIL, "name": settings.SENDGRID_FROM_NAME},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        },
        timeout=10,
    )
    if resp.status_code >= 400:
        print(f"[email] SendGrid error {resp.status_code}: {resp.text}")


def _build_email_html(
    business_name: str,
    logo_url: str,
    title: str,
    lines: list[str],
) -> str:
    logo_html = (
        f'<img src="{logo_url}" alt="{business_name}" style="height:48px;margin-bottom:16px;">'
        if logo_url
        else ""
    )
    body_lines = "".join(
        f"<p style='margin:8px 0;color:#374151;'>{l}</p>" for l in lines if l
    )
    return f"""<!DOCTYPE html><html><body style="font-family:-apple-system,sans-serif;background:#f9fafb;padding:40px 20px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 1px 3px rgba(0,0,0,.1);">
  {logo_html}
  <h2 style="margin:0 0 24px;font-size:20px;color:#111827;">{title}</h2>
  {body_lines}
  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="font-size:12px;color:#9ca3af;">Sent via <a href="https://book-in.online" style="color:#6b7280;">Book-In</a></p>
</div>
</body></html>"""


def send_booking_confirmation(booking, service, business, db=None):
    if not business.email_confirmations:
        return
    html = _build_email_html(
        business.name,
        business.logo_url,
        "Booking Confirmed",
        [
            f"Hi <strong>{booking.customer_name}</strong>, your booking is confirmed.",
            f"<strong>Service:</strong> {service.name}",
            f"<strong>Date:</strong> {booking.start_time.strftime('%A, %d %B %Y')}",
            f"<strong>Time:</strong> {booking.start_time.strftime('%H:%M')}",
            f"<strong>Duration:</strong> {service.duration_minutes} minutes",
            f"<strong>Price:</strong> £{service.price}",
            f"<strong>Business:</strong> {business.name}",
            business.address or "",
            business.phone or "",
        ],
    )
    _send_via_sendgrid(
        booking.customer_email,
        f"Booking Confirmed — {business.name}",
        html,
    )


def send_booking_reminder(booking, service, business, db=None):
    html = _build_email_html(
        business.name,
        business.logo_url,
        "Reminder: Your Appointment Tomorrow",
        [
            f"Hi <strong>{booking.customer_name}</strong>, just a reminder about your appointment.",
            f"<strong>Service:</strong> {service.name}",
            f"<strong>Date:</strong> {booking.start_time.strftime('%A, %d %B %Y')}",
            f"<strong>Time:</strong> {booking.start_time.strftime('%H:%M')}",
            f"<strong>Business:</strong> {business.name}",
            business.address or "",
            business.phone or "",
        ],
    )
    _send_via_sendgrid(
        booking.customer_email,
        f"Reminder — {business.name} appointment tomorrow",
        html,
    )

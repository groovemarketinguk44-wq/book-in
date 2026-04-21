"""Sends emails via connected Gmail/Outlook account, falling back to SendGrid."""
import base64
import json
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.orm import Session

from ..config import settings


def _refresh_google_token(account, db) -> str:
    import requests
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    data = resp.json()
    account.access_token = data["access_token"]
    account.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
    db.commit()
    return account.access_token


def _refresh_microsoft_token(account, db) -> str:
    import requests
    url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
    resp = requests.post(
        url,
        data={
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
            "scope": "offline_access Mail.Send User.Read",
        },
    )
    data = resp.json()
    account.access_token = data["access_token"]
    account.token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
    db.commit()
    return account.access_token


def _get_valid_token(account, db) -> str:
    if account.token_expiry and datetime.utcnow() >= account.token_expiry - timedelta(minutes=5):
        if account.provider == "gmail":
            return _refresh_google_token(account, db)
        else:
            return _refresh_microsoft_token(account, db)
    return account.access_token


def _send_via_gmail(token: str, from_email: str, to_email: str, subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    import requests
    requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"raw": raw},
    )


def _send_via_outlook(token: str, to_email: str, subject: str, html: str):
    import requests
    requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            }
        },
    )


def _send_via_sendgrid(to_email: str, subject: str, html: str):
    if not settings.SENDGRID_API_KEY:
        return
    import requests
    requests.post(
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
    )


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
    body_lines = "".join(f"<p style='margin:8px 0;color:#374151;'>{l}</p>" for l in lines)
    return f"""
<!DOCTYPE html><html><body style="font-family:-apple-system,sans-serif;background:#f9fafb;padding:40px 20px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:40px;box-shadow:0 1px 3px rgba(0,0,0,.1);">
  {logo_html}
  <h2 style="margin:0 0 24px;font-size:20px;color:#111827;">{title}</h2>
  {body_lines}
  <hr style="margin:32px 0;border:none;border-top:1px solid #e5e7eb;">
  <p style="font-size:12px;color:#9ca3af;">Powered by <strong>Book-In</strong></p>
</div>
</body></html>"""


def send_email(to_email: str, subject: str, html: str, business_id: int, db: Session):
    from ..models import EmailAccount

    account = db.query(EmailAccount).filter(EmailAccount.business_id == business_id).first()
    if account:
        token = _get_valid_token(account, db)
        if account.provider == "gmail":
            _send_via_gmail(token, account.email_address, to_email, subject, html)
        else:
            _send_via_outlook(token, to_email, subject, html)
    else:
        _send_via_sendgrid(to_email, subject, html)


def send_booking_confirmation(booking, service, business, db: Session):
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
    send_email(
        booking.customer_email,
        f"Booking Confirmed — {business.name}",
        html,
        business.id,
        db,
    )


def send_booking_reminder(booking, service, business, db: Session):
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
    send_email(
        booking.customer_email,
        f"Reminder — {business.name} appointment tomorrow",
        html,
        business.id,
        db,
    )

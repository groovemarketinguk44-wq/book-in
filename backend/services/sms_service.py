from ..config import settings


def _twilio_client():
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN]):
        return None
    from twilio.rest import Client
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(to_number: str, message: str) -> tuple[bool, str]:
    if not settings.TWILIO_PHONE_NUMBER:
        print(f"[sms] Twilio not configured — skipping SMS to {to_number}")
        return False, "not configured"
    client = _twilio_client()
    if not client:
        return False, "no client"
    try:
        client.messages.create(body=message, from_=settings.TWILIO_PHONE_NUMBER, to=to_number)
        return True, ""
    except Exception as e:
        print(f"[sms] Send failed: {e}")
        return False, str(e)


def send_whatsapp(to_number: str, message: str) -> tuple[bool, str]:
    if not settings.TWILIO_WHATSAPP_NUMBER:
        print(f"[whatsapp] Twilio WhatsApp not configured — skipping to {to_number}")
        return False, "not configured"
    client = _twilio_client()
    if not client:
        return False, "no client"
    wa_to = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
    try:
        client.messages.create(
            body=message,
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            to=wa_to,
        )
        return True, ""
    except Exception as e:
        print(f"[whatsapp] Send failed: {e}")
        return False, str(e)


def send_reminder_sms(booking, service, business) -> tuple[bool, str]:
    if not booking.customer_phone:
        return False, "no phone"
    message = (
        f"Hi {booking.customer_name}, reminder: your {service.name} appointment "
        f"at {business.name} is tomorrow at {booking.start_time.strftime('%H:%M')}. "
        f"See you then!"
    )
    return send_sms(booking.customer_phone, message)


def send_reminder_sms_2h(booking, service, business) -> tuple[bool, str]:
    if not booking.customer_phone:
        return False, "no phone"
    message = (
        f"Hi {booking.customer_name}, your {service.name} appointment "
        f"at {business.name} is in 2 hours at {booking.start_time.strftime('%H:%M')}. "
        f"See you soon!"
    )
    return send_sms(booking.customer_phone, message)


def send_confirmation_sms(booking, service, business) -> tuple[bool, str]:
    if not booking.customer_phone:
        return False, "no phone"
    message = (
        f"Booking confirmed! {service.name} at {business.name} on "
        f"{booking.start_time.strftime('%d %b at %H:%M')}. "
        f"We look forward to seeing you."
    )
    return send_sms(booking.customer_phone, message)


def send_reminder_whatsapp(booking, service, business) -> tuple[bool, str]:
    if not booking.customer_phone:
        return False, "no phone"
    message = (
        f"Hi {booking.customer_name} 👋\n\n"
        f"Just a reminder that your *{service.name}* appointment at *{business.name}* "
        f"is tomorrow at *{booking.start_time.strftime('%H:%M')}*.\n\n"
        f"See you then!"
    )
    return send_whatsapp(booking.customer_phone, message)


def send_reminder_whatsapp_2h(booking, service, business) -> tuple[bool, str]:
    if not booking.customer_phone:
        return False, "no phone"
    message = (
        f"Hi {booking.customer_name} 👋\n\n"
        f"Your *{service.name}* appointment at *{business.name}* "
        f"is in *2 hours* at *{booking.start_time.strftime('%H:%M')}*.\n\n"
        f"See you soon!"
    )
    return send_whatsapp(booking.customer_phone, message)


def send_confirmation_whatsapp(booking, service, business) -> tuple[bool, str]:
    if not booking.customer_phone:
        return False, "no phone"
    message = (
        f"Booking confirmed! ✅\n\n"
        f"*{service.name}* at *{business.name}*\n"
        f"📅 {booking.start_time.strftime('%A, %d %B at %H:%M')}\n\n"
        f"We look forward to seeing you!"
    )
    return send_whatsapp(booking.customer_phone, message)

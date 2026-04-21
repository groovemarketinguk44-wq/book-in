from ..config import settings


def send_sms(to_number: str, message: str):
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]):
        return

    from twilio.rest import Client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_number,
    )


def send_reminder_sms(booking, service, business):
    if not booking.customer_phone:
        return
    message = (
        f"Hi {booking.customer_name}, reminder: your {service.name} appointment "
        f"at {business.name} is tomorrow at {booking.start_time.strftime('%H:%M')}. "
        f"See you then!"
    )
    send_sms(booking.customer_phone, message)

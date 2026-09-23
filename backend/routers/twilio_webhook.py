"""Twilio voice webhooks — incoming calls, IVR, voicemail, missed call detection."""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import (
    AutomationSettings, Business, CallbackRequest, MissedCall,
    OutboundMessage, Voicemail,
    DEFAULT_MISSED_CALL_MSG, DEFAULT_RECEPTIONIST_GREETING,
)
from ..utils import render_template
from ..config import settings as app_settings

router = APIRouter(prefix="/api/twilio", tags=["twilio"])

_TWIML_CT = "application/xml"


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type=_TWIML_CT)


def _find_business(called: str, db: Session) -> Business | None:
    """Look up business by the Twilio number that was called."""
    if not called:
        return None
    number = called.strip().replace(" ", "")
    return db.query(Business).filter(Business.tracking_phone_number == number).first()


def _get_auto_settings(business_id: int, db: Session) -> AutomationSettings | None:
    return db.query(AutomationSettings).filter(
        AutomationSettings.business_id == business_id
    ).first()


def _booking_link(business: Business) -> str:
    return f"{app_settings.APP_URL}/book/{business.slug}"


# ── Incoming call ─────────────────────────────────────────────────────────────

@router.post("/voice")
async def incoming_call(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    called = form.get("To", "")
    caller = form.get("From", "")
    call_sid = form.get("CallSid", "")

    business = _find_business(called, db)

    if not business:
        return _twiml("<Response><Hangup/></Response>")

    auto = _get_auto_settings(business.id, db)
    receptionist_on = auto.receptionist_enabled if auto else False

    base_url = app_settings.APP_URL

    if receptionist_on:
        greeting = (auto.receptionist_greeting if auto and auto.receptionist_greeting
                    else DEFAULT_RECEPTIONIST_GREETING)
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather numDigits="1" action="{base_url}/api/twilio/voice/gather?biz={business.id}&amp;caller={caller}&amp;sid={call_sid}" timeout="10">
    <Say voice="alice">{greeting}</Say>
  </Gather>
  <Redirect>{base_url}/api/twilio/voice/no-input?biz={business.id}&amp;caller={caller}&amp;sid={call_sid}</Redirect>
</Response>"""
    else:
        # Forward to business phone, detect missed via dial-status callback
        salon_phone = business.phone or ""
        if salon_phone:
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial action="{base_url}/api/twilio/voice/dial-status?biz={business.id}&amp;caller={caller}&amp;sid={call_sid}" timeout="20">
    <Number>{salon_phone}</Number>
  </Dial>
</Response>"""
        else:
            # No forwarding number — just record as missed and hang up
            _record_missed_call(business.id, caller, call_sid, db)
            _send_recovery(business, caller, db)
            xml = "<Response><Hangup/></Response>"

    return _twiml(xml)


# ── Gather (keypress) ─────────────────────────────────────────────────────────

@router.post("/voice/gather")
async def voice_gather(
    request: Request,
    biz: int = 0,
    caller: str = "",
    sid: str = "",
    db: Session = Depends(get_db),
):
    form = await request.form()
    digit = form.get("Digits", "")
    business = db.query(Business).filter(Business.id == biz).first()
    base_url = app_settings.APP_URL

    if not business:
        return _twiml("<Response><Hangup/></Response>")

    missed_call = _record_missed_call(business.id, caller, sid, db)

    if digit == "1":
        _send_recovery(business, caller, db, missed_call_id=missed_call.id)
        missed_call.recovery_sent = True
        missed_call.recovery_sent_at = datetime.utcnow()
        db.commit()
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Your booking link has been sent. We look forward to seeing you!</Say>
  <Hangup/>
</Response>"""

    elif digit == "2":
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Please leave your message after the tone.</Say>
  <Record maxLength="120" action="{base_url}/api/twilio/voice/recording?biz={biz}&amp;caller={caller}&amp;sid={sid}&amp;mc_id={missed_call.id}" transcribe="true" transcribeCallback="{base_url}/api/twilio/voice/transcription?biz={biz}&amp;mc_id={missed_call.id}"/>
</Response>"""

    elif digit == "3":
        cb = CallbackRequest(
            business_id=biz,
            caller_number=caller,
            missed_call_id=missed_call.id,
        )
        db.add(cb)
        db.commit()
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">We've noted your request and will call you back as soon as possible.</Say>
  <Hangup/>
</Response>"""

    else:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Redirect>{base_url}/api/twilio/voice?To={business.tracking_phone_number}</Redirect>
</Response>"""

    return _twiml(xml)


# ── No input fallback ─────────────────────────────────────────────────────────

@router.post("/voice/no-input")
async def voice_no_input(
    request: Request,
    biz: int = 0,
    caller: str = "",
    sid: str = "",
    db: Session = Depends(get_db),
):
    business = db.query(Business).filter(Business.id == biz).first()
    if business:
        missed_call = _record_missed_call(business.id, caller, sid, db)
        _send_recovery(business, caller, db, missed_call_id=missed_call.id)
        missed_call.recovery_sent = True
        missed_call.recovery_sent_at = datetime.utcnow()
        db.commit()
    return _twiml("<Response><Hangup/></Response>")


# ── Dial status (missed call detection when forwarding) ───────────────────────

@router.post("/voice/dial-status")
async def voice_dial_status(
    request: Request,
    biz: int = 0,
    caller: str = "",
    sid: str = "",
    db: Session = Depends(get_db),
):
    form = await request.form()
    dial_status = form.get("DialCallStatus", "")

    business = db.query(Business).filter(Business.id == biz).first()
    if not business:
        return _twiml("<Response><Hangup/></Response>")

    if dial_status in ("no-answer", "busy", "failed", "canceled"):
        missed_call = _record_missed_call(business.id, caller, sid, db)
        auto = _get_auto_settings(business.id, db)
        if auto and auto.missed_call_recovery:
            _send_recovery(business, caller, db, missed_call_id=missed_call.id)
            missed_call.recovery_sent = True
            missed_call.recovery_sent_at = datetime.utcnow()
            db.commit()

    return _twiml("<Response><Hangup/></Response>")


# ── Voicemail recording ready ─────────────────────────────────────────────────

@router.post("/voice/recording")
async def voice_recording(
    request: Request,
    biz: int = 0,
    caller: str = "",
    sid: str = "",
    mc_id: int = 0,
    db: Session = Depends(get_db),
):
    form = await request.form()
    recording_url = form.get("RecordingUrl", "")
    recording_sid = form.get("RecordingSid", "")
    duration = form.get("RecordingDuration", "0")

    try:
        dur_int = int(duration)
    except ValueError:
        dur_int = 0

    vm = Voicemail(
        business_id=biz,
        caller_number=caller,
        recording_url=recording_url,
        recording_sid=recording_sid,
        duration_seconds=dur_int,
        missed_call_id=mc_id or None,
    )
    db.add(vm)
    db.commit()

    return _twiml("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Thank you for your message. We'll get back to you soon.</Say>
  <Hangup/>
</Response>""")


# ── Transcription callback ────────────────────────────────────────────────────

@router.post("/voice/transcription")
async def voice_transcription(
    request: Request,
    biz: int = 0,
    mc_id: int = 0,
    db: Session = Depends(get_db),
):
    form = await request.form()
    recording_sid = form.get("RecordingSid", "")
    transcription_text = form.get("TranscriptionText", "")

    vm = db.query(Voicemail).filter(
        Voicemail.business_id == biz,
        Voicemail.recording_sid == recording_sid,
    ).first()

    if vm and transcription_text:
        vm.transcription = transcription_text
        vm.ai_category = _classify_voicemail(transcription_text)
        db.commit()

    return Response(status_code=200)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _record_missed_call(
    business_id: int, caller: str, call_sid: str, db: Session
) -> MissedCall:
    existing = (
        db.query(MissedCall)
        .filter(MissedCall.call_sid == call_sid, MissedCall.business_id == business_id)
        .first()
    )
    if existing:
        return existing
    mc = MissedCall(
        business_id=business_id,
        caller_number=caller,
        call_sid=call_sid,
    )
    db.add(mc)
    db.commit()
    db.refresh(mc)
    return mc


def _send_recovery(
    business: Business,
    to_number: str,
    db: Session,
    missed_call_id: int | None = None,
):
    from ..services.sms_service import send_sms, send_whatsapp

    auto = _get_auto_settings(business.id, db)
    template = (
        auto.missed_call_message if auto and auto.missed_call_message
        else DEFAULT_MISSED_CALL_MSG
    )
    booking_link = _booking_link(business)
    message = render_template(template, {
        "salon_name": business.name,
        "booking_link": booking_link,
        "phone_number": to_number,
    })

    ok, err = send_whatsapp(to_number, message)
    if not ok:
        ok, err = send_sms(to_number, message)

    channel = "whatsapp" if ok else "sms"
    outbound = OutboundMessage(
        business_id=business.id,
        to_number=to_number,
        channel=channel,
        message_type="missed_call_recovery",
        status="sent" if ok else "failed",
        message_body=message,
        error_message=err if not ok else None,
        reference_id=missed_call_id,
        reference_type="missed_call",
        sent_at=datetime.utcnow() if ok else None,
    )
    db.add(outbound)
    db.commit()


def _classify_voicemail(text: str) -> str:
    """Simple keyword classification — no external AI dependency."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["book", "appointment", "slot", "available"]):
        return "booking"
    if any(w in text_lower for w in ["price", "cost", "how much", "charge"]):
        return "pricing"
    if any(w in text_lower for w in ["cancel", "reschedule", "change"]):
        return "cancellation"
    if any(w in text_lower for w in ["complain", "unhappy", "upset", "terrible", "awful"]):
        return "complaint"
    return "general"

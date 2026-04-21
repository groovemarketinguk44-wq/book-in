"""OAuth flows for Gmail and Outlook email account connection."""
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, EmailAccount

router = APIRouter(prefix="/api/email", tags=["email"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = "https://www.googleapis.com/auth/gmail.send email profile"

MS_AUTH_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
MS_SCOPES = "offline_access Mail.Send User.Read"


# ── Google ─────────────────────────────────────────────────────────────────

@router.get("/google/connect")
def google_connect(
    request: Request,
    token: str = None,
    business: Business = Depends(get_current_business),
):
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": str(business.id),
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user_info = userinfo_resp.json()

    business_id = int(state)
    expiry = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))

    existing = db.query(EmailAccount).filter(EmailAccount.business_id == business_id).first()
    if existing:
        existing.provider = "gmail"
        existing.email_address = user_info["email"]
        existing.access_token = tokens["access_token"]
        existing.refresh_token = tokens.get("refresh_token", existing.refresh_token)
        existing.token_expiry = expiry
    else:
        account = EmailAccount(
            business_id=business_id,
            provider="gmail",
            email_address=user_info["email"],
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_expiry=expiry,
        )
        db.add(account)

    db.commit()
    return RedirectResponse(f"{settings.APP_URL}/settings?email=connected")


# ── Microsoft ─────────────────────────────────────────────────────────────────

@router.get("/microsoft/connect")
def microsoft_connect(business: Business = Depends(get_current_business)):
    url = MS_AUTH_URL.format(tenant=settings.MICROSOFT_TENANT_ID)
    params = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
        "response_type": "code",
        "scope": MS_SCOPES,
        "state": str(business.id),
    }
    return RedirectResponse(f"{url}?{urlencode(params)}")


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    token_url = MS_TOKEN_URL.format(tenant=settings.MICROSOFT_TENANT_ID)
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            token_url,
            data={
                "code": code,
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
                "grant_type": "authorization_code",
                "scope": MS_SCOPES,
            },
        )
        tokens = token_resp.json()

        me_resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me = me_resp.json()

    business_id = int(state)
    expiry = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    email_address = me.get("mail") or me.get("userPrincipalName", "")

    existing = db.query(EmailAccount).filter(EmailAccount.business_id == business_id).first()
    if existing:
        existing.provider = "outlook"
        existing.email_address = email_address
        existing.access_token = tokens["access_token"]
        existing.refresh_token = tokens.get("refresh_token", existing.refresh_token)
        existing.token_expiry = expiry
    else:
        account = EmailAccount(
            business_id=business_id,
            provider="outlook",
            email_address=email_address,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_expiry=expiry,
        )
        db.add(account)

    db.commit()
    return RedirectResponse(f"{settings.APP_URL}/settings?email=connected")

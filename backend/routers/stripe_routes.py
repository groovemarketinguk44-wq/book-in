import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


@router.post("/create-checkout")
def create_checkout(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    if not business.stripe_customer_id:
        customer = stripe.Customer.create(email=business.email, name=business.name)
        business.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=business.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        mode="subscription",
        subscription_data={"trial_period_days": settings.STRIPE_TRIAL_DAYS},
        success_url=f"{settings.APP_URL}/dashboard?checkout=success",
        cancel_url=f"{settings.APP_URL}/settings?checkout=cancelled",
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(body, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        customer_id = data.get("customer")
        sub_id = data.get("subscription")
        if customer_id and sub_id:
            biz = db.query(Business).filter(Business.stripe_customer_id == customer_id).first()
            if biz:
                biz.stripe_subscription_id = sub_id
                biz.subscription_status = "active"
                db.commit()

    elif event["type"] == "customer.subscription.updated":
        sub = stripe.Subscription.retrieve(data["id"])
        biz = db.query(Business).filter(
            Business.stripe_subscription_id == data["id"]
        ).first()
        if biz:
            status_map = {
                "active": "active",
                "trialing": "trial",
                "past_due": "past_due",
                "canceled": "cancelled",
                "unpaid": "expired",
            }
            biz.subscription_status = status_map.get(data["status"], data["status"])
            db.commit()

    elif event["type"] == "customer.subscription.deleted":
        biz = db.query(Business).filter(
            Business.stripe_subscription_id == data["id"]
        ).first()
        if biz:
            biz.subscription_status = "cancelled"
            db.commit()

    return {"ok": True}

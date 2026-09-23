import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


def _pro_price_id() -> str:
    return settings.STRIPE_PRO_PRICE_ID or settings.STRIPE_PRICE_ID


def _ultra_price_id() -> str:
    return settings.STRIPE_ULTRA_PRICE_ID


@router.post("/create-checkout")
def create_checkout(
    plan: str = "pro",
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    plan = plan.lower()
    if plan not in ("pro", "ultra"):
        plan = "pro"

    if plan == "ultra":
        price_id = _ultra_price_id()
        if not price_id:
            raise HTTPException(status_code=503, detail="Ultra plan not configured")
    else:
        price_id = _pro_price_id()
        if not price_id:
            raise HTTPException(status_code=503, detail="Pro plan not configured")

    if not business.stripe_customer_id:
        customer = stripe.Customer.create(email=business.email, name=business.name)
        business.stripe_customer_id = customer.id
        db.commit()

    line_items = [{"price": price_id, "quantity": 1}]

    # Pro plan can add SMS/WhatsApp metered add-ons
    if plan == "pro":
        if settings.STRIPE_WHATSAPP_PRICE_ID:
            line_items.append({"price": settings.STRIPE_WHATSAPP_PRICE_ID})
        if settings.STRIPE_SMS_PRICE_ID:
            line_items.append({"price": settings.STRIPE_SMS_PRICE_ID})

    # Apply 50% off first month coupon if configured
    discounts = []
    if settings.STRIPE_FIRST_MONTH_COUPON:
        discounts = [{"coupon": settings.STRIPE_FIRST_MONTH_COUPON}]

    session_kwargs = dict(
        customer=business.stripe_customer_id,
        payment_method_types=["card"],
        line_items=line_items,
        mode="subscription",
        subscription_data={"metadata": {"plan": plan}},
        metadata={"plan": plan},
        success_url=f"{settings.APP_URL}/dashboard?checkout=success",
        cancel_url=f"{settings.APP_URL}/dashboard?checkout=cancelled",
    )
    if discounts:
        session_kwargs["discounts"] = discounts

    session = stripe.checkout.Session.create(**session_kwargs)
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
        chosen_plan = data.get("metadata", {}).get("plan", "pro")
        if customer_id and sub_id:
            biz = db.query(Business).filter(Business.stripe_customer_id == customer_id).first()
            if biz:
                biz.stripe_subscription_id = sub_id
                biz.subscription_status = "active"
                biz.plan = chosen_plan
                try:
                    sub = stripe.Subscription.retrieve(sub_id)
                    for item in sub["items"]["data"]:
                        price_id = item["price"]["id"]
                        if price_id == settings.STRIPE_WHATSAPP_PRICE_ID:
                            biz.stripe_whatsapp_item_id = item["id"]
                        elif price_id == settings.STRIPE_SMS_PRICE_ID:
                            biz.stripe_sms_item_id = item["id"]
                except Exception as e:
                    print(f"[webhook] failed to capture item IDs: {e}")
                db.commit()

    elif event["type"] == "customer.subscription.updated":
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
            # Update plan from metadata if present
            meta_plan = data.get("metadata", {}).get("plan")
            if meta_plan in ("pro", "ultra"):
                biz.plan = meta_plan
            db.commit()

    elif event["type"] == "customer.subscription.deleted":
        biz = db.query(Business).filter(
            Business.stripe_subscription_id == data["id"]
        ).first()
        if biz:
            biz.subscription_status = "cancelled"
            db.commit()

    return {"ok": True}


@router.post("/portal")
def billing_portal(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    if not business.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=business.stripe_customer_id,
        return_url=f"{settings.APP_URL}/dashboard?tab=settings",
    )
    return {"url": session.url}

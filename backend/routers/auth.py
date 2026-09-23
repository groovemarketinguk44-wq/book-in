from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Business, User
from ..schemas import LoginRequest, SignupRequest, TokenResponse
from ..auth import create_access_token, hash_password, verify_password
from ..utils import unique_slug
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    slug = unique_slug(body.business_name, db)
    trial_ends = datetime.utcnow() + timedelta(days=settings.STRIPE_TRIAL_DAYS)

    business = Business(
        name=body.business_name,
        slug=slug,
        email=body.email,
        subscription_status="trial",
        trial_ends_at=trial_ends,
    )
    db.add(business)
    db.flush()

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        business_id=business.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "business_id": business.id})
    return {"access_token": token}


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "sub": user.id,
        "business_id": user.business_id,
        "is_platform_admin": bool(user.is_platform_admin),
    })
    return {"access_token": token, "is_platform_admin": bool(user.is_platform_admin)}

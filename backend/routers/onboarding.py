from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_business, get_current_user
from ..models import Business, Category, Service, User
from ..schemas import CategoryCreate, OnboardingStep1, ServiceCreate

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.post("/step1")
def step1(
    body: OnboardingStep1,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    business.name = body.name
    if body.address:
        business.address = body.address
    if body.phone:
        business.phone = body.phone
    db.commit()
    return {"ok": True}


@router.post("/step2")
def step2(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    category = Category(
        name=body.name,
        image_url=body.image_url,
        business_id=business.id,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return {"id": category.id, "name": category.name}


@router.post("/step3")
def step3(
    body: ServiceCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    service = Service(
        name=body.name,
        description=body.description,
        price=body.price,
        duration_minutes=body.duration_minutes,
        image_url=body.image_url,
        category_id=body.category_id,
        business_id=business.id,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"id": service.id, "name": service.name}


@router.post("/complete")
def complete(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    business.onboarding_complete = True
    db.commit()
    return {"ok": True}

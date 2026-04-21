from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, Service
from ..schemas import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("", response_model=List[ServiceResponse])
def list_services(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    return (
        db.query(Service)
        .filter(Service.business_id == business.id)
        .order_by(Service.name)
        .all()
    )


@router.post("", response_model=ServiceResponse, status_code=201)
def create_service(
    body: ServiceCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    svc = Service(
        name=body.name,
        description=body.description,
        price=body.price,
        duration_minutes=body.duration_minutes,
        image_url=body.image_url,
        category_id=body.category_id,
        business_id=business.id,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.put("/{svc_id}", response_model=ServiceResponse)
def update_service(
    svc_id: int,
    body: ServiceUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    svc = db.query(Service).filter(
        Service.id == svc_id, Service.business_id == business.id
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(svc, field, value)
    db.commit()
    db.refresh(svc)
    return svc


@router.delete("/{svc_id}", status_code=204)
def delete_service(
    svc_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    svc = db.query(Service).filter(
        Service.id == svc_id, Service.business_id == business.id
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    db.delete(svc)
    db.commit()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..dependencies import get_current_business
from ..models import Business, Category
from ..schemas import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=List[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    return db.query(Category).filter(Category.business_id == business.id).all()


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    cat = Category(name=body.name, image_url=body.image_url, business_id=business.id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{cat_id}", response_model=CategoryResponse)
def update_category(
    cat_id: int,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    cat = db.query(Category).filter(
        Category.id == cat_id, Category.business_id == business.id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if body.name is not None:
        cat.name = body.name
    if body.image_url is not None:
        cat.image_url = body.image_url
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{cat_id}", status_code=204)
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    cat = db.query(Category).filter(
        Category.id == cat_id, Category.business_id == business.id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()

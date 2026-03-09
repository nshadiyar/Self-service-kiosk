from fastapi import APIRouter, Depends, Query

from app.dependencies import get_db
from app.schemas.catalog import CategoryResponse, ProductResponse
from app.services.catalog_service import CatalogService
from app.core.security import require_any_user, get_current_user_dep

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    categories = await svc.list_categories()
    return [CategoryResponse.model_validate(c) for c in categories]


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    category = await svc.get_category(category_id)
    return CategoryResponse.model_validate(category)


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    category_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    facility_id = current_user.facility_id if current_user.role.value == "PRISON_ADMIN" else None
    products = await svc.list_products(category_id=category_id, facility_id=facility_id, skip=skip, limit=limit)
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    product = await svc.get_product(product_id)
    return ProductResponse.model_validate(product)

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_db
from app.schemas.catalog import (
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductStockUpdate,
    ProductUpdate,
    VendorDetailResponse,
    VendorResponse,
)
from app.services.catalog_service import CatalogService
from app.services.audit_service import AuditService
from app.core.security import get_current_user_dep, require_super_admin

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _to_product_response(product) -> ProductResponse:
    payload = ProductResponse.model_validate(product).model_dump()
    payload["category_name"] = product.category.name if product.category else None
    payload["vendor_name"] = product.vendor.name if product.vendor else None
    payload["facility_name"] = product.facility.name if product.facility else None
    return ProductResponse(**payload)


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
    category_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    category = await svc.get_category(category_id)
    return CategoryResponse.model_validate(category)


@router.get("/vendors", response_model=list[VendorResponse])
async def list_vendors(
    category_id: UUID | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    vendors = await svc.list_vendors(category_id=category_id)
    return [VendorResponse.model_validate(v) for v in vendors]


@router.get("/vendors/{vendor_id}", response_model=VendorDetailResponse)
async def get_vendor(
    vendor_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    vendor = await svc.get_vendor(vendor_id)
    return VendorDetailResponse.model_validate(vendor)


@router.get("/products", response_model=list[ProductResponse])
async def list_products(
    category_id: UUID | None = Query(None),
    facility_id: UUID | None = Query(None),
    vendor_id: UUID | None = Query(None),
    name: str | None = Query(None, description="Поиск по наименованию товара"),
    is_active: bool | None = Query(True),
    sort: str = Query("asc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    facility_filter = facility_id
    if current_user.role.value in {"PRISON_ADMIN", "INMATE"}:
        facility_filter = current_user.facility_id
    products = await svc.list_products(
        category_id=category_id,
        facility_id=facility_filter,
        vendor_id=vendor_id,
        name=name,
        is_active=is_active,
        sort=sort,
        skip=skip,
        limit=limit,
    )
    return [_to_product_response(p) for p in products]


@router.get("/products/low-stock", response_model=list[ProductResponse])
async def list_low_stock_products(
    threshold: int = Query(10, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    facility_id = current_user.facility_id if current_user.role.value == "PRISON_ADMIN" else None
    products = await svc.list_low_stock_products(threshold=threshold, facility_id=facility_id, limit=limit)
    return [_to_product_response(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = CatalogService(db)
    product = await svc.get_product(product_id)
    return _to_product_response(product)


@router.post("/products", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = CatalogService(db)
    product = await svc.create_product(data)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="CREATE_PRODUCT",
        entity_type="product",
        entity_id=str(product.id),
        summary=f"Создан товар {product.name}",
        payload_after=_to_product_response(product).model_dump(mode="json"),
    )
    return _to_product_response(product)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = CatalogService(db)
    before = await svc.get_product(product_id)
    before_payload = _to_product_response(before).model_dump(mode="json")
    product = await svc.update_product(product_id, data)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="UPDATE_PRODUCT",
        entity_type="product",
        entity_id=str(product.id),
        summary=f"Обновлен товар {product.name}",
        payload_before=before_payload,
        payload_after=_to_product_response(product).model_dump(mode="json"),
    )
    return _to_product_response(product)


@router.delete("/products/{product_id}", response_model=ProductResponse)
async def deactivate_product(
    product_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = CatalogService(db)
    before = await svc.get_product(product_id)
    before_payload = _to_product_response(before).model_dump(mode="json")
    product = await svc.deactivate_product(product_id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="DEACTIVATE_PRODUCT",
        entity_type="product",
        entity_id=str(product.id),
        summary=f"Деактивирован товар {product.name}",
        payload_before=before_payload,
        payload_after=_to_product_response(product).model_dump(mode="json"),
    )
    return _to_product_response(product)


@router.patch("/products/{product_id}/stock", response_model=ProductResponse)
async def update_product_stock(
    product_id: UUID,
    data: ProductStockUpdate,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = CatalogService(db)
    before = await svc.get_product(product_id)
    before_payload = _to_product_response(before).model_dump(mode="json")
    product = await svc.update_product_stock(product_id, data.stock_quantity)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="UPDATE_PRODUCT_STOCK",
        entity_type="product",
        entity_id=str(product.id),
        summary=f"Изменен остаток товара {product.name}",
        payload_before=before_payload,
        payload_after=_to_product_response(product).model_dump(mode="json") | {"reason": data.reason},
    )
    return _to_product_response(product)

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.dependencies import get_db
from app.schemas.catalog import (
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductStockUpdate,
    ProductUpdate,
    VendorCreate,
    VendorDetailResponse,
    VendorResponse,
    VendorUpdate,
)
from app.services.catalog_service import CatalogService
from app.services.audit_service import AuditService
from app.services.storage_service import MinioStorageService
from app.core.enums import UserRole
from app.core.exceptions import AuthorizationError, ValidationError
from app.core.security import get_current_user_dep, require_catalog_manager

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _to_product_response(product) -> ProductResponse:
    payload = ProductResponse.model_validate(product).model_dump()
    payload["category_name"] = product.category.name if product.category else None
    payload["vendor_name"] = product.vendor.name if product.vendor else None
    payload["facility_name"] = product.facility.name if product.facility else None
    return ProductResponse(**payload)


def _to_vendor_response(vendor) -> VendorResponse:
    return VendorResponse.model_validate(vendor)


def _apply_catalog_write_scope(current_user, data):
    if current_user.role != UserRole.WAREHOUSE_MANAGER:
        return data
    if current_user.facility_id is None:
        return data
    if getattr(data, "facility_id", None) is not None and data.facility_id != current_user.facility_id:
        raise AuthorizationError("Начальник склада может управлять товарами только своего учреждения")
    if getattr(data, "facility_id", None) is None:
        return data.model_copy(update={"facility_id": current_user.facility_id})
    return data


def _ensure_existing_product_write_scope(current_user, product, data=None) -> None:
    if current_user.role != UserRole.WAREHOUSE_MANAGER or current_user.facility_id is None:
        return
    if product.facility_id not in {None, current_user.facility_id}:
        raise AuthorizationError("Доступ запрещен")
    if data is not None and "facility_id" in getattr(data, "model_fields_set", set()):
        raise AuthorizationError("Начальник склада не может менять привязку товара к учреждению")


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


@router.post("/vendors", response_model=VendorResponse)
async def create_vendor(
    code: str = Form(...),
    name: str = Form(...),
    category_id: UUID | None = Form(None),
    sort_order: int = Form(0),
    logo_url: str | None = Form(None),
    file: UploadFile | None = File(None),
    db=Depends(get_db),
    current_user=Depends(require_catalog_manager),
):
    svc = CatalogService(db)
    uploaded_logo_url = logo_url
    if file is not None:
        if not file.filename:
            raise ValidationError("Необходимо указать имя файла логотипа")
        if file.content_type and not file.content_type.startswith("image/"):
            raise ValidationError("Поддерживается загрузка только изображений")
        file_bytes = await file.read()
        storage = MinioStorageService()
        upload_result = storage.upload_vendor_image(
            uploader_id=current_user.id,
            file_bytes=file_bytes,
            content_type=file.content_type,
            filename=file.filename,
        )
        uploaded_logo_url = upload_result["url"]

    data = VendorCreate.model_validate(
        {
            "code": code,
            "name": name,
            "logo_url": uploaded_logo_url,
            "category_id": category_id,
            "sort_order": sort_order,
        }
    )
    vendor = await svc.create_vendor(data)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="CREATE_VENDOR",
        entity_type="vendor",
        entity_id=str(vendor.id),
        summary=f"Создан поставщик {vendor.name}",
        payload_after=_to_vendor_response(vendor).model_dump(mode="json"),
    )
    return _to_vendor_response(vendor)


@router.patch("/vendors/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: UUID,
    code: str | None = Form(None),
    name: str | None = Form(None),
    category_id: UUID | None = Form(None),
    sort_order: int | None = Form(None),
    logo_url: str | None = Form(None),
    is_active: bool | None = Form(None),
    file: UploadFile | None = File(None),
    db=Depends(get_db),
    current_user=Depends(require_catalog_manager),
):
    svc = CatalogService(db)
    before = await svc.get_vendor(vendor_id)
    uploaded_logo_url = logo_url
    if file is not None:
        if not file.filename:
            raise ValidationError("Необходимо указать имя файла логотипа")
        if file.content_type and not file.content_type.startswith("image/"):
            raise ValidationError("Поддерживается загрузка только изображений")
        file_bytes = await file.read()
        storage = MinioStorageService()
        upload_result = storage.upload_vendor_image(
            uploader_id=current_user.id,
            file_bytes=file_bytes,
            content_type=file.content_type,
            filename=file.filename,
        )
        uploaded_logo_url = upload_result["url"]

    data = VendorUpdate.model_validate(
        {
            "code": code,
            "name": name,
            "logo_url": uploaded_logo_url,
            "category_id": category_id,
            "sort_order": sort_order,
            "is_active": is_active,
        }
    )
    before_payload = _to_vendor_response(before).model_dump(mode="json")
    vendor = await svc.update_vendor(vendor_id, data)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="UPDATE_VENDOR",
        entity_type="vendor",
        entity_id=str(vendor.id),
        summary=f"Обновлен поставщик {vendor.name}",
        payload_before=before_payload,
        payload_after=_to_vendor_response(vendor).model_dump(mode="json"),
    )
    return _to_vendor_response(vendor)


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
    name: str = Form(...),
    description: str | None = Form(None),
    category_id: UUID = Form(...),
    facility_id: UUID | None = Form(None),
    vendor_id: UUID | None = Form(None),
    price: Decimal = Form(...),
    stock_quantity: int = Form(0),
    image_url: str | None = Form(None),
    file: UploadFile | None = File(None),
    db=Depends(get_db),
    current_user=Depends(require_catalog_manager),
):
    svc = CatalogService(db)
    uploaded_image_url = image_url
    if file is not None:
        if not file.filename:
            raise ValidationError("Необходимо указать имя файла изображения")
        if file.content_type and not file.content_type.startswith("image/"):
            raise ValidationError("Поддерживается загрузка только изображений")
        file_bytes = await file.read()
        storage = MinioStorageService()
        upload_result = storage.upload_product_image(
            uploader_id=current_user.id,
            file_bytes=file_bytes,
            content_type=file.content_type,
            filename=file.filename,
        )
        uploaded_image_url = upload_result["url"]

    data = ProductCreate.model_validate(
        {
            "name": name,
            "description": description,
            "category_id": category_id,
            "facility_id": facility_id,
            "vendor_id": vendor_id,
            "price": price,
            "stock_quantity": stock_quantity,
            "image_url": uploaded_image_url,
        }
    )
    data = _apply_catalog_write_scope(current_user, data)
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
    current_user=Depends(require_catalog_manager),
):
    svc = CatalogService(db)
    before = await svc.get_product(product_id)
    _ensure_existing_product_write_scope(current_user, before, data)
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
    current_user=Depends(require_catalog_manager),
):
    svc = CatalogService(db)
    before = await svc.get_product(product_id)
    _ensure_existing_product_write_scope(current_user, before)
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
    current_user=Depends(require_catalog_manager),
):
    svc = CatalogService(db)
    before = await svc.get_product(product_id)
    _ensure_existing_product_write_scope(current_user, before)
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

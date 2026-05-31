from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.category import Category
from app.models.facility import Facility
from app.models.product import Product
from app.models.vendor import Vendor
from app.schemas.catalog import ProductCreate, ProductUpdate, VendorCreate, VendorUpdate


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_categories(self, facility_id: UUID | None = None) -> list[Category]:
        q = select(Category).where(Category.is_active == True).order_by(Category.sort_order)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_category(self, category_id: UUID) -> Category:
        result = await self.db.execute(select(Category).where(Category.id == category_id))
        c = result.scalar_one_or_none()
        if not c:
            raise NotFoundError("Категория не найдена")
        return c

    async def list_products(
        self,
        category_id: UUID | None = None,
        facility_id: UUID | None = None,
        vendor_id: UUID | None = None,
        name: str | None = None,
        is_active: bool | None = True,
        sort: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        q = select(Product).options(
            selectinload(Product.category),
            selectinload(Product.vendor),
            selectinload(Product.facility),
        )
        if is_active is not None:
            q = q.where(Product.is_active == is_active)
        if category_id is not None:
            q = q.where(Product.category_id == category_id)
        if facility_id is not None:
            q = q.where((Product.facility_id == facility_id) | (Product.facility_id.is_(None)))
        if vendor_id is not None:
            q = q.where(Product.vendor_id == vendor_id)
        if name is not None and name.strip():
            q = q.where(Product.name.ilike(f"%{name.strip()}%"))
        q = q.order_by(Product.price.asc() if sort == "asc" else Product.price.desc())
        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def list_low_stock_products(
        self,
        *,
        threshold: int = 10,
        facility_id: UUID | None = None,
        limit: int = 50,
    ) -> list[Product]:
        q = (
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.vendor),
                selectinload(Product.facility),
            )
            .where(Product.is_active == True, Product.stock_quantity <= threshold)
            .order_by(Product.stock_quantity.asc(), Product.name.asc())
            .limit(limit)
        )
        if facility_id is not None:
            q = q.where((Product.facility_id == facility_id) | (Product.facility_id.is_(None)))
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def list_vendors(
        self,
        category_id: UUID | None = None,
        is_active: bool | None = True,
    ) -> list[Vendor]:
        q = select(Vendor).order_by(Vendor.sort_order)
        if is_active is not None:
            q = q.where(Vendor.is_active == is_active)
        if category_id is not None:
            q = q.where(Vendor.category_id == category_id)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_vendor(self, vendor_id: UUID) -> Vendor:
        result = await self.db.execute(
            select(Vendor)
            .options(selectinload(Vendor.products))
            .where(Vendor.id == vendor_id)
        )
        v = result.scalar_one_or_none()
        if not v:
            raise NotFoundError("Поставщик не найден")
        return v

    async def create_vendor(self, data: VendorCreate) -> Vendor:
        await self._validate_vendor_refs(category_id=data.category_id)
        existing_code = await self.db.scalar(select(Vendor.id).where(Vendor.code == data.code))
        if existing_code is not None:
            raise ConflictError("Поставщик с таким кодом уже существует")
        vendor = Vendor(
            code=data.code,
            name=data.name,
            logo_url=data.logo_url,
            category_id=data.category_id,
            sort_order=data.sort_order,
            is_active=True,
        )
        self.db.add(vendor)
        await self.db.flush()
        await self.db.refresh(vendor)
        return await self.get_vendor(vendor.id)

    async def update_vendor(self, vendor_id: UUID, data: VendorUpdate) -> Vendor:
        vendor = await self.get_vendor(vendor_id)
        await self._validate_vendor_refs(category_id=data.category_id)
        if data.code is not None:
            existing_code = await self.db.scalar(select(Vendor.id).where(Vendor.code == data.code))
            if existing_code is not None and existing_code != vendor.id:
                raise ConflictError("Поставщик с таким кодом уже существует")
        for field in ("code", "name", "logo_url", "category_id", "sort_order", "is_active"):
            value = getattr(data, field)
            if value is not None:
                setattr(vendor, field, value)
        await self.db.flush()
        await self.db.refresh(vendor)
        return await self.get_vendor(vendor.id)

    async def deactivate_vendor(self, vendor_id: UUID) -> Vendor:
        vendor = await self.get_vendor(vendor_id)
        vendor.is_active = False
        await self.db.flush()
        await self.db.refresh(vendor)
        return await self.get_vendor(vendor.id)

    async def get_product(self, product_id: UUID) -> Product:
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.vendor),
                selectinload(Product.facility),
            )
            .where(Product.id == product_id)
        )
        p = result.scalar_one_or_none()
        if not p:
            raise NotFoundError("Товар не найден")
        return p

    async def create_product(self, data: ProductCreate) -> Product:
        await self._validate_product_refs(
            category_id=data.category_id,
            vendor_id=data.vendor_id,
            facility_id=data.facility_id,
        )
        product = Product(
            name=data.name,
            description=data.description,
            category_id=data.category_id,
            facility_id=data.facility_id,
            vendor_id=data.vendor_id,
            price=data.price,
            stock_quantity=data.stock_quantity,
            image_url=data.image_url,
            is_active=True,
        )
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)
        return await self.get_product(product.id)

    async def update_product(self, product_id: UUID, data: ProductUpdate) -> Product:
        product = await self.get_product(product_id)
        await self._validate_product_refs(
            category_id=data.category_id,
            vendor_id=data.vendor_id,
            facility_id=data.facility_id,
        )
        for field in (
            "name",
            "description",
            "category_id",
            "facility_id",
            "vendor_id",
            "price",
            "stock_quantity",
            "image_url",
            "is_active",
        ):
            value = getattr(data, field)
            if value is not None:
                setattr(product, field, value)
        await self.db.flush()
        await self.db.refresh(product)
        return await self.get_product(product.id)

    async def deactivate_product(self, product_id: UUID) -> Product:
        product = await self.get_product(product_id)
        product.is_active = False
        await self.db.flush()
        await self.db.refresh(product)
        return await self.get_product(product.id)

    async def update_product_stock(self, product_id: UUID, stock_quantity: int) -> Product:
        product = await self.get_product(product_id)
        product.stock_quantity = stock_quantity
        await self.db.flush()
        await self.db.refresh(product)
        return await self.get_product(product.id)

    async def _validate_product_refs(
        self,
        *,
        category_id: UUID | None,
        vendor_id: UUID | None,
        facility_id: UUID | None,
    ) -> None:
        if category_id is not None:
            category = await self.db.scalar(select(Category.id).where(Category.id == category_id))
            if category is None:
                raise ValidationError("Категория не найдена")
        if vendor_id is not None:
            vendor = await self.db.scalar(select(Vendor.id).where(Vendor.id == vendor_id))
            if vendor is None:
                raise ValidationError("Поставщик не найден")
        if facility_id is not None:
            facility = await self.db.scalar(select(Facility.id).where(Facility.id == facility_id))
            if facility is None:
                raise ValidationError("Учреждение не найдено")

    async def _validate_vendor_refs(
        self,
        *,
        category_id: UUID | None,
    ) -> None:
        if category_id is not None:
            category = await self.db.scalar(select(Category.id).where(Category.id == category_id))
            if category is None:
                raise ValidationError("Категория не найдена")

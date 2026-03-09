from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.category import Category
from app.models.product import Product


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_categories(self, facility_id: int | None = None) -> list[Category]:
        q = select(Category).where(Category.is_active == True).order_by(Category.sort_order)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_category(self, category_id: int) -> Category:
        result = await self.db.execute(select(Category).where(Category.id == category_id))
        c = result.scalar_one_or_none()
        if not c:
            raise NotFoundError("Category not found")
        return c

    async def list_products(
        self,
        category_id: int | None = None,
        facility_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        q = select(Product).where(Product.is_active == True)
        if category_id is not None:
            q = q.where(Product.category_id == category_id)
        if facility_id is not None:
            q = q.where((Product.facility_id == facility_id) | (Product.facility_id.is_(None)))
        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_product(self, product_id: int) -> Product:
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        p = result.scalar_one_or_none()
        if not p:
            raise NotFoundError("Product not found")
        return p

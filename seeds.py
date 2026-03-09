"""Seed database with initial data."""
import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import User, Facility, Wallet, Category, Product
from app.core.security import get_password_hash
from app.core.enums import UserRole, SecurityRegime


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(User).where(User.email == "admin@bromart.kz"))
        if result.scalar_one_or_none():
            print("Already seeded. Skipping.")
            return

        # Facility
        facility = Facility(
            name="Prison Facility #1",
            code="FAC-001",
            address="Kazakhstan",
            security_regime=SecurityRegime.GENERAL.value,
        )
        db.add(facility)
        await db.flush()

        # Super Admin
        admin = User(
            email="admin@bromart.kz",
            hashed_password=get_password_hash("Admin123!"),
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            facility_id=None,
        )
        db.add(admin)
        await db.flush()

        # Prison Admin
        prison_admin = User(
            email="admin@facility.kz",
            hashed_password=get_password_hash("Admin123!"),
            full_name="Prison Admin",
            role=UserRole.PRISON_ADMIN,
            facility_id=facility.id,
        )
        db.add(prison_admin)
        await db.flush()

        # Inmates
        inmates = [
            ("inmate1@test.kz", "Inmate One"),
            ("inmate2@test.kz", "Inmate Two"),
            ("inmate3@test.kz", "Inmate Three"),
        ]
        for i, (email, name) in enumerate(inmates):
            user = User(
                email=email,
                hashed_password=get_password_hash("Inmate123!"),
                full_name=name,
                role=UserRole.INMATE,
                facility_id=facility.id,
            )
            db.add(user)
            await db.flush()
            wallet = Wallet(user_id=user.id, balance=10000, monthly_spent=0)
            db.add(wallet)

        # Categories
        categories = [
            ("Food", "Food and snacks", 1),
            ("Hygiene", "Personal hygiene", 2),
            ("Stationery", "Writing materials", 3),
        ]
        for name, desc, order in categories:
            cat = Category(name=name, description=desc, sort_order=order)
            db.add(cat)
            await db.flush()

        # Products
        result = await db.execute(select(Category).order_by(Category.sort_order))
        cats = list(result.scalars().all())
        food_id, hygiene_id, stationery_id = cats[0].id, cats[1].id, cats[2].id
        products = [
            ("Bread", 50, 100, food_id),
            ("Water", 30, 200, food_id),
            ("Soap", 150, 50, hygiene_id),
            ("Toothpaste", 200, 30, hygiene_id),
            ("Notebook", 80, 40, stationery_id),
            ("Pen", 20, 100, stationery_id),
        ]
        for name, price, stock, cat_id in products:
            p = Product(
                name=name,
                price=price,
                stock_quantity=stock,
                category_id=cat_id,
                facility_id=None,
            )
            db.add(p)

        await db.commit()
        print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())

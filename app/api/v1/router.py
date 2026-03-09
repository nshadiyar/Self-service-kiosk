from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, facilities, catalog, orders, wallet

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(facilities.router)
router.include_router(catalog.router)
router.include_router(orders.router)
router.include_router(wallet.router)

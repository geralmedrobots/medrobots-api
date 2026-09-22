from fastapi import APIRouter

from app.api.v1 import contacts, health

router = APIRouter()
router.include_router(health.router)
router.include_router(contacts.router)

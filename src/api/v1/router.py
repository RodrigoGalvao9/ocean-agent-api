from fastapi import APIRouter

from src.api.v1.routes.chat import router as chat_router
from src.api.v1.routes.conversations import router as conversations_router

router = APIRouter(prefix="/api/v1")
router.include_router(chat_router)
router.include_router(conversations_router)

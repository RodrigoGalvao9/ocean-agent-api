from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import get_settings
from src.security.client import SESSION_COOKIE, establish_session


class ConversationSessionMiddleware(BaseHTTPMiddleware):
    """Emite uma sessão HttpOnly assinada para ownership das conversas."""

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        _, created = establish_session(request, settings.conversation_session_secret)
        response = await call_next(request)
        if created:
            response.set_cookie(
                SESSION_COOKIE,
                request.state.conversation_session,
                max_age=2_592_000,
                httponly=True,
                secure=settings.environment != "development",
                samesite="none" if settings.environment != "development" else "lax",
                path="/",
            )
        return response

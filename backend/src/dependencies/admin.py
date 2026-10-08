"""HTTP-only session cookie and Origin policy for every admin endpoint."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from src.core.settings import get_settings
from src.dependencies.services import AdminAuthServiceDep
from src.services.admin_auth import SessionGrant

COOKIE_NAME = "admin_session"


def set_session_cookie(response: Response, token: str) -> None:
    """Use root scope so Next.js can authenticate server-rendered /admin pages."""
    settings = get_settings().admin
    response.set_cookie(
        key=COOKIE_NAME, value=token, max_age=settings.session_ttl_seconds,
        httponly=True, secure=settings.cookie_secure, samesite="strict", path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the cookie with exactly the same scope and security attributes."""
    response.delete_cookie(
        key=COOKIE_NAME, path="/", httponly=True,
        secure=get_settings().admin.cookie_secure, samesite="strict",
    )


async def check_admin_origin(request: Request) -> None:
    """Fail closed on unsafe requests; never derive trusted origins from Host."""
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origins = request.headers.getlist("origin")
        if len(origins) != 1 or origins[0] not in get_settings().admin.allowed_origins:
            raise HTTPException(status_code=403, detail="Origin not allowed")


async def require_admin(
    request: Request, response: Response, service: AdminAuthServiceDep,
) -> SessionGrant:
    """Authenticate and renew both the database expiry and the browser lifetime."""
    grant = await service.authenticate(request.cookies.get(COOKIE_NAME))
    set_session_cookie(response, grant.token)
    return grant


AdminDep = Annotated[SessionGrant, Depends(require_admin)]

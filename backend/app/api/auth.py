from fastapi import APIRouter, Depends, Response

from ..core.config import get_settings
from ..core.security import (
    COOKIE_NAME,
    authenticate,
    create_session,
    current_user,
    require_csrf,
)
from ..schemas.auth import LoginRequest, SessionResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=SessionResponse)
def login(data: LoginRequest, response: Response) -> SessionResponse:
    user = authenticate(data.password)
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Senha incorreta")
    token, csrf = create_session(user)
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return SessionResponse(role=user["role"], name=user["name"], csrf_token=csrf)


@router.get("/me", response_model=SessionResponse)
def me(user: dict = Depends(current_user)) -> SessionResponse:
    return SessionResponse(role=user["role"], name=user["name"], csrf_token=user["csrf"])


@router.post("/logout", status_code=204)
def logout(response: Response, _: dict = Depends(require_csrf)) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")

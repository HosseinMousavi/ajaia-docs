from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.deps import SESSION_COOKIE, CurrentUser, DbSession
from app.models import User
from app.schemas import DemoUserOut, LoginIn, UserOut
from app.security import verify_password
from app.seed import DEMO_USERS

router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID = "Invalid email or password"


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: DbSession) -> User:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _INVALID)
    settings = request.app.state.settings
    response.set_cookie(
        SESSION_COOKIE,
        request.app.state.signer.issue(user.id),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.get("/demo-users", response_model=list[DemoUserOut])
def demo_users(request: Request) -> list[DemoUserOut]:
    if not request.app.state.settings.seed_demo_users:
        return []
    return [DemoUserOut(email=e, name=n) for e, n in DEMO_USERS]

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

import jwt
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import Settings, get_settings
from src.core.exceptions import AuthenticationError, ForbiddenError

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    role: str


def decode_token(token: str, settings: Settings) -> dict[str, object]:
    try:
        return cast(
            dict[str, object],
            jwt.decode(
                token,
                settings.jwt.secret,
                algorithms=[settings.jwt.algorithm],
                audience=settings.jwt.audience,
                issuer=settings.jwt.issuer,
                leeway=settings.jwt.leeway,
            ),
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("TOKEN_EXPIRED", "Токен истёк") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("TOKEN_INVALID", "Токен недействителен") from exc


async def get_current_user(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("TOKEN_MISSING", "Токен отсутствует")
    payload = decode_token(credentials.credentials, settings)
    try:
        user_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("TOKEN_INVALID", "Токен недействителен") from exc
    role = str(payload.get("role", ""))
    if role not in {"admin", "teacher", "student"}:
        raise AuthenticationError("TOKEN_INVALID", "Токен недействителен")
    return CurrentUser(id=user_id, role=role)


def require_roles(*roles: str) -> Callable[..., Awaitable[CurrentUser]]:
    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return _checker


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
TeacherDep = Annotated[CurrentUser, Depends(require_roles("teacher", "admin"))]
AdminDep = Annotated[CurrentUser, Depends(require_roles("admin"))]
StudentDep = Annotated[CurrentUser, Depends(require_roles("student"))]

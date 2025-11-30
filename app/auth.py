import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings

security = HTTPBearer()


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iss": settings.JWT_ISS,
        "aud": settings.JWT_AUD,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def parse_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            audience=settings.JWT_AUD,
            issuer=settings.JWT_ISS,
        )
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user_id(
    creds: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return parse_token(creds.credentials)


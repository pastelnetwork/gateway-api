from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader

from typing import Generator
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

api_key_header = APIKeyHeader(name="api_key", auto_error=False)


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

class OAuth2Auth:
    @staticmethod
    def get_current_user(
            db: Session = Depends(get_db),
            token: str = Depends(reusable_oauth2)
    ) -> models.User:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
            )
            token_data = schemas.TokenPayload(**payload)
            print(token)
        except (jwt.JWTError, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
        user = crud.user.get(db, id=token_data.sub)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    def get_current_active_user(
            current_user: models.User = Depends(get_current_user),
    ) -> models.User:
        if not crud.user.is_active(current_user):
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    @staticmethod
    def get_current_active_superuser(
            current_user: models.User = Depends(get_current_user),
    ) -> models.User:
        if not crud.user.is_superuser(current_user):
            raise HTTPException(
                status_code=400, detail="The user doesn't have enough privileges"
            )
        return current_user


class APIKeyAuth:
    @staticmethod
    async def get_api_key(api_key: str = Security(api_key_header)):
        if api_key == "test-api-key":
            return api_key_header
        else:
            raise HTTPException(
                status_code=403, detail="Could not validate API KEY"
            )

    @staticmethod
    def get_current_user(
            db: Session = Depends(get_db),
            api_key: str = Depends(api_key_header)
    ) -> models.User:
        print(api_key)
        user = crud.user.get_by_api_key(api_key)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

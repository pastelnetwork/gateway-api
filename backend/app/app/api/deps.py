from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader

from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core import security
from app.core.config import settings
from app.db.session import get_db_session

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

api_key_header = APIKeyHeader(name="api_key", auto_error=False)


class OAuth2Auth:
    @staticmethod
    def get_current_user(
            db: Session = Depends(get_db_session),
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
    async def get_api_key(
            db: Session = Depends(get_db_session),
            api_key: str = Security(api_key_header)
    ) -> models.ApiKey:
        print(api_key)
        apikey = crud.api_key.get_by_api_key(db=db, api_key=api_key)
        if not apikey:
            raise HTTPException(
                status_code=403, detail="Could not validate API KEY"
            )
        return apikey

    @staticmethod
    async def get_api_key_for_cascade(
            db: Session = Depends(get_db_session),
            api_key: str = Security(api_key_header)
    ) -> models.ApiKey:
        apikey = await APIKeyAuth.get_api_key(db=db, api_key=api_key)
        if not apikey.can_cascade:
            raise HTTPException(
                status_code=403,
                detail="Cascade scope is not allowed for API Key",
            )
        return apikey

    @staticmethod
    async def get_api_key_for_sense(
            db: Session = Depends(get_db_session),
            api_key: str = Security(api_key_header)
    ) -> models.ApiKey:
        apikey = await APIKeyAuth.get_api_key(db=db, api_key=api_key)
        if not apikey.can_sense:
            raise HTTPException(
                status_code=403,
                detail="Sense scope is not allowed for API Key",
            )
        return apikey

    @staticmethod
    async def get_api_key_for_nft(
            db: Session = Depends(get_db_session),
            api_key: str = Security(api_key_header)
    ) -> models.ApiKey:
        apikey = await APIKeyAuth.get_api_key(db=db, api_key=api_key)
        if not apikey.can_nft:
            raise HTTPException(
                status_code=403,
                detail="Cascade scope is not allowed for API Key",
            )
        return apikey

    @staticmethod
    def get_user_by_apikey(
            db: Session = Depends(get_db_session),
            api_key: str = Depends(api_key_header)
    ) -> models.User:
        print(api_key)
        user = crud.user.get_by_api_key(db=db, api_key=api_key)
        if not user:
            raise HTTPException(status_code=404, detail="Unknown API Key")
        return user

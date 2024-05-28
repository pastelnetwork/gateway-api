from datetime import timedelta, datetime, timezone

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import get_random_string

import app.db.session as session
from app import crud, schemas, models
from app.core.config import settings
from app.utils.authentication import send_new_account_with_key_email
from app.core import security
from app.api import deps
from app.utils.crypto import verify_signature

router = APIRouter()


@router.post("/user", response_model=schemas.UserWithKey, response_model_exclude_none=True,
             description="Create new user with key auth, returns user object with funding address.",
             operation_id="key_authentication_create_user")
def create_user(
        *,
        user_in: schemas.UserCreateWithKey,
        client_id: str,
        client_secret: str,
        db: Session = Depends(session.get_db_session),
) -> Any:
    """
    Create new user.
    """
    if not crud.client.authenticate(db, id=client_id, secret=client_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid client ID or secret",
        )

    user = crud.user.get_by_wallet_id(db, wallet_id=user_in.wallet_id)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The account for this wallet already exists in the system.",
        )

    user = crud.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.user.create_with_key(db, obj_in=user_in)
    if settings.EMAILS_ENABLED and user_in.email:
        send_new_account_with_key_email( email_to=user_in.email, wallet_id=user.wallet_id,
                                         wallet_key_index=user.wallet_key_index, key_salt=user.key_salt)
    return user


@router.put("/user/set_key", response_model=schemas.UserWithKey, response_model_exclude_none=True, operation_id="key_authentication_set_wallet_key")
async def set_wallet_key(
    *,
    wallet_id: str,
    signature1: str,
    signature2: str,
    wallet_key: str,
    timestamp: str,
    client_id: str,
    client_secret: str,
    db: Session = Depends(session.get_db_session),
) -> Any:
    # Validate timestamp is not too old - < 5 minutes
    validate_timestamp(timestamp)

    if not crud.client.authenticate(db, id=client_id, secret=client_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid client ID or secret",
        )

    user = crud.user.get_by_wallet_id(db, wallet_id=wallet_id)
    if not user:
        raise HTTPException(status_code=403, detail="Incorrect wallet_id")

    if user.wallet_key is not None:
        raise HTTPException(status_code=403, detail="Key already set")

    # Validate signature1: msg = wallet_key+timestamp; key = wallet_id
    if not await verify_signature(wallet_key+timestamp, signature1, wallet_id):
        raise HTTPException(status_code=403, detail="Incorrect signature1")

    # Validate signature2: msg = user.key_salt+timestamp; key = wallet_key
    if not await verify_signature(user.key_salt+timestamp, signature2, wallet_key):
        raise HTTPException(status_code=403, detail="Incorrect signature2")

    upd = {
        "wallet_key": wallet_key,
        "key_salt": get_random_string(16),
        "updated_at": datetime.utcnow(),
    }
    return crud.user.update(db, db_obj=user, obj_in=upd)


@router.put("/user/clear_key", response_model=schemas.UserWithKey, response_model_exclude_none=True, operation_id="key_authentication_clear_wallet_key")
def clear_wallet_key(
    *,
    db: Session = Depends(session.get_db_session),
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    return crud.user.set_wallet_key(db, user=current_user, wallet_key="")


@router.get("/login/get_params", response_model=schemas.UserWithKey, operation_id="key_authentication_login_get")
async def get_login_with_key_params(
        wallet_id: str,
        signature: str,
        validation_token: str,
        timestamp: str,
        client_id: str,
        client_secret: str,
        db: Session = Depends(session.get_db_session),
) -> Any:
    # Validate timestamp is not too old - < 5 minutes
    validate_timestamp(timestamp)

    if not crud.client.authenticate(db, id=client_id, secret=client_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid client ID or secret",
        )

    # Validate signature: msg = wallet_key+timestamp; key = wallet_id
    if not await verify_signature(validation_token+timestamp, signature, wallet_id):
        raise HTTPException(status_code=403, detail="Incorrect signature")

    user = crud.user.get_by_wallet_id(db, wallet_id=wallet_id)
    if not user:
        raise HTTPException(status_code=403, detail="Incorrect wallet_id")

    return schemas.UserWithKey(wallet_id=wallet_id, wallet_key_index=user.wallet_key_index, key_salt=user.key_salt,
                               is_superuser=user.is_superuser)


@router.post("/login", response_model=schemas.Token, operation_id="key_authentication_login_post")
async def login_with_key(
        wallet_id: str,
        signature: str,
        timestamp: str,
        client_id: str,
        client_secret: str,
        db: Session = Depends(session.get_db_session),
) -> Any:
    # Validate timestamp is not too old - < 5 minutes
    validate_timestamp(timestamp)

    if not crud.client.authenticate(db, id=client_id, secret=client_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid client ID or secret",
        )

    user = crud.user.get_by_wallet_id(db, wallet_id=wallet_id)
    if not user:
        raise HTTPException(status_code=403, detail="Incorrect wallet_id")

    if not user.wallet_key:
        raise HTTPException(status_code=403, detail="Key not set")

    # Validate signature: msg = user.key_salt+timestamp; key = user.wallet_key
    if not await verify_signature(user.key_salt+timestamp, signature, user.wallet_key):
        raise HTTPException(status_code=403, detail="Incorrect signature")

    upd = {"key_salt": get_random_string(16), "updated_at": datetime.utcnow()}
    crud.user.update(db, db_obj=user, obj_in=upd)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


def validate_timestamp(timestamp: str):
    if int(timestamp) < (datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp():
        raise HTTPException(status_code=403, detail="Timestamp too old")

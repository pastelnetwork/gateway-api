from typing import Any, List

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic.networks import EmailStr
from sqlalchemy.orm import Session

import app.db.session as session
from app import crud, models, schemas
from app.api import deps
from app.core.config import settings
from app.utils.authentication import send_new_account_email

router = APIRouter()


@router.get("", response_model=List[schemas.User], response_model_exclude_none=True, operation_id="users_read_users")
def read_users(
    db: Session = Depends(session.get_db_session),
    skip: int = 0,
    limit: int = 100,
    super_user: models.User = Depends(deps.OAuth2Auth.get_current_active_superuser),
) -> Any:
    """
    Retrieve users.
    """
    users = crud.user.get_multi(db, skip=skip, limit=limit)
    return users


@router.post("", response_model=schemas.User, response_model_exclude_none=True, description="Create new user, returns user object with funding address. limit=0 means no limit", operation_id="users_create_user")
def create_user(
    *,
    db: Session = Depends(session.get_db_session),
    user_in: schemas.UserCreate,
    super_user: models.User = Depends(deps.OAuth2Auth.get_current_active_superuser),
) -> Any:
    """
    Create new user.
    """
    user = crud.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    user = crud.user.create(db, obj_in=user_in)
    if settings.EMAILS_ENABLED and user_in.email:
        send_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
    return user


@router.delete("/{user_id}", response_model=schemas.User, response_model_exclude_none=True, operation_id="users_delete_user")
def delete_apikey(
    *,
    user_id: int,
    db: Session = Depends(session.get_db_session),
    super_user: models.User = Depends(deps.OAuth2Auth.get_current_active_superuser),
) -> Any:
    """
    Delete user.
    """
    user = crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this user ID does not exist in the system",
        )
    deletedUser = crud.user.remove(db, id=user_id)
    return deletedUser


@router.put("/me", response_model=schemas.User, response_model_exclude_none=True, operation_id="users_update_user_me")
def update_user_me(
    *,
    db: Session = Depends(session.get_db_session),
    password: str = Body(None),
    full_name: str = Body(None),
    email: EmailStr = Body(None),
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    """
    Update own user.
    """
    current_user_data = jsonable_encoder(current_user)
    user_in = schemas.UserUpdate(**current_user_data)
    if password is not None:
        user_in.password = password
    if full_name is not None:
        user_in.full_name = full_name
    if email is not None:
        user_in.email = email
    user = crud.user.update(db, db_obj=current_user, obj_in=user_in)
    return user


@router.get("/me", response_model=schemas.User, response_model_exclude_none=True, operation_id="users_read_user_me")
def read_user_me(
    db: Session = Depends(session.get_db_session),
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user


@router.post("/open", response_model=schemas.User, response_model_exclude_none=True, operation_id="users_create_user_open")
def create_user_open(
    *,
    db: Session = Depends(session.get_db_session),
    password: str = Body(...),
    email: EmailStr = Body(...),
    full_name: str = Body(None),
    balance_limit: float = Body(0.0, description="User's balance limit, 0 means no limit"),
) -> Any:
    """
    Create new user without the need to be logged in.
    """
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open user registration is forbidden on this server",
        )
    user = crud.user.get_by_email(db, email=email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    user_in = schemas.UserCreate(password=password, email=email, full_name=full_name, balance_limit=balance_limit)
    user = crud.user.create(db, obj_in=user_in)
    return user


@router.get("/{user_id}", response_model=schemas.User, response_model_exclude_none=True, operation_id="users_read_user_by_id")
def read_user_by_id(
    user_id: int,
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
    db: Session = Depends(session.get_db_session),
) -> Any:
    """
    Get a specific user by id.
    """
    user = crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this user ID does not exist in the system",
        )
    if user == current_user:
        return user
    if not crud.user.is_superuser(current_user):
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return user


@router.put("/{user_id}", response_model=schemas.User, response_model_exclude_none=True, operation_id="users_update_user")
def update_user(
    *,
    db: Session = Depends(session.get_db_session),
    user_id: int,
    user_in: schemas.UserUpdate,
    super_user: models.User = Depends(deps.OAuth2Auth.get_current_active_superuser),
) -> Any:
    """
    Update a user.
    """
    user = crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system",
        )
    user = crud.user.update(db, db_obj=user, obj_in=user_in)
    return user

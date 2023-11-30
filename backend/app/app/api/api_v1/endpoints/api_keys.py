import random
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import app.db.session as session
from app import crud, models, schemas
from app.api import deps
from app.utils.pasteld import create_and_register_pastelid
from app.utils.authentication import get_random_string
from app.utils.pasteld import create_address
from app.utils.secret_manager import store_pastelid_to_secret_manager
from app.core.config import settings

router = APIRouter()


@router.get("", response_model=List[schemas.ApiKey], response_model_exclude_none=True)
def read_apikeys(
    db: Session = Depends(session.get_db_session),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    """
    Retrieve api key of the user.
    """
    if crud.user.is_superuser(current_user):
        apikeys = crud.api_key.get_multi(db, skip=skip, limit=limit)
    else:
        apikeys = crud.api_key.get_multi_by_owner(
            db=db, owner_id=current_user.id, skip=skip, limit=limit
        )
    return apikeys


@router.post("", response_model=schemas.ApiKey, response_model_exclude_none=True)
def create_apikey(
    *,
    db: Session = Depends(session.get_db_session),
    apikey_in: schemas.ApiKeyCreate,
    # with_address: bool = False,
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    """
    Create new api key.
    """
    passkey = get_random_string(16)
    pastel_id = create_and_register_pastelid(passkey, settings.MAIN_GATEWAY_ADDRESS)
    funding_address = None
    # if with_address:
    #     funding_address = create_address()
    apikey = crud.api_key.create_with_owner(db=db, obj_in=apikey_in, owner_id=current_user.id,
                                            pastel_id=pastel_id, funding_address=funding_address)
    store_pastelid_to_secret_manager(pastel_id, passkey)
    return apikey


@router.get("/{api_key}", response_model=schemas.ApiKey, response_model_exclude_none=True)
def read_apikey(
    *,
    db: Session = Depends(session.get_db_session),
    api_key: str,
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    """
    Get api key by apikey.
    """
    return get_api_key(db=db, api_key=api_key, current_user=current_user)


@router.delete("/{api_key}", response_model=schemas.ApiKey)
def delete_apikey(
    *,
    db: Session = Depends(session.get_db_session),
    api_key: str,
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    """
    Delete an api key.
    """
    apikey = get_api_key(db=db, api_key=api_key, current_user=current_user)
    return crud.api_key.remove(db=db, id=apikey.id)


def get_api_key(
        db: Session,
        api_key: str,
        current_user: models.User
) -> schemas.ApiKey:
    apikey = crud.api_key.get_by_api_key(db=db, api_key=api_key)
    if not apikey:
        raise HTTPException(status_code=404, detail="Api Key not found")
    if not crud.user.is_superuser(current_user) and (apikey.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return apikey

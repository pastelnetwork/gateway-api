from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import app.db.session as session
from app import crud, schemas, models
from app.core.security import get_random_string
from app.api import deps

router = APIRouter()


@router.post("/create_client", response_model=schemas.ClientWithSecret, response_model_exclude_none=True,
             # include_in_schema=False
             )
def create_client(
        *,
        db: Session = Depends(session.get_db_session),
        super_user: models.User = Depends(deps.OAuth2Auth.get_current_active_superuser),
) -> Any:
    """
    Create new client.
    """
    client_secret = get_random_string(32)
    client = crud.client.create(db, secret=client_secret)
    client_with_secret = schemas.ClientWithSecret(client_id=client.id, client_secret=client_secret)
    return client_with_secret

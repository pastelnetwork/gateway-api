from typing import Any, Dict, Optional, Union, List

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.security import get_secret_hash, verify_hashed_secret
from app.crud.base import CRUDBase, CreateSchemaType, ModelType, UpdateSchemaType
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


class CRUDClient(CRUDBase[Client, ClientCreate, ClientUpdate]):

    def create(self, db: Session, *, secret: str) -> Client:
        db_obj = Client(
            hashed_secret=get_secret_hash(secret),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


    def authenticate(self, db: Session, *, id: str, secret: str) -> bool:
        c = self.get(db, id=id)
        if not c:
            return False
        return verify_hashed_secret(secret, c.hashed_secret)


client = CRUDClient(Client)

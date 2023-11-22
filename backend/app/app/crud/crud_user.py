from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.security import get_secret_hash, verify_hashed_secret
from app.crud.base import CRUDBase
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.user import ClaimedPastelId
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def get_by_api_key(self, db: Session, *, api_key: str) -> Optional[User]:
        return (
            db.query(User)
            .join(ApiKey)
            .filter(ApiKey.api_key == api_key)
            .first())

    def create(self, db: Session, *, obj_in: UserCreate, funding_address: str = None) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=get_secret_hash(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
        )
        if funding_address:
            db_obj.funding_address = funding_address
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        if update_data["password"]:
            hashed_password = get_secret_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def authenticate(self, db: Session, *, email: str, password: str) -> Optional[User]:
        u = self.get_by_email(db, email=email)
        if not u:
            return None
        if not verify_hashed_secret(password, u.hashed_password):
            return None
        return u

    def is_active(self, user: User) -> bool:
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        return user.is_superuser

    # Get user by PastelID from ClaimedPasteID table
    def get_by_pastelid(self, db: Session, *, pastel_id: str) -> Optional[User]:
        return (
            db.query(User)
            .join(ClaimedPastelId)
            .filter(ClaimedPastelId.pastel_id == pastel_id)
            .first())

    # Add PastelID to user in ClaimedPastelID table
    def add_pastelid(self, db: Session, *, pastel_id: str, owner_id: int) -> ClaimedPastelId:
        db_obj = ClaimedPastelId(
            pastel_id=pastel_id,
            owner_id=owner_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_funding_address(self, db: Session, *, owner_id: int) -> Optional[str]:
        db_obj = db.query(self.model).filter(User.id == owner_id).first()
        if not db_obj:
            return None
        return db_obj.funding_address


user = CRUDUser(User)

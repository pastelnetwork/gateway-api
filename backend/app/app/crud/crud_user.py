from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.security import get_secret_hash, verify_hashed_secret
from app.crud.base import CRUDBase
from app.models.user import User
from app.models.api_key import ApiKey, InviteCode
from app.schemas.user import UserCreate, UserUpdate

#Temporarily using a file for invite codes instead of the database, because not clear the right way to import the data
filepath_to_invite_code_list = '/OpenAPI_Invite_codes.csv'
with open(filepath_to_invite_code_list,'r') as f:
    data = f.read()
    list_of_invite_codes = data.split('\n')


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def get_by_api_key(self, db: Session, *, api_key: str) -> Optional[User]:
        return db.query(User).join(ApiKey).first()

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=get_secret_hash(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
            invite_code=obj_in.invite_code
        )
        if obj_in.invite_code in list_of_invite_codes:
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
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_hashed_secret(password, user.hashed_password):
            return None
        return user

    def is_active(self, user: User) -> bool:
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        return user.is_superuser


user = CRUDUser(User)

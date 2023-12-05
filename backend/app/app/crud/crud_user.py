from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.security import get_secret_hash, verify_hashed_secret
from app.crud.base import CRUDBase, CreateSchemaType, ModelType, UpdateSchemaType
from app.models.user import User, AccountTransactions, TXType
from app.models.api_key import ApiKey
from app.models.user import ClaimedPastelId
from app.schemas.user import UserCreate, UserUpdate, AccountTransactionsCreate, AccountTransactionsUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def get_by_api_key(self, db: Session, *, api_key: str) -> Optional[User]:
        return (
            db.query(User)
            .join(ApiKey)
            .filter(ApiKey.api_key == api_key)
            .first())

    def create(self, db: Session, *, obj_in: UserCreate,
               balance: float = 0.0, funding_address: str = None) -> User:
        db_obj = User(
            email=obj_in.email,
            hashed_password=get_secret_hash(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
        )
        if funding_address:
            db_obj.funding_address = funding_address
        if balance > 0:
            db_obj.balance = balance
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

    def get_funding_address(self, db: Session, *, owner_id: int, default_value: str = None) -> Optional[str]:
        db_obj = db.query(self.model).filter(User.id == owner_id).first()
        if not db_obj:
            return None
        return db_obj.funding_address if (db_obj.funding_address and db_obj.funding_address != '') else default_value

    def decrement_balance(self, db: Session, *, user_id: int, amount: float) -> Optional[User]:
        db_obj = db.query(self.model).filter(User.id == user_id).first()
        if not db_obj:
            return None
        # if db_obj.balance < amount:
        #     return None
        db_obj.balance -= amount
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def increment_balance(self, db: Session, *, owner_id: int, amount: float) -> Optional[User]:
        db_obj = db.query(self.model).filter(User.id == owner_id).first()
        if not db_obj:
            return None
        db_obj.balance += amount
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def check_balance(self, db: Session, *, owner_id: int, amount: float) -> bool:
        db_obj = db.query(self.model).filter(User.id == owner_id).first()
        if not db_obj:
            return False
        if db_obj.balance < amount:
            return False
        return True


class CRUDAccountTransactions(CRUDBase[AccountTransactions, AccountTransactionsCreate, AccountTransactionsUpdate]):
    def create_with_owner(self, db: Session, *, owner_id: int, balance: float, tx_type: TXType) -> AccountTransactions:
        db_obj = AccountTransactions(
            owner_id=owner_id,
            type=tx_type,
            balance=balance
        )

        # Update user's current balance
        user_obj = db.query(User).filter_by(id=owner_id).one()
        if tx_type == TXType.DEPOSIT:
            user_obj.balance += balance
        elif tx_type == TXType.WITHDRAWAL or tx_type == TXType.USAGE:
            if user_obj.balance < balance:
                return None
            user_obj.balance -= balance
        elif tx_type == TXType.MOVED_TO_APIKEY:
            if user_obj.balance < balance:
                return None
            user_obj.balance -= balance
            api_key_obj = db.query(ApiKey).filter_by(id=owner_id).one()
            api_key_obj.balance += balance
        else:
            return None

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        pass

    def update(self, db: Session, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        pass

    def remove(self, db: Session, *, id: int) -> ModelType:
        pass


user = CRUDUser(User)
account_transactions = CRUDAccountTransactions(AccountTransactions)

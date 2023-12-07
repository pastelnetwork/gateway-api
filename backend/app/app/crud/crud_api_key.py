from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.security import create_api_key
from app.crud.base import CRUDBase
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate


class CRUDApiKey(CRUDBase[ApiKey, ApiKeyCreate, ApiKeyUpdate]):
    def get_by_api_key(self, db: Session, *, api_key: str) -> Optional[ApiKey]:
        return db.query(self.model).filter(ApiKey.api_key == api_key).first()

    @staticmethod
    def create_with_owner(db: Session, *, obj_in: ApiKeyCreate, owner_id: int,
                          pastel_id: str = None,
                          funding_address: str = None) -> ApiKey:
        db_obj = ApiKey(
            api_key=create_api_key(owner_id),
            can_nft=obj_in.can_nft,
            can_sense=obj_in.can_sense,
            can_cascade=obj_in.can_cascade,
            owner_id=owner_id
        )
        if pastel_id:
            db_obj.pastel_id = pastel_id
        # if funding_address:
        #     db_obj.funding_address = funding_address
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_owner(
        self, db: Session, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[ApiKey]:
        return (
            db.query(self.model)
            .filter(ApiKey.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    # def get_funding_address_by_api_key(self, db: Session, *, api_key: str, default_value: str = None) -> Optional[str]:
    #     db_obj = db.query(self.model).filter(ApiKey.api_key == api_key).first()
    #     if not db_obj:
    #         return None
    #     return db_obj.funding_address if (db_obj.funding_address and db_obj.funding_address != '') else default_value
    #
    # def get_funding_address_by_pastel_id(self, db: Session, *, pastel_id: str, default_value: str = None) -> Optional[str]:
    #     db_obj = db.query(self.model).filter(ApiKey.pastel_id == pastel_id).first()
    #     if not db_obj:
    #         return None
    #     return db_obj.funding_address if (db_obj.funding_address and db_obj.funding_address != '') else default_value


api_key = CRUDApiKey(ApiKey)

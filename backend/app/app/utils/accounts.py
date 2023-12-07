from sqlalchemy.orm import Session
from typing import Dict

from app import crud, models
from app.core.config import settings


def get_total_balance_by_userid(db: Session, *, user_id: int) -> Dict:
    user = crud.user.get(db, id=user_id)
    return get_total_balance(db, user=user)


def get_total_balance(db: Session, *, user: models.User) -> Dict:
    current_balance = user.balance if user.balance else 0.0
    cascade_pending = crud.cascade.get_pending_fee_sum(db, owner_id=user.id)
    sense_pending = crud.sense.get_pending_fee_sum(db, owner_id=user.id)
    nft_pending = crud.nft.get_pending_fee_sum(db, owner_id=user.id)
    collection_pending = (crud.collection.get_number_of_pending(db, owner_id=user.id)
                          * settings.TICKET_PRICE_COLLECTION_REG)

    total_pending = cascade_pending + sense_pending + nft_pending + collection_pending
    results = {
        "balance_limit": user.balance_limit,
        "total_balance": current_balance + total_pending,
    }
    if total_pending > 0:
        results["current_balance"] = current_balance
        results["pending_balance"] = total_pending
        results["pending_details"] = {
            "cascade": cascade_pending,
            "sense": sense_pending,
            "nft": nft_pending,
            "collection": collection_pending,
        }
    return results

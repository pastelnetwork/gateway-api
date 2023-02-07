from sqlalchemy.orm import Session
from app import crud
from app.tests.utils.utils import random_lower_string


def test_create_cascade_job(db: Session) -> None:
    burn_txid = random_lower_string()
    ticket_id = random_lower_string()

    # Create new bound
    burn_tx = crud.preburn_tx.create_new_bound(db,
                                               fee=11111,
                                               height=1000000,
                                               txid=burn_txid,
                                               ticket_id=ticket_id)
    assert burn_tx.fee == 11111
    assert burn_tx.height == 1000000
    assert burn_tx.txid == burn_txid
    assert burn_tx.ticket_id == ticket_id

    # Get bound by ticket_id
    burn_tx_from_db = crud.preburn_tx.get_bound_to_result(db, result_id=ticket_id)
    assert burn_tx_from_db.fee == 11111
    assert burn_tx_from_db.height == 1000000
    assert burn_tx_from_db.txid == burn_txid
    assert burn_tx_from_db.ticket_id == ticket_id

    # Mark bound as new
    crud.preburn_tx.mark_non_used(db, burn_tx_from_db)
    free_burn_tx = crud.preburn_tx.get_non_used_by_fee(db, fee=11111)
    assert free_burn_tx.fee == 11111
    assert free_burn_tx.height == 1000000
    assert free_burn_tx.txid == burn_txid
    assert free_burn_tx.ticket_id == ticket_id

    # Delete preburn_tx
    crud.preburn_tx.remove(db, id=free_burn_tx.id)


import asyncio
import time
import random
import binascii
from typing import Any
from cachetools import TTLCache

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import app.db.session as session
from app import crud, models
from app.api import deps
import app.utils.pasteld as psl

router = APIRouter()
cache = TTLCache(maxsize=100, ttl=600)


@router.get("/pastelid_claiming_step_1")
def pastelid_claiming_step_1(
    *,
    pastel_id = Query("", description="Pastel ID to claim"),
    db: Session = Depends(session.get_db_session),
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> str:
    check_new_pastelid(current_user, db, pastel_id)

    # Get current timestamp
    timestamp = int(time.time())
    # Get 4-byte random number
    random_number = random.randint(0, 2 ** 32 - 1)  # Generate a number in the range [0, 2^32 - 1]
    # Create string from timestamp and random number
    message = f"{timestamp}_{random_number}"
    # Encode the string to bytes
    message_bytes = message.encode('utf-8')
    # Convert bytes to hexadecimal representation
    hex_encoded_message = binascii.hexlify(message_bytes)

    # Store in cache using hash as key
    cache[pastel_id] = hex_encoded_message.decode()

    return hex_encoded_message.decode()


@router.put("/pastelid_claiming_step_2")
def pastelid_claiming_step_2(
    *,
    pastel_id = Query("", description="Pastel ID to claim"),
    signature = Query("", description="Signature of the message returned by pastelid_claiming_step_1"),
    db: Session = Depends(session.get_db_session),
    current_user: models.User = Depends(deps.OAuth2Auth.get_current_active_user),
) -> Any:
    # Retrieve from cache using hash as key
    stored_message = cache.get(pastel_id, None)
    if not stored_message:
        raise HTTPException(
            status_code=400,
            detail="The signature is invalid",
        )
    ok = asyncio.run(psl.verify_message(stored_message, signature, pastel_id))
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="The signature is invalid",
        )

    check_new_pastelid(current_user, db, pastel_id)

    # Update the user with the Pastel ID
    user = crud.user.add_pastelid(db, pastel_id=pastel_id, owner_id=current_user.id)
    return


def check_new_pastelid(current_user, db, pastel_id):
    # Check if the Pastel ID is already claimed
    user = crud.user.get_by_pastelid(db, pastel_id=pastel_id)
    if user:
        if user.id != current_user.id:
            raise HTTPException(
                status_code=400,
                detail="The Pastel ID is already claimed by another user",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="The Pastel ID is already claimed by this user",
            )

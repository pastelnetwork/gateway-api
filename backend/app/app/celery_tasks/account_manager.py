from celery import shared_task
from celery.utils.log import get_task_logger

from app.db.session import db_context
from app.utils.pasteld import create_address
from app import crud
from app.core.config import settings
from app.utils import pasteld as psl


logger = get_task_logger(__name__)


@shared_task(name="account_manager:address_maker")
def address_maker():
    logger.info(f"address_maker task started")
    with db_context() as session:
        users = crud.user.get_all_without_funding_address(session)
    for user in users:
        try:
            funding_address = create_address()
        except Exception as e:
            logger.error(f"Error creating address for user {user.id}: {e}")
            continue
        with db_context() as session:
            crud.user.update(session, db_obj=user, obj_in={"funding_address": funding_address})
    logger.info(f"address_maker task finished")


@shared_task(name="account_manager:balancer")
def address_maker():
    logger.info(f"balancer task started")
    with db_context() as session:
        users = crud.user.get_all_with_balance_more_then(session, balance=settings.BALANCE_PAYMENT_THRESHOLD)
    for user in users:
        try:
            if not psl.check_address_balance(user.funding_address,
                                             settings.BALANCE_PAYMENT_THRESHOLD,
                                             f"user account payment"):
                logger.info(f'balancer: User {user.id} address {user.funding_address} '
                            f'balance is less then {settings.BALANCE_PAYMENT_THRESHOLD}')
                continue
            txid = psl.send_to_many_z(user.funding_address,
                                      {settings.MAIN_GATEWAY_ADDRESS: settings.BALANCE_PAYMENT_THRESHOLD})
            if not txid:
                logger.info(f'balancer: Cannot charge user {user.id} address {user.funding_address} ')
                continue
        except Exception as e:
            logger.error(f"Error paying balance for user {user.id}: {e}")
            continue
        with db_context() as session:
            crud.user.reset_balance(session, user_id=user.id)

    logger.info(f"balancer task finished")

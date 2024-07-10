import logging

from app.core.config import settings
from app.utils.aws import add_item_to_secret_in_secret_manager, get_secret_string_from_secret_manager

logger = logging.getLogger(__name__)


def store_pastelid_to_secret_manager(pastel_id: str, pastelid_secret: str):
    add_item_to_secret_in_secret_manager(settings.AWS_SECRET_MANAGER_REGION,
                                         settings.AWS_SECRET_MANAGER_PASTEL_IDS,
                                         pastel_id, pastelid_secret)


def get_pastelid_pwd(pastel_id: str) -> str:
    # Check if the pastel_id is the same as the one in the settings
    # If it is, return the password from the settings if it set
    if settings.PASTEL_ID_PWD and pastel_id == settings.PASTEL_ID:
        return settings.PASTEL_ID_PWD

    secret = get_secret_string_from_secret_manager(settings.AWS_SECRET_MANAGER_REGION,
                                                   settings.AWS_SECRET_MANAGER_PASTEL_IDS)
    if secret:
        return secret.get(pastel_id)

from requests import RequestException
import json
from PIL import Image

from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.status import DbStatus
from app.utils.authentication import send_alert_email
from .pastel_tasks import PastelAPITask, PastelAPIException
from app import crud, schemas
from app.utils.walletnode import WalletNodeService, WalletnodeException
from app.utils.pasteld import PasteldException
from app.core.config import settings
import app.utils.pasteld as psl

logger = get_task_logger(__name__)


class NftAPITask(PastelAPITask):
    def on_success(self, retval, result_id, args, kwargs):
        PastelAPITask.on_success_base(args, crud.nft.get_by_result_id, crud.nft.update)

    def on_failure(self, exc, result_id, args, kwargs, einfo):
        PastelAPITask.on_failure_base(args, crud.nft.get_by_result_id, crud.nft.update)

    def get_request_form(self, task_from_db) -> str:
        if not task_from_db.nft_properties:
            raise PastelAPIException(f"Task {task_from_db.result_id} doesn't have 'nft_properties'")

        maximum_fee = 0.0
        if "maximum_fee" in task_from_db.nft_properties:
            maximum_fee = task_from_db.nft_properties["maximum_fee"]

        if maximum_fee != 0 and task_from_db.wn_fee > maximum_fee:
            raise PastelAPIException(f"Task {task_from_db.result_id} has wn_fee [{task_from_db.wn_fee}] > "
                                     f"maximum_fee [{task_from_db.nft_properties['maximum_fee']}]")

        if maximum_fee == 0:
            # can throw exception here - this called from celery task, it will retry it on specific exceptions
            storage_fees = psl.call("storagefee", ["getnetworkfee"])
            if storage_fees and "networkfee" in storage_fees:
                maximum_fee = storage_fees["networkfee"]*settings.NFT_DEFAULT_MAX_FILE_SIZE_FOR_FEE_IN_MB
            else:
                raise PastelAPIException(f"Failed to call 'storagefee getnetworkfee'")

        # can throw exception here - this called from celery task, it will retry it on specific exceptions
        address_list = psl.call("listaddressamounts", [])
        spendable_address = None
        if address_list:
            for spendable_address, value in address_list.items():
                if value > task_from_db.wn_fee:
                    break

        if not spendable_address:
            send_alert_email(f"No spendable address found to pay NFT fee in the amount > {task_from_db.wn_fee}")
            raise PastelAPIException(f"No spendable address found for amount > {task_from_db.wn_fee}")

        return json.dumps(
            {
                "spendable_address": spendable_address,
                "creator_pastelid": settings.PASTEL_ID,  # task_from_db.creator_pastelid,

                "image_id": task_from_db.wn_file_id,
                "make_publicly_accessible": task_from_db.make_publicly_accessible,
                "collection_act_txid": task_from_db.collection_act_txid,
                "open_api_group_id": task_from_db.open_api_group_id,

                "creator_name": task_from_db.nft_properties["creator_name"] \
                    if "creator_name" in task_from_db.nft_properties else "",
                "creator_website_url": task_from_db.nft_properties["creator_website_url"] \
                    if "creator_website_url" in task_from_db.nft_properties else "",
                "description": task_from_db.nft_properties["description"] \
                    if "description" in task_from_db.nft_properties else "",
                "green": task_from_db.nft_properties["green"] \
                    if "green" in task_from_db.nft_properties else "",
                "issued_copies": task_from_db.nft_properties["issued_copies"] \
                    if "issued_copies" in task_from_db.nft_properties else "",
                "keywords": task_from_db.nft_properties["keywords"] \
                    if "keywords" in task_from_db.nft_properties else "",
                "maximum_fee": maximum_fee,
                "name": task_from_db.nft_properties["name"] \
                    if "name" in task_from_db.nft_properties else "",
                "royalty": task_from_db.nft_properties["royalty"] \
                    if "royalty" in task_from_db.nft_properties else "",
                "series_name": task_from_db.nft_properties["series_name"] \
                    if "series_name" in task_from_db.nft_properties else "",
                "thumbnail_coordinate": {
                    "bottom_right_x": task_from_db.nft_properties["thumbnail_coordinate_bottom_right_x"] \
                        if "thumbnail_coordinate_bottom_right_x" in task_from_db.nft_properties else 256,
                    "bottom_right_y": task_from_db.nft_properties["thumbnail_coordinate_bottom_right_y"] \
                        if "thumbnail_coordinate_bottom_right_y" in task_from_db.nft_properties else 256,
                    "top_left_x": task_from_db.nft_properties["thumbnail_coordinate_top_left_x"] \
                        if "thumbnail_coordinate_top_left_x" in task_from_db.nft_properties else 0,
                    "top_left_y": task_from_db.nft_properties["thumbnail_coordinate_top_left_y"] \
                        if "thumbnail_coordinate_top_left_y" in task_from_db.nft_properties else 0,
                },
                "youtube_url": task_from_db.nft_properties["youtube_url"] \
                    if "youtube_url" in task_from_db.nft_properties else "",
            }
        )

    def check_specific_conditions(self, task_from_db) -> (bool, str):
        if task_from_db.process_status != DbStatus.UPLOADED.value:
            err_msg = f'NFT: process_task: Wrong task state - "{task_from_db.process_status}", ' \
                      f'Should be {DbStatus.UPLOADED.value}' \
                      f'... [Result ID: {task_from_db.result_id}]'
            return False, err_msg
        return True, ''


def get_thumbnail_coordinates(image_path: str, thumbnail_size: int) -> schemas.ThumbnailCoordinate:
    with Image.open(image_path) as img:
        width, height = img.size

    # Calculate center of image
    center_x = width // 2
    center_y = height // 2

    # Calculate coordinates of square thumbnail
    left = max(0, center_x - thumbnail_size // 2)
    top = max(0, center_y - thumbnail_size // 2)
    right = min(width, center_x + thumbnail_size // 2)
    bottom = min(height, center_y + thumbnail_size // 2)

    return schemas.ThumbnailCoordinate(
        top_left_x=left,
        top_left_y=top,
        bottom_right_x=right,
        bottom_right_y=bottom,
    )


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             soft_time_limit=300, time_limit=360,
             name='nft:register_file', base=NftAPITask)
def register_file(self, result_id, local_file, request_id, user_id, ipfs_hash,
                  make_publicly_accessible: bool, collection_act_txid: str, open_api_group_id: str,
                  nft_details_payload: schemas.NftPropertiesExternal,
                  after_activation_transfer_to_pastelid: str) -> str:
    return self.register_file_task(
        result_id, local_file, user_id,
        lambda height: schemas.NftCreate(
            original_file_name=local_file.name,
            original_file_content_type=local_file.type,
            original_file_local_path=local_file.path,
            original_file_ipfs_link=ipfs_hash,
            make_publicly_accessible=make_publicly_accessible,
            offer_ticket_intended_rcpt_pastel_id=after_activation_transfer_to_pastelid,
            request_id=request_id,
            result_id=result_id,
            process_status=DbStatus.NEW.value,
            wn_file_id='',
            wn_fee=0,
            height=height,
            # The additional parameters for the NFT service:
            collection_act_txid=collection_act_txid,
            open_api_group_id=open_api_group_id,
            nft_properties=schemas.NftPropertiesInternal(
                creator_name=nft_details_payload.creator_name,
                creator_website_url=nft_details_payload.creator_website_url,
                description=nft_details_payload.description,
                green=nft_details_payload.green,
                issued_copies=nft_details_payload.issued_copies,
                keywords=nft_details_payload.keywords,
                maximum_fee=nft_details_payload.maximum_fee,
                name=nft_details_payload.name,
                royalty=nft_details_payload.royalty,
                series_name=nft_details_payload.series_name,
                youtube_url=nft_details_payload.youtube_url,
                thumbnail_coordinate=get_thumbnail_coordinates(local_file.path, settings.NFT_THUMBNAIL_SIZE_IN_PIXELS),
            )
        ),
        crud.nft.get_by_result_id,
        crud.nft.create_with_owner,
        crud.nft.update,
        register_file.retry,
        WalletNodeService.NFT,
        "register/upload", "image_id", "estimated_fee", 1)


# NFT registration does not require preburning
@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=10,
             soft_time_limit=300, time_limit=360,
             name='nft:process', base=NftAPITask)
def process(self, result_id) -> str:
    return self.process_task(result_id,
                             crud.nft.get_by_result_id,
                             crud.nft.update,
                             process.retry,
                             WalletNodeService.NFT)


@shared_task(bind=True,
             autoretry_for=(RequestException, WalletnodeException, PasteldException,),
             retry_backoff=30, max_retries=5,
             soft_time_limit=300, time_limit=360,
             name='nft:re_register_file', base=NftAPITask)
def re_register_file(self, result_id) -> str:
    return self.re_register_file_task(result_id,
                                      crud.nft.get_by_result_id,
                                      crud.nft.update,
                                      WalletNodeService.NFT,
                                      "register/upload", "image_id", "estimated_fee", 1)

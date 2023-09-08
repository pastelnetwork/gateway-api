import asyncio
import os
from pathlib import Path
from datetime import datetime
import requests

from app import crud
from app.core.status import DbStatus
from app.db.session import db_context
from app.utils.filestorage import search_processed_file, search_nft_dd_result
from app.utils.ipfs_tools import store_file_to_ipfs
from app.utils.walletnode import WalletNodeService


async def read_file_from_ipfs(ipfs_cid) -> bool:
    try:
        response = requests.get(f"https://ipfs.io/ipfs/{ipfs_cid}", timeout=20)
        if response.status_code == 200:
            return True
    except requests.exceptions.Timeout:
        pass
    except Exception:
        pass
    return False


async def check_processed_files_accessibility(get_all_func, update_func, service: WalletNodeService, ticket_type: str,
                                              check_ipfsio: bool = True):

    with db_context() as session:
        tasks_from_db = get_all_func(session)  # get latest 100(!) tasks in DONE state

    if not tasks_from_db:
        print("No tasks found")
        return

    records_to_check = len(tasks_from_db)
    print(f"checking {records_to_check} {ticket_type} links")

    processed_unavailable_file = f'processed-unavailable-{ticket_type}.txt'
    processed_unavailable = await get_unavailables(processed_unavailable_file, ticket_type)

    i = 0
    bad = 0
    for task_from_db in tasks_from_db:
        i += 1
        # Validate local cached and IPFS files
        if service == WalletNodeService.NFT:
            await search_nft_dd_result(db=session, task_from_db=task_from_db,
                                       update_task_in_db_func=update_func)
        data = await search_processed_file(db=session, task_from_db=task_from_db, update_task_in_db_func=update_func,
                                           task_done=(task_from_db.process_status in [DbStatus.DONE.value]),
                                           service=service)
        if not data:
            print(f"{i}/{records_to_check} Checking {ticket_type} {task_from_db.reg_ticket_txid} ... Not found")
            continue

        if check_ipfsio:
            # check if processed file is available on ipfs.io
            if task_from_db.stored_file_ipfs_link not in processed_unavailable:
                ipfs_cid = task_from_db.stored_file_ipfs_link
                print(f"{i}/{records_to_check} Checking {ticket_type} {ipfs_cid} ...", end='\r')
                if await read_file_from_ipfs(ipfs_cid):
                    print(f"{i}/{records_to_check} Checking {ticket_type} {ipfs_cid} ... Available from ipfs.io")
                else:
                    print(f"{i}/{records_to_check} Checking {ticket_type} {ipfs_cid} ... Unavailable from ipfs.io")
                    bad += 1
                    with open(processed_unavailable_file, 'a') as f:
                        f.write(f"{ipfs_cid}\n")

    print(f"There are {bad} new unavailable {ticket_type} links")


async def re_add_original_files_to_ipfs(get_all_func, update_func, ticket_type: str):

    with db_context() as session:
        tasks_from_db = get_all_func(session)  # get latest 100(!) tasks in DONE state

    if not tasks_from_db:
        print("No tasks found")
        return

    records_to_check = len(tasks_from_db)
    print(f"checking {records_to_check} {ticket_type} links")

    i = 0
    for task_from_db in tasks_from_db:
        i += 1

        # add original files to IPFS
        print(f"{i}/{records_to_check} Checking {ticket_type} "
              f"local file {task_from_db.original_file_ipfs_link}...", end='\r')
        path = Path(task_from_db.original_file_local_path)
        if path.is_file():
            ipfs_cid = store_file_to_ipfs(task_from_db.original_file_local_path)
            upd = {"original_file_ipfs_link": ipfs_cid, "updated_at": datetime.utcnow()}
            with db_context() as session:
                update_func(session, db_obj=task_from_db, obj_in=upd)
            print(f"{i}/{records_to_check} Checking {ticket_type} "
                  f"local file {task_from_db.original_file_ipfs_link}... Added", end='\r')


async def get_unavailables(processed_unavailable_file, ticket_type):
    unavailable = []
    if os.path.exists(processed_unavailable_file):
        with open(processed_unavailable_file, 'r') as f:
            unavailable = f.read().splitlines()
    print(f"There are {len(unavailable)} known unavailable {ticket_type} links to result files")
    return unavailable


if __name__ == "__main__":

    # re-add original files to IPFS
    # asyncio.run(re_add_original_files_to_ipfs(crud.sense.get_all_in_done, crud.sense.update, 'sense'))
    asyncio.run(re_add_original_files_to_ipfs(crud.nft.get_all_in_done, crud.nft.update, 'nft'))


    # check ipfs accessibility from ipfs.io
    # asyncio.run(check_processed_files_accessibility(crud.cascade.get_all_in_done, crud.cascade.update,
    #                                                      WalletNodeService.CASCADE, 'cascade'))
    # asyncio.run(check_processed_files_accessibility(crud.sense.get_all_in_done, crud.sense.update,
    #                                                      WalletNodeService.SENSE, 'sense'))
    asyncio.run(check_processed_files_accessibility(crud.nft.get_all_in_done, crud.nft.update,
                                                         WalletNodeService.NFT, 'nft'))

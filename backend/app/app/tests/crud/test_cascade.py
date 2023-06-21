# import random
from datetime import datetime
from sqlalchemy.orm import Session

from app import crud
from app.schemas.cascade import CascadeCreate   # , CascadeUpdate
from app.models.cascade import Cascade
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string, random_mime_type


def create_cascade_task(db: Session, *, request_id: str = None) -> (CascadeCreate, Cascade):
    local_file_name = random_lower_string()
    local_file_type = random_mime_type()
    local_file_path = random_lower_string()
    if not request_id:
        request_id = random_lower_string()
    result_id = random_lower_string()
    file_id = random_lower_string()
    # wn_fee = random.randint(100, 1000),
    # height = random.randint(100000, 1000000),

    new_cascade_job = CascadeCreate(
        original_file_name=local_file_name,
        original_file_content_type=local_file_type,
        original_file_local_path=local_file_path,
        request_id=request_id,
        result_id=result_id,
        process_status=result_id,
        wn_file_id=file_id,
        wn_fee=100000,
        height=1000000,
    )
    user = create_random_user(db)
    created_cascade_job = crud.cascade.create_with_owner(db=db, obj_in=new_cascade_job, owner_id=user.id)
    return new_cascade_job, created_cascade_job


def assert_cascade_jobs(cascade_job_1: CascadeCreate, cascade_job_2: Cascade) -> None:
    assert cascade_job_1.original_file_name == cascade_job_2.original_file_name
    assert cascade_job_1.original_file_content_type == cascade_job_2.original_file_content_type
    assert cascade_job_1.original_file_local_path == cascade_job_2.original_file_local_path
    assert cascade_job_1.request_id == cascade_job_2.request_id
    assert cascade_job_1.result_id == cascade_job_2.result_id
    assert cascade_job_1.wn_file_id == cascade_job_2.wn_file_id
    assert cascade_job_1.wn_fee == cascade_job_2.wn_fee
    assert cascade_job_1.height == cascade_job_2.height


# 1
def test_create_cascade_job(db: Session) -> None:
    new_cascade_task, created_cascade_task = create_cascade_task(db)
    assert_cascade_jobs(new_cascade_task, created_cascade_task)
    crud.cascade.remove(db=db, id=created_cascade_task.id)


# 2
def test_get_cascade_job_by_result_id(db: Session) -> None:
    new_cascade_task, created_cascade_task = create_cascade_task(db)
    stored_cascade_task = crud.cascade.get_by_result_id(db=db, result_id=new_cascade_task.result_id)
    assert_cascade_jobs(new_cascade_task, stored_cascade_task)
    crud.cascade.remove(db=db, id=created_cascade_task.id)


# 3
def test_get_cascade_job_by_request_id_and_name(db: Session) -> None:
    request_id = random_lower_string()
    new_cascade_task1, created_cascade_task1 = create_cascade_task(db, request_id=request_id)
    new_cascade_task2, created_cascade_task2 = create_cascade_task(db, request_id=request_id)
    stored_cascade_task1 = crud.cascade.get_by_request_id_and_name(db=db, request_id=request_id,
                                                                   file_name=new_cascade_task1.original_file_name)
    assert_cascade_jobs(new_cascade_task1, stored_cascade_task1)
    stored_cascade_task2 = crud.cascade.get_by_request_id_and_name(db=db, request_id=request_id,
                                                                   file_name=new_cascade_task2.original_file_name)
    assert_cascade_jobs(new_cascade_task2, stored_cascade_task2)
    crud.cascade.remove(db=db, id=created_cascade_task1.id)
    crud.cascade.remove(db=db, id=created_cascade_task2.id)


# 4
def test_get_multiple_cascade_job(db: Session) -> None:
    request_id = random_lower_string()
    new_cascade_task1, created_cascade_task1 = create_cascade_task(db, request_id=request_id)
    new_cascade_task2, created_cascade_task2 = create_cascade_task(db, request_id=request_id)
    # stored_cascade_tasks = crud.cascade.get_all_in_work(db=db, request_id=request_id, owner_id=current_user)
    # assert_cascade_jobs(new_cascade_task1, stored_cascade_tasks[0])
    # assert_cascade_jobs(new_cascade_task2, stored_cascade_tasks[1])
    crud.cascade.remove(db=db, id=created_cascade_task1.id)
    crud.cascade.remove(db=db, id=created_cascade_task2.id)


# 5
def test_get_non_started(db: Session) -> None:
    request_id = random_lower_string()
    new_cascade_task1, created_cascade_task1 = create_cascade_task(db, request_id=request_id)
    new_cascade_task2, created_cascade_task2 = create_cascade_task(db, request_id=request_id)
    stored_cascade_tasks = crud.cascade.get_all_in_request_not_started(db=db, request_id=request_id)
    assert_cascade_jobs(new_cascade_task1, stored_cascade_tasks[0])
    assert_cascade_jobs(new_cascade_task2, stored_cascade_tasks[1])
    crud.cascade.remove(db=db, id=created_cascade_task1.id)
    crud.cascade.remove(db=db, id=created_cascade_task2.id)


def mark_prepaid(db: Session, new_job: CascadeCreate, created_job: Cascade) -> (CascadeCreate, Cascade):
    task_id = random_lower_string()
    print(f"process_status: {task_id}")
    burn_txid = random_lower_string()
    upd = {"burn_txid": burn_txid, "process_status": task_id, "updated_at": datetime.utcnow()}
    updated_job = crud.cascade.update(db, db_obj=created_job, obj_in=upd)
    new_job.process_status = task_id
    print(f"updated_job: {updated_job.result_id}; new_job: {new_job.result_id}")
    assert_cascade_jobs(new_job, updated_job)
    assert updated_job.burn_txid == burn_txid
    return new_job, updated_job


def check_prepaid(db: Session, prepaid_job: CascadeCreate, request_id: str, num: int):
    prepaid_cascade_tasks = crud.cascade.get_all_in_request_prepaid(db=db, request_id=request_id)
    assert len(prepaid_cascade_tasks) == num
    assert_cascade_jobs(prepaid_job, prepaid_cascade_tasks[0])


def mark_started(db: Session, new_job: CascadeCreate, created_job: Cascade) -> (CascadeCreate, Cascade):
    task_id = random_lower_string()
    wn_task_id = random_lower_string()
    upd = {"wn_task_id": wn_task_id, "process_status": task_id, "updated_at": datetime.utcnow()}
    updated_job = crud.cascade.update(db, db_obj=created_job, obj_in=upd)
    new_job.process_status = task_id
    assert_cascade_jobs(new_job, updated_job)
    assert updated_job.wn_task_id == wn_task_id
    return new_job, updated_job


def check_started(db: Session, started_job: CascadeCreate, request_id: str, num: int):
    prepaid_cascade_tasks = crud.cascade.get_all_in_request_started(db=db, request_id=request_id)
    assert len(prepaid_cascade_tasks) == num
    assert_cascade_jobs(started_job, prepaid_cascade_tasks[0])


# 6
def test_update_and_get(db: Session) -> None:
    request_id = random_lower_string()
    new_job, created_job = create_cascade_task(db, request_id=request_id)

    prepaid_job, updated_job = mark_prepaid(db, new_job, created_job)
    check_prepaid(db, prepaid_job, request_id, 1)

    started_job, updated_job = mark_started(db, prepaid_job, updated_job)
    check_started(db, started_job, request_id, 1)

    non_started_cascade_tasks = crud.cascade.get_all_in_request_not_started(db=db, request_id=request_id)
    assert len(non_started_cascade_tasks) == 0

    crud.cascade.remove(db=db, id=created_job.id)


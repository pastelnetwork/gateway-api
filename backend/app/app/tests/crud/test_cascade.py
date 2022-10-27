import random
import time

from sqlalchemy.orm import Session

from app import crud
from app.schemas.cascade import CascadeCreate, CascadeUpdate
from app.models.cascade import Cascade
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string, random_mime_type


def create_cascade_task(db: Session, *, work_id: str = None) -> (CascadeCreate, Cascade):
    local_file_name = random_lower_string()
    local_file_type = random_mime_type()
    local_file_path = random_lower_string()
    if not work_id:
        work_id = random_lower_string()
    ticket_id = random_lower_string()
    task_id = random_lower_string()
    file_id = random_lower_string()
    # wn_fee = random.randint(100, 1000),
    # height = random.randint(100000, 1000000),

    new_cascade_job = CascadeCreate(
        original_file_name=local_file_name,
        original_file_content_type=local_file_type,
        original_file_local_path=local_file_path,
        work_id=work_id,
        ticket_id=ticket_id,
        last_task_id=task_id,
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
    assert cascade_job_1.work_id == cascade_job_2.work_id
    assert cascade_job_1.ticket_id == cascade_job_2.ticket_id
    assert cascade_job_1.last_task_id == cascade_job_2.last_task_id
    assert cascade_job_1.wn_file_id == cascade_job_2.wn_file_id
    assert cascade_job_1.wn_fee == cascade_job_2.wn_fee
    assert cascade_job_1.height == cascade_job_2.height


# 1
def test_create_cascade_job(db: Session) -> None:
    new_cascade_task, created_cascade_task = create_cascade_task(db)
    assert_cascade_jobs(new_cascade_task, created_cascade_task)


# 2
def test_get_cascade_job_by_task_id(db: Session) -> None:
    new_cascade_task, created_cascade_task = create_cascade_task(db)
    stored_cascade_task = crud.cascade.get_by_task_id(db=db, task_id=new_cascade_task.last_task_id)
    assert_cascade_jobs(new_cascade_task, stored_cascade_task)


# 3
def test_get_cascade_job_by_work_id_and_name(db: Session) -> None:
    work_id = random_lower_string()
    new_cascade_task1, created_cascade_task1 = create_cascade_task(db, work_id=work_id)
    new_cascade_task2, created_cascade_task2 = create_cascade_task(db, work_id=work_id)
    stored_cascade_task1 = crud.cascade.get_by_work_id_and_name(db=db, work_id=work_id,
                                                                file_name=new_cascade_task1.original_file_name)
    assert_cascade_jobs(new_cascade_task1, stored_cascade_task1)
    stored_cascade_task2 = crud.cascade.get_by_work_id_and_name(db=db, work_id=work_id,
                                                                file_name=new_cascade_task2.original_file_name)
    assert_cascade_jobs(new_cascade_task2, stored_cascade_task2)


# 4
def test_get_multiple_cascade_job(db: Session) -> None:
    work_id = random_lower_string()
    new_cascade_task1, created_cascade_task1 = create_cascade_task(db, work_id=work_id)
    new_cascade_task2, created_cascade_task2 = create_cascade_task(db, work_id=work_id)
    stored_cascade_tasks = crud.cascade.get_all_in_work(db=db, work_id=work_id)
    assert_cascade_jobs(new_cascade_task1, stored_cascade_tasks[0])
    assert_cascade_jobs(new_cascade_task2, stored_cascade_tasks[1])


# 5
def test_get_non_started(db: Session) -> None:
    work_id = random_lower_string()
    new_cascade_task1, created_cascade_task1 = create_cascade_task(db, work_id=work_id)
    new_cascade_task2, created_cascade_task2 = create_cascade_task(db, work_id=work_id)
    stored_cascade_tasks = crud.cascade.get_all_in_work_not_started(db=db, work_id=work_id)
    assert_cascade_jobs(new_cascade_task1, stored_cascade_tasks[0])
    assert_cascade_jobs(new_cascade_task2, stored_cascade_tasks[1])


def mark_prepaid(db: Session, new_job: CascadeCreate, created_job: Cascade) -> (CascadeCreate, Cascade):
    new_task_id = random_lower_string()
    print(f"new_task_id: {new_task_id}")
    burn_txid = random_lower_string()
    upd = {"burn_txid": burn_txid, "last_task_id": new_task_id}
    updated_job = crud.cascade.update(db, db_obj=created_job, obj_in=upd)
    new_job.last_task_id = new_task_id
    print(f"updated_job: {updated_job.last_task_id}; new_job: {new_job.last_task_id}")
    assert_cascade_jobs(new_job, updated_job)
    assert updated_job.burn_txid == burn_txid
    return new_job, updated_job


def test_prepaid(db: Session, prepaid_job: CascadeCreate, work_id: str, num: int):
    prepaid_cascade_tasks = crud.cascade.get_all_in_work_prepaid(db=db, work_id=work_id)
    assert len(prepaid_cascade_tasks) == num
    assert_cascade_jobs(prepaid_job, prepaid_cascade_tasks[0])


def mark_started(db: Session, new_job: CascadeCreate, created_job: Cascade) -> (CascadeCreate, Cascade):
    new_task_id = random_lower_string()
    wn_task_id = random_lower_string()
    upd = {"wn_task_id": wn_task_id, "last_task_id": new_task_id}
    updated_job = crud.cascade.update(db, db_obj=created_job, obj_in=upd)
    new_job.last_task_id = new_task_id
    assert_cascade_jobs(new_job, updated_job)
    assert updated_job.wn_task_id == wn_task_id
    return new_job, updated_job


def test_started(db: Session, started_job: CascadeCreate, work_id: str, num: int):
    prepaid_cascade_tasks = crud.cascade.get_all_in_work_started(db=db, work_id=work_id)
    assert len(prepaid_cascade_tasks) == num
    assert_cascade_jobs(started_job, prepaid_cascade_tasks[0])


# 6
def test_update_and_get(db: Session) -> None:
    work_id = random_lower_string()
    new_job, created_job = create_cascade_task(db, work_id=work_id)

    prepaid_job, updated_job = mark_prepaid(db, new_job, created_job)
    test_prepaid(db, prepaid_job, work_id, 1)

    started_job, updated_job = mark_started(db, prepaid_job, updated_job)
    test_started(db, started_job, work_id, 1)

    non_started_cascade_tasks = crud.cascade.get_all_in_work_not_started(db=db, work_id=work_id)
    assert len(non_started_cascade_tasks) == 0



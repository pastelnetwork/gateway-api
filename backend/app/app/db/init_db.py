from sqlalchemy.orm import Session
from app import crud, schemas
from app.db import base  # noqa: F401


def init_db(db: Session, superuser_email: str, superuser_password: str) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next line
    # Base.metadata.create_all(bind=engine)

    if not superuser_email or not superuser_password:
        raise ValueError("Superuser email and password must be provided")

    user = crud.user.get_by_email(db, email=superuser_email)
    if not user:
        user_in = schemas.UserCreate(
            email=superuser_email,
            password=superuser_password,
            is_superuser=True,
        )
        user = crud.user.create(db, obj_in=user_in)  # noqa: F841

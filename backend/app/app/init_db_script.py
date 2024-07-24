import argparse
import logging
from app.db.init_db import init_db
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(superuser_email: str, superuser_password: str) -> None:
    logger.info("Creating initial data")
    db = SessionLocal()
    init_db(db, superuser_email, superuser_password)
    logger.info("Initial data created")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the database with a superuser.")
    parser.add_argument("--email", required=True, help="Superuser email")
    parser.add_argument("--password", required=True, help="Superuser password")
    args = parser.parse_args()

    main(args.email, args.password)
import os
import json
import requests
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from pydantic import BaseSettings, validator
from typing import Any, Dict, Optional


class Settings(BaseSettings):
    AWS_SECRET_MANAGER_REGION: str
    AWS_SECRET_MANAGER_RDS_CREDENTIALS: str
    SQLALCHEMY_DATABASE_URI: Optional[dict] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v

        if values.get("AWS_SECRET_MANAGER_RDS_CREDENTIALS") and values.get("AWS_SECRET_MANAGER_REGION"):
            return get_database_url_from_aws_secret_manager(
                values.get("AWS_SECRET_MANAGER_REGION"),
                values.get("AWS_SECRET_MANAGER_RDS_CREDENTIALS"),
            )

        return None


def get_secret_string_from_aws_secret_manager(region_name, secret_id) -> Any:
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_id)
    except ClientError as e:
        raise e

    secret_json = json.loads(get_secret_value_response["SecretString"])
    if not secret_json:
        raise ValueError(f"Cannot get {secret_id} values from AWS secret manager")
    return secret_json


def get_database_url_from_aws_secret_manager(region_name, secret_id) -> Any:
    secret_json = get_secret_string_from_aws_secret_manager(region_name, secret_id)
    return {
        "dbname": secret_json['dbname'],
        "user": secret_json['username'],
        "password": secret_json['password'],
        "host": secret_json['host'],
        "port": str(secret_json['port'])
    }


def check_ipfs_links(db_conn):
    cur = db_conn.cursor()

    cur.execute("SELECT stored_file_ipfs_link FROM cascade WHERE process_status = 'DONE' AND stored_file_ipfs_link IS NOT NULL AND stored_file_ipfs_link != '' ORDER BY updated_at DESC")

    rows = cur.fetchall()

    print(f"checking {len(rows)} links")

    blacklist = []
    if os.path.exists('blacklist.txt'):
        with open('blacklist.txt', 'r') as f:
            blacklist = f.read().splitlines()
    print(f"blacklist: {len(blacklist)}")

    # if not os.path.isfile('unavailable.txt'):
    #     open('unavailable.txt', 'w').close()

    i = 0
    for row in rows:
        link = row[0]
        if link not in blacklist:
            print(f"{i} Checking {link}...", end='\r')
            try:
                response = requests.get(f"https://ipfs.io/ipfs/{link}", timeout=10)
                if response.status_code == 200:
                    print(f"{i} Checking {link}... Available")
                    continue
            except requests.exceptions.Timeout:
                pass
            
            print(f"{i} Checking {link}... Unavailable")
            with open('unavailable.txt', 'a') as f:
                f.write(f"{link}\n")
            i += 1


if __name__ == "__main__":
    load_dotenv()

    settings = Settings()
    db_params = settings.SQLALCHEMY_DATABASE_URI
    conn = psycopg2.connect(
        dbname=db_params["dbname"],
        user=db_params["user"],
        password=db_params["password"],
        host=db_params["host"],
        port=db_params["port"]
    )

    print("connected to db")

    check_ipfs_links(conn)

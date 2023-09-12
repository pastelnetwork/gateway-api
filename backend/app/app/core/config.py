import secrets
import boto3
from botocore.exceptions import ClientError
import json

from functools import lru_cache
from dotenv import find_dotenv
from pydantic import BaseSettings, EmailStr, PostgresDsn, validator, AnyHttpUrl
from typing import Any, Dict, Optional, List, Union


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pastel Network API Gateway"
    PROJECT_DESCRIPTION: str = "Pastel Network’s Gateway provides Web3 developers with easy, robust, " \
                               "and reliable access to the Pastel Network and its underlying protocols " \
                               "via a lightweight, centralized service.<br/> " \
                               "For more information on Pastel Network, review our " \
                               "<a href=https://docs.pastel.network/introduction/pastel-overview>documentation</a>."
    SERVER_HOST: AnyHttpUrl

    AWS_SECRET_MANAGER_REGION: Optional[str] = None
    AWS_SECRET_MANAGER_PASTEL_IDS: Optional[str] = None
    AWS_SECRET_MANAGER_RDS_CREDENTIALS: Optional[str] = None
    AWS_SECRET_MANAGER_SMTP_SECRETS: Optional[str] = None

    API_V1_STR: str = "/api/v1"
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 90 days = 60 days
    API_KEY_EXPIRE_MINUTES: int = 60 * 24 * 90

    # BACKEND_CORS_ORIGINS is a JSON-formatted list of origins
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = None

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    PASTEL_RPC_HOST: Optional[str] = None
    PASTEL_RPC_PORT: Optional[str] = None
    PASTEL_RPC_URL: Optional[str] = None

    @validator("PASTEL_RPC_URL", pre=True)
    def assemble_pastel_rpc_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        else:
            return f"http://{values.get('PASTEL_RPC_HOST') or 'localhost'}:{values.get('PASTEL_RPC_PORT') or '19932'}"

    PASTEL_RPC_USER: str
    PASTEL_RPC_PWD: str

    PASTEL_ID: str
    PASTEL_ID_PASSPHRASE: Optional[str] = None

    @validator("PASTEL_ID_PASSPHRASE", pre=True)
    def get_pastel_id_passphrase(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        if values.get("AWS_SECRET_MANAGER_PASTEL_IDS") and values.get("AWS_SECRET_MANAGER_REGION"):
            secret = get_secret_string_from_aws_secret_manager(
                values.get("AWS_SECRET_MANAGER_REGION"),
                values.get("AWS_SECRET_MANAGER_PASTEL_IDS"))
            return secret[values.get("PASTEL_ID")]

    BURN_ADDRESS: str

    WN_HOST: Optional[str] = None
    WN_BASE_PORT: Optional[str] = None
    WN_BASE_URL: Optional[str] = None

    @validator("WN_BASE_URL", pre=True)
    def assemble_wn_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        else:
            return f"http://{values.get('WN_HOST') or 'localhost'}:{values.get('WN_BASE_PORT') or '8080'}"

    IPFS_HOST: Optional[str] = None
    IPFS_URL: Optional[str] = None

    SCW_ENABLED = False
    SCW_PIN_URL_PREFIX = f"https://api.scaleway.com/ipfs/v1alpha1/regions"
    SCW_PIN_URL_SUFFIX = f"pins/create-by-cid"
    SCW_REGION = "fr-par"
    SCW_SECRET_KEY = "2c95a2f3-802b-4fe2-96c9-374c9974dff9"     # TODO: move to AWS secret manager
    SCW_VOLUME_ID = "4af3da90-2d92-4079-9b95-f5964e5b2c2c"


    @validator("IPFS_URL", pre=True)
    def assemble_ipfs_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        else:
            return f"/dns/{values.get('IPFS_HOST') or 'localhost'}/tcp/5001/http"

    REDIS_HOST: Optional[str] = 'localhost'
    REDIS_PORT: Optional[str] = '6379'
    REDIS_URL: Optional[str] = None

    @validator("REDIS_URL", pre=True)
    def assemble_redis_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        else:
            h = values.get('REDIS_HOST') or 'localhost'
            p = values.get('REDIS_PORT') or '6379'
            return f"redis://{h}:{p}/0"

    FILE_STORAGE: str
    FILE_STORAGE_FOR_RESULTS_SUFFIX: str = "results"
    FILE_STORAGE_FOR_PARSED_RESULTS_SUFFIX: str = "parsed_results"

    NFT_DEFAULT_MAX_FILE_SIZE_FOR_FEE_IN_MB: int = 100
    NFT_THUMBNAIL_SIZE_IN_PIXELS: int = 256
    MAX_SIZE_FOR_PREBURN: int = 20

    POSTGRES_SERVER: Optional[str]
    POSTGRES_USER: Optional[str]
    POSTGRES_PASSWORD: Optional[str]
    POSTGRES_DB: Optional[str]
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v

        if values.get("AWS_SECRET_MANAGER_RDS_CREDENTIALS") and values.get("AWS_SECRET_MANAGER_REGION"):
            return get_database_url_from_aws_secret_manager(
                values.get("AWS_SECRET_MANAGER_REGION"),
                values.get("AWS_SECRET_MANAGER_RDS_CREDENTIALS"),
            )

        if values.get("POSTGRES_SERVER") and values.get("POSTGRES_USER") and values.get("POSTGRES_PASSWORD"):
            return PostgresDsn.build(
                scheme="postgresql",
                user=values.get("POSTGRES_USER"),
                password=values.get("POSTGRES_PASSWORD"),
                host=values.get("POSTGRES_SERVER"),
                path=f"/{values.get('POSTGRES_DB') or ''}",
            )

        return None

    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None
    ALERTS_EMAIL_RCPT: Optional[EmailStr] = None

    @validator("SMTP_PASSWORD", pre=True)
    def get_smtp_pwd(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        if values.get("AWS_SECRET_MANAGER_SMTP_SECRETS") and values.get("AWS_SECRET_MANAGER_REGION"):
            secret = get_secret_string_from_aws_secret_manager(
                values.get("AWS_SECRET_MANAGER_REGION"),
                values.get("AWS_SECRET_MANAGER_SMTP_SECRETS"))
            return secret["password"]

    @validator("EMAILS_FROM_NAME")
    def get_project_name(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if not v:
            return values["PROJECT_NAME"]
        return v

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48
    EMAIL_TEMPLATES_DIR: str = "email-templates"
    EMAILS_ENABLED: bool = False

    @validator("EMAILS_ENABLED", pre=True)
    def get_emails_enabled(cls, v: bool, values: Dict[str, Any]) -> bool:
        return bool(
            values.get("SMTP_HOST")
            and values.get("SMTP_PORT")
            and values.get("EMAILS_FROM_EMAIL")
        )

    FRONTEND_URL: Optional[AnyHttpUrl] = None

    FIRST_SUPERUSER: Optional[EmailStr]
    FIRST_SUPERUSER_PASSWORD: Optional[str]
    USERS_OPEN_REGISTRATION: bool = False
    RETURN_DETAILED_WN_ERROR: bool = True

    # registration_helpers
    REGISTRATION_FINISHER_INTERVAL: float = 600.0
    REGISTRATION_RE_PROCESSOR_INTERVAL: float = 700.0

    # scheduled_tools
    FEE_PRE_BURNER_INTERVAL: float = 500.0
    REG_TICKETS_FINDER_INTERVAL: float = 150.0
    TICKET_ACTIVATOR_INTERVAL: float = 500.0
    WATCHDOG_INTERVAL: float = 1200.0

    # celery config
    # 10 retries with exponential delays starting from 180 seconds, capped at 10 hours will take ~32 hours
    REGISTER_FILE_RETRY_BACKOFF: int = 180
    REGISTER_FILE_RETRY_BACKOFF_MAX: int = 36000
    REGISTER_FILE_MAX_RETRIES: int = 15
    REGISTER_FILE_SOFT_TIME_LIMIT: int = 300
    REGISTER_FILE_TIME_LIMIT: int = 360

    PREBURN_FEE_RETRY_BACKOFF: int = 180
    PREBURN_FEE_RETRY_BACKOFF_MAX: int = 36000
    PREBURN_FEE_MAX_RETRIES: int = 15
    PREBURN_FEE_SOFT_TIME_LIMIT: int = 300
    PREBURN_FEE_TIME_LIMIT: int = 360

    PROCESS_RETRY_BACKOFF: int = 180
    PROCESS_RETRY_BACKOFF_MAX: int = 36000
    PROCESS_MAX_RETRIES: int = 15
    PROCESS_SOFT_TIME_LIMIT: int = 300
    PROCESS_TIME_LIMIT: int = 360

    RE_REGISTER_FILE_RETRY_BACKOFF: int = 180
    RE_REGISTER_FILE_RETRY_BACKOFF_MAX: int = 36000
    RE_REGISTER_FILE_MAX_RETRIES: int = 15
    RE_REGISTER_FILE_SOFT_TIME_LIMIT: int = 300
    RE_REGISTER_FILE_TIME_LIMIT: int = 360

    COLLECTION_REGISTER_RETRY_BACKOFF: int = 180
    COLLECTION_REGISTER_RETRY_BACKOFF_MAX: int = 36000
    COLLECTION_REGISTER_MAX_RETRIES: int = 15
    COLLECTION_REGISTER_SOFT_TIME_LIMIT: int = 300
    COLLECTION_REGISTER_TIME_LIMIT: int = 360

    REGISTRATION_RE_PROCESSOR_LIMIT: int = 10

    class Config:
        env_file = find_dotenv(usecwd=True)
        print("env_file is "+env_file)


def get_secret_string_from_aws_secret_manager(region_name, secret_id) -> Any:
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_id)
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret_json = json.loads(get_secret_value_response["SecretString"])
    if not secret_json:
        raise ValueError(f"Cannot get {secret_id} values from AWS secret manager")
    return secret_json


def get_database_url_from_aws_secret_manager(region_name, secret_id) -> Any:
    secret_json = get_secret_string_from_aws_secret_manager(region_name, secret_id)

    return PostgresDsn.build(
        scheme="postgresql",
        user=secret_json["username"],
        port=str(secret_json["port"]),
        password=secret_json["password"],
        host=secret_json["host"],
        path=f"/{secret_json['dbname']}",
    )


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

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

    API_V1_STR: str = "/api/v1"
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 90 days = 60 days
    API_KEY_EXPIRE_MINUTES: int = 60 * 24 * 90

    # BACKEND_CORS_ORIGINS is a JSON-formatted list of origins
    # e.g: '["http://localhost", "http://localhost:4200", "http://localhost:3000", \
    # "http://localhost:8080", "http://local.dockertoolbox.tiangolo.com"]'
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost",
                                              "http://localhost:8081",
                                              "http://100.26.28.34",
                                              "http://100.26.28.34:8081",
                                              "https://smartmint.pastel.network",
                                              "https://smartmintdev.pastel.network"
                                              ]

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
    PASSPHRASE: str

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

    AWS_SECRET_MANAGER_REGION: Optional[str] = None
    AWS_SECRET_MANAGER_SECRET_NAME: Optional[str] = None

    POSTGRES_SERVER: Optional[str]
    POSTGRES_USER: Optional[str]
    POSTGRES_PASSWORD: Optional[str]
    POSTGRES_DB: Optional[str]
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v

        if values.get("AWS_SECRET_MANAGER_SECRET_NAME") and values.get("AWS_SECRET_MANAGER_REGION"):
            return get_database_url_from_aws_secret_manager(
                values.get("AWS_SECRET_MANAGER_REGION"),
                values.get("AWS_SECRET_MANAGER_SECRET_NAME"),
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

    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    USERS_OPEN_REGISTRATION: bool = False
    RETURN_DETAILED_WN_ERROR: bool = True

    class Config:
        env_file = find_dotenv(usecwd=True)
        print("env_file is "+env_file)


def get_database_url_from_aws_secret_manager(region_name, secret_id) -> PostgresDsn:
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
    secret = json.loads(get_secret_value_response["SecretString"])
    if not secret:
        raise ValueError("Cannot get database values from AWS secret manager")

    return PostgresDsn.build(
        scheme="postgresql",
        user=secret["username"],
        port=str(secret["port"]),
        password=secret["password"],
        host=secret["host"],
        path=f"/{secret['dbname']}",
    )


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

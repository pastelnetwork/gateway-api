import secrets

from functools import lru_cache
from dotenv import find_dotenv
from pydantic import EmailStr, PostgresDsn, field_validator, AnyHttpUrl
from typing import Any, Optional, List, Union, Dict
from pydantic_settings import BaseSettings
from pydantic_core.core_schema import FieldValidationInfo

from app.utils.aws import get_secret_string_from_secret_manager, get_database_url_from_secret_manager


class Settings(BaseSettings):
    PROJECT_NAME: str = "Pastel Network API Gateway"
    PROJECT_DESCRIPTION: str = "Pastel Network’s Gateway provides Web3 developers with easy, robust, " \
                               "and reliable access to the Pastel Network and its underlying protocols " \
                               "via a lightweight, centralized service.<br/> " \
                               "For more information on Pastel Network, review our " \
                               "<a href=https://docs.pastel.network/introduction/pastel-overview>documentation</a>."
    PROJECT_VERSION: str = "1.0.0"
    SERVER_HOST: AnyHttpUrl

    STACK_NAME: str = "pastel-network-api-gateway"

    AWS_SECRET_MANAGER_REGION: Optional[str] = None
    AWS_SECRET_MANAGER_PASTEL_IDS: Optional[str] = None
    AWS_SECRET_MANAGER_RDS_CREDENTIALS: Optional[str] = None
    AWS_SECRET_MANAGER_RDS_PARAMETERS: Optional[str] = None
    AWS_SECRET_MANAGER_SMTP_SECRETS: Optional[str] = None

    API_V1_STR: str = "/api/v1"
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 90 days = 60 days
    API_KEY_EXPIRE_MINUTES: int = 60 * 24 * 90

    # BACKEND_CORS_ORIGINS is a JSON-formatted list of origins
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = None

    @field_validator("BACKEND_CORS_ORIGINS", mode='before')
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    PASTEL_RPC_HOST: Optional[str] = None
    PASTEL_RPC_PORT: Optional[str] = None
    PASTEL_RPC_URL: Optional[str] = None

    @field_validator("PASTEL_RPC_URL", mode='before')
    def assemble_pastel_rpc_url(cls, v: Optional[str], info: FieldValidationInfo) -> str:
        if isinstance(v, str):
            return v
        else:
            host = info.data['PASTEL_RPC_HOST'] if check_parameter('PASTEL_RPC_HOST', info) else 'localhost'
            port = info.data['PASTEL_RPC_PORT'] if check_parameter('PASTEL_RPC_PORT', info) else '19932'
            return f"http://{host}:{port}"

    PASTEL_RPC_USER: str
    PASTEL_RPC_PWD: str

    PASTEL_ID: Optional[str] = None

    BURN_ADDRESS: str
    MAIN_GATEWAY_ADDRESS: Optional[str] = None

    WN_HOST: Optional[str] = None
    WN_BASE_PORT: Optional[str] = None
    WN_BASE_URL: Optional[str] = None

    @field_validator("WN_BASE_URL", mode='before')
    def assemble_wn_url(cls, v: Optional[str], info: FieldValidationInfo) -> str:
        if isinstance(v, str):
            return v
        else:
            host = info.data['WN_HOST'] if check_parameter('WN_HOST', info) else 'localhost'
            port = info.data['WN_BASE_PORT'] if check_parameter('WN_BASE_PORT', info) else '8080'
            return f"http://{host}:{port}"

    IPFS_HOST: Optional[str] = None
    IPFS_URL: Optional[str] = None

    SCW_ENABLED: bool = False
    SCW_PIN_URL_PREFIX: Optional[str] = f"https://api.scaleway.com/ipfs/v1alpha1/regions"
    SCW_PIN_URL_SUFFIX: Optional[str] = f"pins/create-by-cid"
    SCW_REGION: Optional[str] = "fr-par"
    SCW_SECRET_KEY: Optional[str] = "2c95a2f3-802b-4fe2-96c9-374c9974dff9"     # TODO: move to AWS secret manager
    SCW_VOLUME_ID: Optional[str] = "4af3da90-2d92-4079-9b95-f5964e5b2c2c"

    @field_validator("IPFS_URL", mode='before')
    def assemble_ipfs_url(cls, v: Optional[str], info: FieldValidationInfo) -> str:
        if isinstance(v, str):
            return v
        else:
            host = info.data['IPFS_HOST'] if check_parameter('IPFS_HOST', info) else 'localhost'
            return f"/dns/{host}/tcp/5001/http"

    REDIS_HOST: Optional[str] = 'localhost'
    REDIS_PORT: Optional[str] = '6379'
    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode='before')
    def assemble_redis_url(cls, v: Optional[str], info: FieldValidationInfo) -> str:
        if isinstance(v, str):
            return v
        else:
            host = info.data['REDIS_HOST'] if check_parameter('REDIS_HOST', info) else 'localhost'
            port = info.data['REDIS_PORT'] if check_parameter('REDIS_PORT', info) else '6379'
            return f"redis://{host}:{port}/0"

    FILE_STORAGE: str
    FILE_STORAGE_FOR_RESULTS_SUFFIX: str = "results"
    FILE_STORAGE_FOR_PARSED_RESULTS_SUFFIX: str = "parsed_results"

    NFT_DEFAULT_MAX_FILE_SIZE_FOR_FEE_IN_MB: int = 100
    NFT_THUMBNAIL_SIZE_IN_PIXELS: int = 256
    MAX_SIZE_FOR_PREBURN: int = 20

    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode='after')
    def assemble_db_connection(cls, v: Optional[str], info: FieldValidationInfo) -> Any:
        if isinstance(v, str):
            return v

        if (check_parameter('AWS_SECRET_MANAGER_REGION', info) and
                check_parameter('AWS_SECRET_MANAGER_RDS_CREDENTIALS', info)):
            return get_database_url_from_secret_manager(
                info.data["AWS_SECRET_MANAGER_REGION"],
                info.data["AWS_SECRET_MANAGER_RDS_CREDENTIALS"],
                info.data["AWS_SECRET_MANAGER_RDS_PARAMETERS"]
                if check_parameter('AWS_SECRET_MANAGER_RDS_PARAMETERS', info) else None
            )

        if (check_parameter('POSTGRES_USER', info) and
                check_parameter('POSTGRES_PASSWORD', info) and
                check_parameter('POSTGRES_SERVER', info)):
            return PostgresDsn.build(
                scheme="postgresql",
                username=info.data["POSTGRES_USER"],
                password=info.data["POSTGRES_PASSWORD"],
                host=info.data["POSTGRES_SERVER"],
                path=f"/{info.data['POSTGRES_DB'] if check_parameter('POSTGRES_DB', info) else ''}",
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

    @field_validator("SMTP_PASSWORD", mode='before')
    def get_smtp_pwd(cls, v: Optional[str], info: FieldValidationInfo) -> str:
        if isinstance(v, str):
            return v
        if (check_parameter('AWS_SECRET_MANAGER_REGION', info) and
                check_parameter('AWS_SECRET_MANAGER_SMTP_SECRETS', info)):
            secret = get_secret_string_from_secret_manager(
                info.data["AWS_SECRET_MANAGER_REGION"],
                info.data["AWS_SECRET_MANAGER_SMTP_SECRETS"])
            return secret["password"]

    @field_validator("EMAILS_FROM_NAME", mode='before')
    def get_project_name(cls, v: Optional[str], info: FieldValidationInfo) -> str:
        if not v:
            return info.data["PROJECT_NAME"]
        return v

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48
    EMAIL_TEMPLATES_DIR: str = "email-templates"
    EMAILS_ENABLED: bool = False

    @field_validator("EMAILS_ENABLED", mode='before')
    def get_emails_enabled(cls, v: bool, info: FieldValidationInfo) -> bool:
        return bool(
            check_parameter('SMTP_HOST', info) and
            check_parameter('SMTP_PORT', info) and
            check_parameter('EMAILS_FROM_EMAIL', info)
        )

    FRONTEND_URL: Optional[AnyHttpUrl] = None

    FIRST_SUPERUSER: Optional[EmailStr] = None
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None
    USERS_OPEN_REGISTRATION: bool = False
    RETURN_DETAILED_WN_ERROR: bool = True

    # registration_helpers
    REGISTRATION_FINISHER_INTERVAL: float = 600.0
    REGISTRATION_RE_PROCESSOR_INTERVAL: float = 700.0

    # scheduled_tools
    FEE_PRE_BURNER_ENABLED: bool = True
    FEE_PRE_BURNER_INTERVAL: float = 500.0
    FEE_PRE_BURNER_RELEASE_NON_USED: bool = True
    FEE_PRE_BURNER_CHECK_NEW: bool = True

    REG_TICKETS_FINDER_ENABLED: bool = True
    REG_TICKETS_FINDER_INTERVAL: float = 150.0
    TICKET_ACTIVATOR_INTERVAL: float = 500.0
    TICKET_ACTIVATOR_ENABLED: bool = True
    WATCHDOG_INTERVAL: float = 1200.0
    WATCHDOG_ENABLED: bool = True

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

    # ticket prices
    TICKET_PRICE_PASTELID: int = 1000
    TICKET_PRICE_NFT_REG: int = 10        # + 10% of reg fee
    TICKET_PRICE_NFT_ACT: int = 10        # + 90% of reg fee
    TICKET_PRICE_ACTION_REG: int = 10     # + 20% of reg fee
    TICKET_PRICE_ACTION_ACT: int = 10     # + 80% of reg fee
    TICKET_PRICE_COLLECTION_REG: int = 10
    TICKET_PRICE_COLLECTION_ACT: int = 10
    TICKET_PRICE_OFFER: int = 10          # OR 2% of Offered price
    TICKET_PRICE_ACCEPT: int = 100        # OR 1% of Offered price
    TICKET_PRICE_TRANSFER: int = 10
    TICKET_PRICE_MIN_BALANCE: int = 1000  # used for balance check, just in case, so value is arbitrary

    PRE_BURN_TX_CONFIRMATIONS: int = 3

    class Config:
        env_file = find_dotenv(usecwd=True)
        print("env_file is "+env_file)


def check_parameter(name: str, info: FieldValidationInfo) -> bool:
    return name in info.data and info.data[name]


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

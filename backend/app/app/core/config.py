import secrets
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

    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[str] = None
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

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

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
    EMAIL_TEMPLATES_DIR: str = "/app/app/email-templates/build"
    EMAILS_ENABLED: bool = False

    @validator("EMAILS_ENABLED", pre=True)
    def get_emails_enabled(cls, v: bool, values: Dict[str, Any]) -> bool:
        return bool(
            values.get("SMTP_HOST")
            and values.get("SMTP_PORT")
            and values.get("EMAILS_FROM_EMAIL")
        )

    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    USERS_OPEN_REGISTRATION: bool = False
    RETURN_DETAILED_WN_ERROR: bool = True

    class Config:
        env_file = find_dotenv(usecwd=True)
        print("env_file is "+env_file)


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

from functools import lru_cache
from dotenv import find_dotenv
from pydantic import BaseSettings, EmailStr, PostgresDsn, validator
from typing import Any, Dict, Optional


class Settings(BaseSettings):
    APP_NAME: str = "Pastel Open API"

    PASTEL_RPC_USER: str
    PASTEL_RPC_PWD: str
    PASTEL_ID: str
    PASSPHRASE: str

    WN_BASE_URL: str = "http://127.0.0.1:8080"
    BASE_CASCADE_URL = f"{WN_BASE_URL}/openapi/cascade"
    BASE_SENSE_URL = f"{WN_BASE_URL}/openapi/sense"

    FILE_STORAGE: str

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

    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    class Config:
        env_file = find_dotenv(usecwd=True)
        print("env_file is "+env_file)


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

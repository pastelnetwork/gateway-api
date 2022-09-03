from functools import lru_cache
from pydantic import BaseSettings


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

    SQLALCHEMY_DATABASE_URI: str

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

from functools import lru_cache
from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Pastel Open API"

    pastel_rpc_user: str
    pastel_rpc_pwd: str
    wn_url: str = "http://127.0.0.1:8080"
    pastel_id: str
    passphrase: str

    base_cascade_url = f"{wn_url}/openapi/cascade"
    base_sense_url = f"{wn_url}/openapi/sense"

    file_storage: str

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()

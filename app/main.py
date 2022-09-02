import uvicorn as uvicorn
from fastapi import FastAPI

from config.celery_utils import create_celery
from routers import cascade


def create_app() -> FastAPI:
    current_app = FastAPI(title="Pastel Open API",
                          description="Pastel Open API",
                          version="0.0.1", )

    current_app.celery_app = create_celery()
    current_app.include_router(cascade.router)
    return current_app


app = create_app()
celery = app.celery_app


if __name__ == "__main__":
    uvicorn.run("main:app", port=9000, reload=True)

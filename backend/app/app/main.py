import uvicorn as uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.celery_utils import create_celery
from app.api.api_v1.api import api_router


def create_app() -> FastAPI:
    current_app = FastAPI(title=settings.PROJECT_NAME,
                          description=settings.PROJECT_DESCRIPTION,
                          openapi_url=f"{settings.API_V1_STR}/openapi.json",
                          docs_url="/", )

    from app.core.logging import configure_logging
    configure_logging()

    current_app.celery_app = create_celery()
    current_app.include_router(api_router, prefix=settings.API_V1_STR)

    if settings.BACKEND_CORS_ORIGINS:
        current_app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    return current_app


app = create_app()
celery = app.celery_app


if __name__ == "__main__":
    uvicorn.run("main:app", port=9000, reload=True)

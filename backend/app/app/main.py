import uvicorn as uvicorn
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.celery_utils import create_celery
from app.api.api_v1.api import api_router


def create_app() -> FastAPI:
    current_app = FastAPI(title=settings.PROJECT_NAME,
                          description=settings.PROJECT_DESCRIPTION,
                          openapi_url=f"{settings.API_V1_STR}/pastel_gateway_api.json",
                          docs_url="/",
                          version=settings.PROJECT_VERSION)

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


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):

    from app.schemas import RequestResult, ResultRegistrationResult, Status
    response_content = RequestResult(
        request_id="NONE",
        request_status=Status.FAILED,
        results=[
            ResultRegistrationResult(
                result_status=Status.FAILED,
                error=exc.detail)
        ]
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(response_content, exclude_none=True)
    )


if __name__ == "__main__":
    if settings.ACCOUNT_MANAGER_ENABLED:  # throw and exception if account manager is enabled
        raise Exception("Account manager and Gateway API Server can't be enabled at the same time")

    uvicorn.run("main:app", port=9000, reload=True)

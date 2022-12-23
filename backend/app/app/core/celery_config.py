import os
from functools import lru_cache
from kombu import Queue
from app.core.config import settings


def route_task(name, args, kwargs, options, task=None, **kw):
    if ":" in name:
        queue, _ = name.split(":")
        return {"queue": queue}
    return {"queue": "celery"}


class BaseConfig:
    broker_url: settings.REDIS_URL
    result_backend: settings.REDIS_URL

    task_queues: list = (
        # default queue
        Queue("celery"),
        # custom queue
        Queue("cascade"),
        Queue("sense"),
    )

    task_routes = (route_task,)


class DevelopmentConfig(BaseConfig):
    pass


@lru_cache()
def get_settings():
    config_cls_dict = {
        "development": DevelopmentConfig,
    }
    config_name = os.environ.get("CELERY_CONFIG", "development")
    config_cls = config_cls_dict[config_name]
    return config_cls()


settings = get_settings()

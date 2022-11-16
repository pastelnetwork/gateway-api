from celery import current_app as current_celery_app

from .celery_config import settings
import app.celery_tasks.scheduled   # MUST be here for beat to work


def create_celery():
    celery_app = current_celery_app
    celery_app.config_from_object(settings, namespace='CELERY')
    celery_app.conf.update(task_track_started=True)
    celery_app.conf.update(task_serializer='pickle')
    celery_app.conf.update(result_serializer='pickle')
    celery_app.conf.update(accept_content=['pickle', 'json'])
    celery_app.conf.update(result_expires=200)
    celery_app.conf.update(result_persistent=True)
    celery_app.conf.update(worker_send_task_events=False)
    celery_app.conf.update(worker_prefetch_multiplier=1)
    celery_app.conf.update(celery_ignore_result=False)
    celery_app.conf.update(celery_task_always_eager=True)

    celery_app.conf.beat_schedule = {
        'fee_pre_burner': {
            'task': 'fee_pre_burner',
            'schedule': 600.0,
        },
        'registration_finisher': {
            'task': 'registration_finisher',
            'schedule': 600.0,
        },
        'registration_re_processor': {
            'task': 'registration_re_processor',
            'schedule': 60.0,
        },
    }
    celery_app.conf.timezone = 'UTC'

    return celery_app

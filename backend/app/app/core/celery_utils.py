from celery import current_app as current_celery_app

#!!!!!! MUST be here for beat to work - DO NOT REMOVE
import app.celery_tasks.scheduled
import app.celery_tasks.registration_helpers
#!!!!!! MUST be here for beat to work - DO NOT REMOVE

from .celery_config import settings as celery_settings
from app.core.config import settings as app_settings


def create_celery():
    celery_app = current_celery_app
    celery_app.config_from_object(celery_settings, namespace='CELERY')
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
    celery_app.conf.update(worker_max_tasks_per_child=100)

    celery_app.conf.beat_schedule = {
        'registration_helpers_registration_finisher': {
            'task': 'registration_helpers:registration_finisher',
            'schedule': app_settings.REGISTRATION_FINISHER_INTERVAL,
        },
        'registration_helpers_registration_re_processor': {
            'task': 'registration_helpers:registration_re_processor',
            'schedule': app_settings.REGISTRATION_RE_PROCESSOR_INTERVAL,
        },
        'scheduled_tools_fee_pre_burner': {
            'task': 'scheduled_tools:fee_pre_burner',
            'schedule': app_settings.FEE_PRE_BURNER_INTERVAL,
        },
        'scheduled_tools_reg_tickets_finder': {
            'task': 'scheduled_tools:reg_tickets_finder',
            'schedule': app_settings.REG_TICKETS_FINDER_INTERVAL,
        },
        'scheduled_tools_ticket_activator': {
            'task': 'scheduled_tools:ticket_activator',
            'schedule': app_settings.TICKET_ACTIVATOR_INTERVAL,
        },
        'scheduled_tools_watchdog': {
            'task': 'scheduled_tools:watchdog',
            'schedule': app_settings.WATCHDOG_INTERVAL,
        },
    }
    celery_app.conf.timezone = 'UTC'

    return celery_app

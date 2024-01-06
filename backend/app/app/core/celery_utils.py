from celery import current_app as current_celery_app

#!!!!!! MUST be here for beat to work - DO NOT REMOVE
import app.celery_tasks.scheduled
import app.celery_tasks.registration_helpers
import app.celery_tasks.account_manager
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
    celery_app.conf.update(worker_send_task_events=True)
    celery_app.conf.update(worker_prefetch_multiplier=10)
    celery_app.conf.update(celery_ignore_result=False)
    celery_app.conf.update(celery_task_always_eager=False)
    celery_app.conf.update(worker_max_tasks_per_child=100)

    celery_app.conf.beat_schedule = {}
    if app_settings.REGISTRATION_FINISHER_ENABLED and not app_settings.ACCOUNT_MANAGER_ENABLED:
        celery_app.conf.beat_schedule.update(
            {
                'registration_helpers_registration_finisher': {
                    'task': 'registration_helpers:registration_finisher',
                    'schedule': app_settings.REGISTRATION_FINISHER_INTERVAL,
                }
            }
        )

    if app_settings.REGISTRATION_RE_PROCESSOR_ENABLED and not app_settings.ACCOUNT_MANAGER_ENABLED:
        celery_app.conf.beat_schedule.update(
            {
                'registration_helpers_registration_re_processor': {
                    'task': 'registration_helpers:registration_re_processor',
                    'schedule': app_settings.REGISTRATION_RE_PROCESSOR_INTERVAL,
                }
            }
        )

    if app_settings.FEE_PRE_BURNER_ENABLED and not app_settings.ACCOUNT_MANAGER_ENABLED:
        celery_app.conf.beat_schedule.update(
            {
                'scheduled_tools_fee_pre_burner': {
                    'task': 'scheduled_tools:fee_pre_burner',
                    'schedule': app_settings.FEE_PRE_BURNER_INTERVAL,
                }
            }
        )
    if app_settings.TICKET_ACTIVATOR_ENABLED and not app_settings.ACCOUNT_MANAGER_ENABLED:
        celery_app.conf.beat_schedule.update(
            {
                'scheduled_tools_ticket_activator': {
                    'task': 'scheduled_tools:ticket_activator',
                    'schedule': app_settings.TICKET_ACTIVATOR_INTERVAL,
                }
            }
        )

    if app_settings.REG_TICKETS_FINDER_ENABLED and not app_settings.ACCOUNT_MANAGER_ENABLED:
        celery_app.conf.beat_schedule.update(
            {
                'scheduled_tools_reg_tickets_finder': {
                    'task': 'scheduled_tools:reg_tickets_finder',
                    'schedule': app_settings.REG_TICKETS_FINDER_INTERVAL,
                }
            }
        )

    if app_settings.WATCHDOG_ENABLED and not app_settings.ACCOUNT_MANAGER_ENABLED:
        celery_app.conf.beat_schedule.update(
            {
                'scheduled_tools_watchdog': {
                    'task': 'scheduled_tools:watchdog',
                    'schedule': app_settings.WATCHDOG_INTERVAL,
                }
            }
        )

    if app_settings.ACCOUNT_MANAGER_ENABLED:
        if (app_settings.REGISTRATION_FINISHER_ENABLED or
                app_settings.REGISTRATION_RE_PROCESSOR_ENABLED or
                app_settings.FEE_PRE_BURNER_ENABLED or
                app_settings.TICKET_ACTIVATOR_ENABLED or
                app_settings.REG_TICKETS_FINDER_ENABLED or
                app_settings.WATCHDOG_ENABLED):
            raise Exception("Account Manager and Registration Finisher/Re-Processor/Fee Pre-Burner/"
                            "Ticket Activator/Reg Tickets Finder/Watchdog cannot be enabled at the same time")

        celery_app.conf.beat_schedule.update(
            {
                'account_manager_address_maker': {
                    'task': 'account_manager:address_maker',
                    'schedule': app_settings.ACCOUNT_MANAGER_ADDRESS_MAKER_INTERVAL,
                },
                'account_manager_balancer': {
                    'task': 'account_manager:balancer',
                    'schedule': app_settings.ACCOUNT_MANAGER_BALANCER_INTERVAL,
                }

            }
        )

    celery_app.conf.timezone = 'UTC'

    return celery_app

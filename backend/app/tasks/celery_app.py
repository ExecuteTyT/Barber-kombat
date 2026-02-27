"""Celery application instance."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "barber_kombat",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "poll-yclients-every-10-min": {
        "task": "poll_yclients",
        "schedule": crontab(minute="*/10"),
    },
    "full-sync-daily-4am": {
        "task": "full_sync_yclients",
        "schedule": crontab(hour=4, minute=0),
    },
    "report-daily-evening": {
        "task": "generate_daily_reports",
        "schedule": crontab(hour=22, minute=30),
    },
    "report-day-to-day": {
        "task": "generate_day_to_day",
        "schedule": crontab(hour=11, minute=0),
    },
    "report-monthly": {
        "task": "generate_monthly_reports",
        "schedule": crontab(day_of_month=28, hour=23, minute=0),
    },
    "check-unprocessed-reviews-every-30-min": {
        "task": "check_unprocessed_reviews",
        "schedule": crontab(minute="*/30"),
    },
    # Notification delivery (runs after report generation)
    "deliver-daily-notifications": {
        "task": "deliver_daily_notifications",
        "schedule": crontab(hour=22, minute=35),
    },
    "deliver-day-to-day-notifications": {
        "task": "deliver_day_to_day_notifications",
        "schedule": crontab(hour=11, minute=5),
    },
    "deliver-monthly-notifications": {
        "task": "deliver_monthly_notifications",
        "schedule": crontab(day_of_month=28, hour=23, minute=10),
    },
    # Monthly lifecycle reset (1st of each month at 00:05 Moscow time)
    "monthly-reset": {
        "task": "monthly_reset",
        "schedule": crontab(day_of_month=1, hour=0, minute=5),
    },
}

celery_app.autodiscover_tasks(["app.tasks"])

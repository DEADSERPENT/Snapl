"""
Celery tasks — optional async processing when Redis is configured.

Start worker: celery -A app.tasks worker --loglevel=info
Start beat (periodic):  celery -A app.tasks beat --loglevel=info
"""

from app.config import REDIS_URL

if REDIS_URL:
    from celery import Celery
    from celery.schedules import crontab

    celery_app = Celery("snapl", broker=REDIS_URL, backend=REDIS_URL)
    celery_app.conf.timezone = "UTC"

    # Run cleanup every day at midnight UTC
    celery_app.conf.beat_schedule = {
        "purge-expired-daily": {
            "task": "app.tasks.purge_expired_task",
            "schedule": crontab(hour=0, minute=0),
        },
    }

    @celery_app.task(name="app.tasks.purge_expired_task")
    def purge_expired_task():
        from app.database import SessionLocal
        from app import service
        db = SessionLocal()
        try:
            count = service.purge_expired(db)
            return {"purged": count}
        finally:
            db.close()

    @celery_app.task(name="app.tasks.log_click_task")
    def log_click_task(record_id: int, ip: str, ua_string: str, referrer: str):
        from app import service
        service.log_click_event(record_id, ip, ua_string, referrer)

else:
    # Stub so imports don't fail when Redis is absent
    class _Stub:
        def task(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

    celery_app = _Stub()  # type: ignore

    def purge_expired_task():
        pass

    def log_click_task(*args, **kwargs):
        pass

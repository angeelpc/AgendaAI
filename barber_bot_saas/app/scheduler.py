"""Programador interno: dispara recordatorios y el informe diario sin servicios
externos. Corre en el mismo proceso del backend (APScheduler en segundo plano).

Las horas se configuran con REMINDERS_HOUR / REPORT_HOUR y la zona con SCHED_TZ.
Usa UNA sola réplica del servicio (si tuvieras varias, los jobs se duplicarían).
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(settings.SCHED_TZ)
    except Exception:
        return None


def _job_reminders():
    from .reminders import correr_todas
    try:
        n = correr_todas()
        print(f"[cron] recordatorios enviados: {n}")
    except Exception as e:
        print("[cron] error en recordatorios:", e)


def _job_report():
    from .report import correr
    try:
        correr()
        print("[cron] informe diario ejecutado")
    except Exception as e:
        print("[cron] error en informe:", e)


def build_scheduler() -> BackgroundScheduler:
    """Crea el scheduler con los dos jobs (no lo arranca)."""
    tz = _tz()
    sched = BackgroundScheduler(timezone=tz) if tz else BackgroundScheduler()
    sched.add_job(_job_reminders,
                  CronTrigger(hour=settings.REMINDERS_HOUR, minute=0, timezone=tz),
                  id="reminders", replace_existing=True)
    sched.add_job(_job_report,
                  CronTrigger(hour=settings.REPORT_HOUR, minute=0, timezone=tz),
                  id="report", replace_existing=True)
    return sched


_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = build_scheduler()
    _scheduler.start()
    print(f"[cron] activo -> recordatorios {settings.REMINDERS_HOUR}:00, "
          f"informe {settings.REPORT_HOUR}:00 ({settings.SCHED_TZ})")
    return _scheduler

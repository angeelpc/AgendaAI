from app.scheduler import build_scheduler


def test_scheduler_tiene_jobs():
    s = build_scheduler()
    ids = {j.id for j in s.get_jobs()}
    assert {"reminders", "report"} <= ids

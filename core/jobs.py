"""Fon ishlari (background jobs) menejeri.

Har bir job alohida threadda ishlaydi. Thread server jarayonida yashaydi,
shuning uchun brauzer sahifasi refresh bo'lsa ham ish davom etadi. Holat/loglar
DB dagi FillJob da saqlanadi — sahifa uni poll qilib ko'rsatib turadi.

Turli mahallalar bir vaqtda ishlashi mumkin (har biri alohida thread) — bloklash yo'q.
"""

import threading

from .models import FillJob
from .services.family_filler import run_family_fill
from .services.filler import run_citizen_fill

_lock = threading.Lock()
_jobs = {}  # job_id -> {"thread": Thread, "stop": Event}


def _runner(target, job_id, stop_event):
    try:
        target(job_id, stop_event)
    finally:
        with _lock:
            _jobs.pop(job_id, None)


def start_job(job):
    """FillJob ni fon threadda ishga tushiradi. Allaqachon ishlab tursa — o'zini qaytaradi."""
    with _lock:
        if job.id in _jobs:
            return False
        stop_event = threading.Event()
        if job.section == "citizen":
            target = run_citizen_fill
        elif job.section == "family":
            target = run_family_fill
        else:
            raise ValueError("Noma'lum bo'lim")
        t = threading.Thread(target=_runner, args=(target, job.id, stop_event), daemon=True)
        _jobs[job.id] = {"thread": t, "stop": stop_event}
    FillJob.objects.filter(id=job.id).update(status="running")
    t.start()
    return True


def stop_job(job_id):
    """Ishni to'xtatishni so'raydi (yumshoq to'xtatish)."""
    FillJob.objects.filter(id=job_id).update(status="stopping")
    with _lock:
        info = _jobs.get(job_id)
    if info:
        info["stop"].set()
        return True
    return False


def is_running(job_id):
    with _lock:
        return job_id in _jobs

"""Fuqaro ma'lumotlarini to'ldirish (survey_homes) — push.py mantig'i.

Har bir uy uchun:
  1. kadastr -> mahalla bazasidan pinfl + tug'ilgan sana topiladi.
  2. gcp/pinfl dan shaxs ma'lumoti olinadi (15s throttle).
  3. survey_homes formasi GET qilinadi (formData, survey_uuid saqlanadi).
  4. Identity maydonlar + FOYDALANUVCHI kiritgan static maydonlar bilan to'ldirilib PUT qilinadi.

Static maydonlar foydalanuvchi tomonidan beriladi — kod tasodifiy qiymat o'ylab topmaydi.
"""

from datetime import date

from django.db import close_old_connections

from ..models import CitizenRecord, FillJob
from .api import ApiClient, ApiError
from .pinfl import ddmmyyyy_to_iso

LOG_CAP = 400


def _iso_survey_date(static):
    val = (static.get("survey_date") or "").strip()
    if val:
        return val
    return date.today().isoformat()


def run_citizen_fill(job_id, stop_event):
    close_old_connections()
    job = FillJob.objects.get(id=job_id)
    mahalla = job.mahalla
    static = {**job.static_fields}
    survey_iso = _iso_survey_date(static)
    static.pop("survey_date", None)

    api = ApiClient(mahalla.token)

    # kadastr -> (pinfl, birth_date)
    recmap = {}
    for r in CitizenRecord.objects.filter(mahalla=mahalla):
        if r.pinfl and str(r.pinfl).strip() not in ("", "-"):
            recmap.setdefault(str(r.kadastr), (str(r.pinfl).strip(), r.birth_date))

    done = set(job.done_ids or [])
    stats = {"total": 0, "sent": 0, "skipped": 0, "failed": 0, **(job.stats or {})}
    logs = list(job.logs or [])

    def log(msg):
        logs.append(msg)
        if len(logs) > LOG_CAP:
            del logs[: len(logs) - LOG_CAP]

    def persist(status=None):
        close_old_connections()
        fields = {"stats": stats, "logs": logs, "done_ids": list(done)}
        if status:
            fields["status"] = status
        FillJob.objects.filter(id=job_id).update(**fields)

    def stopping():
        close_old_connections()
        return stop_event.is_set() or \
            FillJob.objects.filter(id=job_id).values_list("status", flat=True).first() == "stopping"

    # "номаълум" ko'cha (id 0) uchun haqiqiy ko'chalar ro'yxati (nolga teng bo'lmagan id'lar).
    # Har bir noma'lum uy NAVBAT bilan (round-robin) shu ko'chalarga taqsimlanadi:
    # 1-uy -> 1-ko'cha, 2-uy -> 2-ko'cha ... tugasa yana 1-ko'chага qaytadi.
    _known = {"ids": None}

    def known_street_ids():
        if _known["ids"] is None:
            ids = []
            try:
                for s in api.streets(mahalla):
                    sid_ = s.get("id")
                    if sid_:  # None ham, 0 ham emas
                        ids.append(sid_)
            except Exception:  # noqa: BLE001
                pass
            _known["ids"] = ids
        return _known["ids"]

    log(f"=== Boshlandi: {mahalla.name} | ko'chalar: {len(job.streets)} ===")
    persist(status="running")

    try:
        for street in job.streets:
            if stopping():
                break
            sid = street.get("id")
            sname = street.get("name", sid)
            log(f"--- Ko'cha: {sname} ---")

            # "номаълум" (id 0) — har bir uy navbat bilan haqiqiy ko'chага (round-robin)
            is_unknown = str(sid) == "0"
            uk_counter = 0
            known_ids = known_street_ids() if is_unknown else []
            if is_unknown:
                if not known_ids:
                    log(f"  '{sname}' o'tkazildi: haqiqiy ko'chalar topilmadi")
                    continue
                log(f"  '{sname}' -> {len(known_ids)} ta ko'chага navbat bilan taqsimlanadi")

            try:
                homes = api.iter_homes(mahalla, sid, stop_event=stop_event)
                for home in homes:
                    if stopping():
                        break
                    cad = str(home.get("cadaster_number"))
                    stats["total"] += 1

                    if cad in done:
                        stats["skipped"] += 1
                        continue

                    # allaqachon pinfl bo'lgan uy -> tegmaymiz
                    db_pinfl = str(home.get("pinfl") or "").strip()
                    if db_pinfl not in ("", "-"):
                        stats["skipped"] += 1
                        done.add(cad)
                        continue

                    rec = recmap.get(cad)
                    if not rec:
                        stats["skipped"] += 1
                        log(f"  SKIP {cad}: bazada pinfl topilmadi")
                        continue
                    pinfl, bdate_db = rec
                    bdate_iso = ddmmyyyy_to_iso(bdate_db)
                    if not bdate_iso:
                        stats["skipped"] += 1
                        log(f"  SKIP {cad}: sana hisoblanmadi")
                        continue

                    next_link = home.get("next_link")
                    try:
                        person = api.gcp(pinfl, bdate_iso, "survey_homes", stop_event=stop_event)
                        if not person:
                            stats["skipped"] += 1
                            log(f"  SKIP {cad}: gcp ma'lumot yo'q")
                            persist()
                            continue
                        form = api.get_form(next_link, stop_event=stop_event)
                        payload = dict(form.get("formData") or {})
                        payload.update({
                            "pinfl": int(pinfl) if pinfl.isdigit() else pinfl,
                            "birth_date": person.get("birth_date") or bdate_iso,
                            "passport": person.get("current_document"),
                            "full_name": person.get("full_name"),
                            "address": person.get("address"),
                            "survey_date": survey_iso,
                            "photo": payload.get("photo") or [],
                        })
                        # FOYDALANUVCHI kiritgan static qiymatlar
                        for k, v in static.items():
                            payload[k] = v

                        # номаълум ko'cha bo'lsa — navbatdagi (round-robin) haqiqiy street_id
                        assigned_street = None
                        if is_unknown:
                            assigned_street = known_ids[uk_counter % len(known_ids)]
                            payload["street_id"] = assigned_street
                            uk_counter += 1

                        api.put_form(next_link, payload, stop_event=stop_event)
                        stats["sent"] += 1
                        done.add(cad)
                        suffix = f" [street_id={assigned_street}]" if assigned_street is not None else ""
                        log(f"  OK {cad} -> {person.get('full_name')}{suffix}")
                    except ApiError:
                        raise  # to'xtatish
                    except Exception as e:  # noqa: BLE001 — bitta uy xatosi butun ishni to'xtatmasin
                        stats["failed"] += 1
                        log(f"  FAIL {cad}: {e}")
                    persist()
            except ApiError:
                break
            except Exception as e:  # noqa: BLE001
                log(f"  Ko'cha xatosi ({sname}): {e}")
                persist()
                continue
    finally:
        final = "stopped" if stopping() else "done"
        log(f"=== Yakun ({final}) | yuborildi: {stats['sent']}, "
            f"o'tkazildi: {stats['skipped']}, xatolik: {stats['failed']} ===")
        persist(status=final)
        close_old_connections()

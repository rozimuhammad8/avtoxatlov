"""Oila a'zolarini kiritish (survey_homes_family) — oila_tarkibi.py mantig'i.

Har bir uy (surveyed) uchun:
  1. egasi pinfl (home pinfl yoki bazadan kadastr bo'yicha).
  2. sr.ihma.uz FamilyFromIntegration -> oila tarkibi.
  3. survey_homes formasidan survey_uuid.
  4. survey_homes_family/data — mavjud a'zolar 1 tadan KO'P bo'lsa SKIP.
  5. formani ochish (GET), so'ng har a'zo: gcp -> check -> POST.

MUHIM: study_level_id, phone manbada yo'q -> null (uydirma EMAS). Foydalanuvchi
static maydonda qiymat kiritsa — o'sha ishlatiladi (uning javobgarligida).
"""

from datetime import datetime
from urllib.parse import parse_qs, urlsplit
import random
from django.db import close_old_connections

from ..models import CitizenRecord, FillJob
from .api import ApiClient, ApiError, WEB_BASE
from .pinfl import birth_date_iso

LOG_CAP = 400
FORM_NAME = "survey_homes_family"

VALUE_BY_REL = {
    "FATHER": 1, "MOTHER": 2, "OLDER_SISTER": 3, "OLDER_BROTHER": 4,
    "YOUNGER_SISTER": 5, "YOUNGER_BROTHER": 6, "SPOUSE": 7, "DAUGHTER": 8,
    "SON": 9, "FATHER_IN_LAW": 10, "MOTHER_IN_LAW": 11, "DAUGHTER_IN_LAW": 12,
    "OTHER": 13, "SON_IN_LAW": 14, "GRANDCHILD": 15,
}


def _ddmmyyyy_to_date(s):
    try:
        return datetime.strptime(str(s).strip(), "%d.%m.%Y")
    except (ValueError, TypeError):
        return None


def _split_document(doc):
    if not doc:
        return None, None
    doc = str(doc).strip()
    letters = "".join(c for c in doc if c.isalpha())
    digits = "".join(c for c in doc if c.isdigit())
    if letters and digits:
        return letters, digits
    return None, doc or None


def _relationship(traversal, member_bd, self_bd):
    t = (traversal or "").upper()
    if t == "FATHER":
        rel = "FATHER"
    elif t == "MOTHER":
        rel = "MOTHER"
    elif t in ("SPOUSE", "WIFE", "HUSBAND"):
        rel = "SPOUSE"
    elif t == "SON":
        rel = "SON"
    elif t == "DAUGHTER":
        rel = "DAUGHTER"
    elif t == "BROTHER":
        older = member_bd and self_bd and member_bd < self_bd
        rel = "OLDER_BROTHER" if older else "YOUNGER_BROTHER"
    elif t == "SISTER":
        older = member_bd and self_bd and member_bd < self_bd
        rel = "OLDER_SISTER" if older else "YOUNGER_SISTER"
    elif t in ("GRANDCHILD", "GRANDSON", "GRANDDAUGHTER"):
        rel = "GRANDCHILD"
    elif t in ("FATHER_IN_LAW", "MOTHER_IN_LAW", "DAUGHTER_IN_LAW", "SON_IN_LAW"):
        rel = t
    else:
        rel = "OTHER"
    return VALUE_BY_REL[rel], rel


def _home_params(next_link):
    qs = parse_qs(urlsplit(next_link).query)
    return {k: qs[k][0] for k in ("obl_id", "area_id", "district_id", "street_id") if k in qs}


def run_family_fill(job_id, stop_event):
    close_old_connections()
    job = FillJob.objects.get(id=job_id)
    mahalla = job.mahalla
    static = {**job.static_fields}
    document_type = (static.get("document_type") or "1")
    phone = (static.get("phone") or "").strip() or f"+99888{random.randint(1000000, 9999999)}"
    study_level_id = (static.get("study_level_id") or "").strip() or random.randint(1,4)
    
    api = ApiClient(mahalla.token, ihma_token=mahalla.ihma_token)

    recmap = {}
    for r in CitizenRecord.objects.filter(mahalla=mahalla):
        if r.pinfl and str(r.pinfl).strip() not in ("", "-"):
            recmap.setdefault(str(r.kadastr), str(r.pinfl).strip())

    done = set(job.done_ids or [])
    stats = {"homes": 0, "members": 0, "skipped": 0, "failed": 0, **(job.stats or {})}
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

    if not mahalla.ihma_token:
        log("XATO: ihma.uz token yo'q (yuqorida saqlang).")
        persist(status="error")
        return

    log(f"=== Oila to'ldirish: {mahalla.name} | ko'chalar: {len(job.streets)} ===")
    persist(status="running")

    try:
        for street in job.streets:
            if stopping():
                break
            sid = street.get("id")
            sname = street.get("name", sid)
            log(f"--- Ko'cha: {sname} ---")

            try:
                for home in api.iter_homes(mahalla, sid, surveyed=1, stop_event=stop_event):
                    if stopping():
                        break
                    cad = str(home.get("cadaster_number"))
                    next_link = home.get("next_link")

                    owner_pinfl = str(home.get("pinfl") or "").strip()
                    if not (len(owner_pinfl) == 14 and owner_pinfl.isdigit()):
                        owner_pinfl = recmap.get(cad)
                    if not owner_pinfl:
                        stats["skipped"] += 1
                        continue
                    if owner_pinfl in done:
                        stats["skipped"] += 1
                        continue

                    try:
                        family = api.ihma_family(owner_pinfl, stop_event=stop_event)
                        if not family:
                            stats["skipped"] += 1
                            log(f"  SKIP {cad}: oila bo'sh")
                            persist()
                            continue

                        form = api.get_form(next_link, stop_event=stop_event)
                        survey_uuid = (form.get("formData") or {}).get("survey_uuid")
                        if not survey_uuid:
                            stats["skipped"] += 1
                            log(f"  SKIP {cad}: survey_uuid yo'q")
                            persist()
                            continue

                        params = _home_params(next_link)

                        # QAYTA ESLATMA: mavjud a'zolar 1 tadan ko'p bo'lsa -> skip
                        count = api.family_existing_count(params, survey_uuid, stop_event=stop_event)
                        if count and count > 1:
                            stats["skipped"] += 1
                            done.add(owner_pinfl)
                            log(f"  SKIP {cad}: oilada allaqachon {count} a'zo bor")
                            persist()
                            continue

                        # forma URL (uy bo'yicha bitta)
                        q = {**params, "_target": "modal", "pinfl": owner_pinfl,
                             "survey_uuid": survey_uuid, "owner_pinfl": owner_pinfl}
                        form_url = f"{WEB_BASE}forms/{FORM_NAME}?" + "&".join(f"{k}={v}" for k, v in q.items())

                        # formani ochish (GET) — gcp'dan oldin
                        api.form_get(form_url, stop_event=stop_event)

                        self_bd = None
                        for m in family:
                            if (m.get("traversal") or "").upper() == "SELF":
                                self_bd = _ddmmyyyy_to_date(m.get("birthDate"))
                                break

                        log(f"  {cad} -> a'zolar: {len(family)}")
                        stats["homes"] += 1

                        for m in family:
                            if stopping():
                                break
                            traversal = (m.get("traversal") or "").upper()
                            if traversal == "SELF":
                                continue
                            member_pinfl = str(m.get("pnfl") or "").strip()
                            if len(member_pinfl) != 14 or not member_pinfl.isdigit():
                                continue

                            bdate = birth_date_iso(member_pinfl)
                            member_bd = _ddmmyyyy_to_date(m.get("birthDate"))
                            try:
                                person = api.gcp(member_pinfl, bdate, FORM_NAME, stop_event=stop_event)
                            except ApiError:
                                raise
                            except Exception as e:  # noqa: BLE001
                                stats["failed"] += 1
                                log(f"    a'zo {member_pinfl}: gcp xatolik: {e}")
                                persist()
                                continue

                            serial, number = _split_document(person.get("current_document"))
                            rel_value, rel_name = _relationship(traversal, member_bd, self_bd)
                            payload = {
                                "address": person.get("address"),
                                "birth_date": person.get("birth_date") or bdate,
                                "doc_number": number,
                                "doc_serial": serial,
                                "document_type": document_type,
                                "full_name": person.get("full_name") or " ".join(
                                    x for x in [m.get("surname"), m.get("name"), m.get("patronym")] if x),
                                "phone": phone,               # bo'sh -> null (uydirma yo'q)
                                "pinfl": int(member_pinfl),
                                "relationship": str(rel_value),
                                "study_level_id": study_level_id,  # bo'sh -> null (uydirma yo'q)
                            }
                            try:
                                api.family_check(owner_pinfl, member_pinfl, stop_event=stop_event)
                                api.form_post(form_url, payload, stop_event=stop_event)
                                stats["members"] += 1
                                log(f"    OK {payload['full_name']} [{rel_name}]")
                            except ApiError:
                                raise
                            except Exception as e:  # noqa: BLE001
                                stats["failed"] += 1
                                log(f"    FAIL {member_pinfl}: {e}")
                            persist()

                        done.add(owner_pinfl)
                        persist()
                    except ApiError:
                        raise
                    except Exception as e:  # noqa: BLE001
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
        log(f"=== Yakun ({final}) | uylar: {stats['homes']}, a'zolar: {stats['members']}, "
            f"o'tkazildi: {stats['skipped']}, xatolik: {stats['failed']} ===")
        persist(status=final)
        close_old_connections()

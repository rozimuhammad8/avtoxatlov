import json

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import jobs
from .models import (DEFAULT_STATIC_FIELDS, FAMILY_STATIC_FIELDS,
                     CitizenRecord, FillJob, Mahalla)
from .services.api import ApiClient
from .services.excel import parse_excel


def home(request):
    return render(request, "core/home.html", {"mahallas": Mahalla.objects.all()})


def mahalla_create(request):
    if request.method == "POST":
        try:
            Mahalla.objects.create(
                name=request.POST["name"].strip(),
                obl_id=int(request.POST["obl_id"]),
                area_id=int(request.POST["area_id"]),
                district_id=int(request.POST["district_id"]),
                token=request.POST.get("token", "").strip(),
            )
            messages.success(request, "Mahalla qo'shildi.")
        except (KeyError, ValueError):
            messages.error(request, "Ma'lumotlar noto'g'ri.")
        return redirect("home")
    return redirect("home")


def mahalla_detail(request, pk):
    mahalla = get_object_or_404(Mahalla, pk=pk)
    cjob = mahalla.jobs.filter(section="citizen").order_by("-created_at").first()
    fjob = mahalla.jobs.filter(section="family").order_by("-created_at").first()

    static = {**DEFAULT_STATIC_FIELDS}
    if cjob and cjob.static_fields:
        static.update(cjob.static_fields)
    fstatic = {**FAMILY_STATIC_FIELDS}
    if fjob and fjob.static_fields:
        fstatic.update(fjob.static_fields)

    selected = []
    if cjob and cjob.streets:
        selected = cjob.streets
    elif fjob and fjob.streets:
        selected = fjob.streets

    return render(request, "core/mahalla.html", {
        "mahalla": mahalla,
        "record_count": mahalla.record_count,
        "static_json": json.dumps(static),
        "family_static_json": json.dumps(fstatic),
        "selected_json": json.dumps(selected),
    })


def save_token(request, pk):
    mahalla = get_object_or_404(Mahalla, pk=pk)
    if request.method == "POST":
        mahalla.token = request.POST.get("token", "").strip()
        mahalla.ihma_token = request.POST.get("ihma_token", "").strip()
        mahalla.save(update_fields=["token", "ihma_token"])
        messages.success(request, "Tokenlar saqlandi.")
    return redirect("mahalla_detail", pk=pk)


def upload_excel(request, pk):
    mahalla = get_object_or_404(Mahalla, pk=pk)
    if request.method == "POST" and request.FILES.get("file"):
        try:
            records = parse_excel(request.FILES["file"])  # avval o'qiymiz (bad fayl bazani o'chirmasin)
            with transaction.atomic():
                # yangi yuklashda eski yozuvlar o'chiriladi, keyin qo'shiladi
                CitizenRecord.objects.filter(mahalla=mahalla).delete()
                CitizenRecord.objects.bulk_create([
                    CitizenRecord(mahalla=mahalla, kadastr=r["kadastr"],
                                  pinfl=r["pinfl"], birth_date=r["birth_date"])
                    for r in records
                ], batch_size=1000)
            messages.success(request, f"Eski baza o'chirildi, {len(records)} ta yangi yozuv yuklandi.")
        except Exception as e:  # noqa: BLE001
            messages.error(request, f"Excel o'qishda xatolik: {e}")
    return redirect("mahalla_detail", pk=pk)


def fetch_streets(request, pk):
    mahalla = get_object_or_404(Mahalla, pk=pk)
    if not mahalla.token:
        return JsonResponse({"ok": False, "error": "Avval token saqlang."}, status=400)
    try:
        results = ApiClient(mahalla.token).streets(mahalla)
        streets = [{"id": s.get("id"), "name": s.get("name"),
                    "homes": s.get("homes_stat_count"),
                    "surveyed": s.get("homes_surveyed_count")}
                   for s in results if s.get("id") is not None]
        return JsonResponse({"ok": True, "streets": streets})
    except Exception as e:  # noqa: BLE001
        return JsonResponse({"ok": False, "error": str(e)}, status=502)


def _section(request, body=None):
    s = (body or {}).get("section") or request.GET.get("section") or "citizen"
    return "family" if s == "family" else "citizen"


def start_fill(request, pk):
    mahalla = get_object_or_404(Mahalla, pk=pk)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST kerak"}, status=405)
    body = json.loads(request.body or "{}")
    section = _section(request, body)
    streets = body.get("streets") or []
    static = body.get("static") or {}
    if not streets:
        return JsonResponse({"ok": False, "error": "Ko'cha tanlang."}, status=400)
    if not mahalla.token:
        return JsonResponse({"ok": False, "error": "online-mahalla token yo'q."}, status=400)
    if section == "family" and not mahalla.ihma_token:
        return JsonResponse({"ok": False, "error": "ihma.uz token yo'q."}, status=400)

    job = mahalla.jobs.filter(section=section).order_by("-created_at").first()
    if job and job.is_active():
        return JsonResponse({"ok": False, "error": "Allaqachon ishlayapti."}, status=409)

    # oldingi to'xtaganini davom ettiramiz (done_ids saqlanadi); done bo'lsa yangi job
    resume = bool(job and job.status in ("stopped", "error"))
    if not job or job.status == "done":
        job = FillJob.objects.create(mahalla=mahalla, section=section)
    job.streets = streets
    job.static_fields = static
    if not resume:
        job.stats = {}
        job.logs = []
        # done_ids SAQLANADI — allaqachon to'ldirilganlar qayta yuborilmaydi.
    job.status = "running"
    job.save()

    jobs.start_job(job)
    return JsonResponse({"ok": True, "job_id": job.id})


def stop_fill(request, pk):
    section = _section(request)
    job = FillJob.objects.filter(mahalla_id=pk, section=section).order_by("-created_at").first()
    if not job:
        return JsonResponse({"ok": False, "error": "Job topilmadi."}, status=404)
    jobs.stop_job(job.id)
    return JsonResponse({"ok": True})


def fill_status(request, pk):
    section = _section(request)
    job = FillJob.objects.filter(mahalla_id=pk, section=section).order_by("-created_at").first()
    if not job:
        return JsonResponse({"ok": True, "status": "idle", "stats": {}, "logs": []})
    return JsonResponse({
        "ok": True,
        "status": job.status,
        "running": jobs.is_running(job.id),
        "stats": job.stats or {},
        "logs": (job.logs or [])[-200:],
    })

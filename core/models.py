from django.db import models


DEFAULT_STATIC_FIELDS = {
    # Fuqaro (survey_homes) formasi uchun static/placeholder qiymatlar.
    # Bular FOYDALANUVCHI tomonidan kiritiladi/o'zgartiriladi — kod o'zi to'qimaydi.
    "mobile_phone": "998991234567",
    "survey_date": "",           # bo'sh bo'lsa bugungi sana ishlatiladi
    "property_type": "1",
    "home_type": "1",
    "ownership": "1",
    "home_registered": "1",
    "study_level_id": "",        # bo'sh qoldirish mumkin
    "home_num": "1",
}

FAMILY_STATIC_FIELDS = {
    # Oila (survey_homes_family) formasi static maydonlari — FOYDALANUVCHI kiritadi.
    "document_type": "1",
    "phone": "",                 # bo'sh -> null (uydirma yo'q)
    "study_level_id": "",        # bo'sh -> null (uydirma yo'q); qiymat kiritilsa hammaga o'sha
}


class Mahalla(models.Model):
    name = models.CharField(max_length=200)
    obl_id = models.IntegerField()
    area_id = models.IntegerField()
    district_id = models.IntegerField()
    token = models.TextField(blank=True, default="")            # online-mahalla.uz
    ihma_token = models.TextField(blank=True, default="")       # sr.ihma.uz (oila tarkibi)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.district_id})"

    @property
    def record_count(self):
        return self.records.count()


class CitizenRecord(models.Model):
    """Mahallaning bazasi: kadastr -> pinfl, tug'ilgan sana (Excel/JSON dan)."""
    mahalla = models.ForeignKey(Mahalla, related_name="records", on_delete=models.CASCADE)
    kadastr = models.CharField(max_length=100, db_index=True)
    pinfl = models.CharField(max_length=20, blank=True, default="")
    birth_date = models.CharField(max_length=20, blank=True, default="")  # DD.MM.YYYY

    class Meta:
        indexes = [models.Index(fields=["mahalla", "kadastr"])]


class FillJob(models.Model):
    SECTION_CHOICES = [("citizen", "Fuqaro ma'lumotlari"), ("family", "Oila a'zolari")]
    STATUS_CHOICES = [
        ("idle", "idle"), ("running", "running"), ("stopping", "stopping"),
        ("stopped", "stopped"), ("done", "done"), ("error", "error"),
    ]

    mahalla = models.ForeignKey(Mahalla, related_name="jobs", on_delete=models.CASCADE)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default="citizen")
    streets = models.JSONField(default=list)          # [{"id":..,"name":..}, ...]
    static_fields = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="idle")
    stats = models.JSONField(default=dict)            # {total, sent, skipped, failed}
    done_ids = models.JSONField(default=list)         # tugatilgan uy kadastrlari
    logs = models.JSONField(default=list)             # oxirgi log qatorlari
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_active(self):
        return self.status in ("running", "stopping")

from django.contrib import admin

from .models import CitizenRecord, FillJob, Mahalla


@admin.register(Mahalla)
class MahallaAdmin(admin.ModelAdmin):
    list_display = ("name", "obl_id", "area_id", "district_id", "record_count", "created_at")


@admin.register(CitizenRecord)
class CitizenRecordAdmin(admin.ModelAdmin):
    list_display = ("mahalla", "kadastr", "pinfl", "birth_date")
    search_fields = ("kadastr", "pinfl")


@admin.register(FillJob)
class FillJobAdmin(admin.ModelAdmin):
    list_display = ("mahalla", "section", "status", "updated_at")

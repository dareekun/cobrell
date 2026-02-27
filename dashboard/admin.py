from django.contrib import admin
from .models import Musik, JadwalBel


@admin.register(Musik)
class MusikAdmin(admin.ModelAdmin):
    list_display = ('nama', 'file', 'created_at')
    search_fields = ('nama',)


@admin.register(JadwalBel)
class JadwalBelAdmin(admin.ModelAdmin):
    list_display = ('nama', 'hari', 'jam', 'musik', 'aktif')
    list_filter = ('hari', 'aktif')
    search_fields = ('nama',)
    list_editable = ('aktif',)

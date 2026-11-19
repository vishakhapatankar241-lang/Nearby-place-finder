from django.contrib.gis import admin

from .models import Place


@admin.register(Place)
class PlaceAdmin(admin.GISModelAdmin):
    list_display = ("name", "category", "owner", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "owner__email")

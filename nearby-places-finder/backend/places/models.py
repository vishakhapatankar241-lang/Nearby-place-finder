from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models


class Place(models.Model):
    class Category(models.TextChoices):
        HOSPITAL = "hospital", "Hospital"
        SCHOOL = "school", "School"
        RESTAURANT = "restaurant", "Restaurant"
        SHOP = "shop", "Shop"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="places")
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices, db_index=True)
    description = models.TextField(blank=True)

   
    location = gis_models.PointField(geography=True, srid=4326, spatial_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.category})"

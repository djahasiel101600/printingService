from django.db import migrations


def seed_id_picture(apps, schema_editor):
    Product = apps.get_model("catalogue", "Product")
    Product.objects.get_or_create(
        slug="2x2-id-picture",
        defaults={
            "name": "2x2 ID Picture",
            "description": "Shop-prepared 2x2 ID pictures printed on A4 photo paper.",
            "category": "ID photos",
            "price": 3000,
            "unit_label": "piece",
            "min_quantity": 1,
            "max_quantity": 99,
            "is_active": True,
            "is_featured": True,
            "display_order": 0,
            "default_spec": {
                "media_size": "ps_a4",
                "media_type": "pt_photopaper",
                "color_mode": "color",
                "print_quality": "high",
                "sides": "none",
                "orientation": "portrait",
                "copies": 1,
            },
            "instructions": (
                "Upload one clear photo. The shop will prepare the 2x2 ID picture layout "
                "before printing; automatic photo composition is not performed."
            ),
        },
    )


def keep_seeded_product(apps, schema_editor):
    """Never remove a product that an administrator may have edited."""


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_id_picture, keep_seeded_product),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0047_salesinvoice_discount_addition"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvoicePrintTemplateMaster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

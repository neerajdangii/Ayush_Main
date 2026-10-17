from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0042_salesinvoice_number_and_delivery_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="salesinvoice",
            name="invoice_type",
            field=models.CharField(blank=True, default="Regular", max_length=80),
        ),
    ]

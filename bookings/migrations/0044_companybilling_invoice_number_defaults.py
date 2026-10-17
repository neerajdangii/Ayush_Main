from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0043_salesinvoice_default_type_regular"),
    ]

    operations = [
        migrations.AddField(
            model_name="companybillingsettings",
            name="invoice_number_prefix",
            field=models.CharField(default="ARL/IN", max_length=30),
        ),
        migrations.AddField(
            model_name="companybillingsettings",
            name="invoice_number_suffix",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="companybillingsettings",
            name="invoice_next_sequence",
            field=models.PositiveIntegerField(default=1),
        ),
    ]

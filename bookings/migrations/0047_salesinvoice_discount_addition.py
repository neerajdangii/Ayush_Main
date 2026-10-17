from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0046_salesinvoice_adjustment_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesinvoice",
            name="discount_is_addition",
            field=models.BooleanField(default=False),
        ),
    ]

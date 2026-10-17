from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0048_invoiceprinttemplatemaster"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceprinttemplatemaster",
            name="header_content",
            field=models.TextField(blank=True),
        ),
    ]

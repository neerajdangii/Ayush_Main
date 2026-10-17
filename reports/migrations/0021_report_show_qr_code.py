from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0020_report_allow_user_deletion"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="show_qr_code",
            field=models.BooleanField(default=True),
        ),
    ]

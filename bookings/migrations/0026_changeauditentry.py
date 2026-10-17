from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0025_booking_allow_user_deletion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChangeAuditEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_id_value", models.PositiveIntegerField(blank=True, null=True)),
                ("booking_code", models.CharField(db_index=True, max_length=16)),
                ("area", models.CharField(choices=[("booking", "Booking"), ("coa", "COA")], max_length=20)),
                ("field_name", models.CharField(max_length=100)),
                ("field_label", models.CharField(max_length=150)),
                ("old_value", models.TextField(blank=True)),
                ("new_value", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="change_audit_entries", to="bookings.booking")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="change_audit_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-changed_at", "-pk"],
                "permissions": [("view_booking_change_audit", "Can view booking and COA change audit")],
                "indexes": [models.Index(fields=["booking_code", "-changed_at"], name="bookings_ch_bookin_8cd1_idx")],
            },
        ),
    ]

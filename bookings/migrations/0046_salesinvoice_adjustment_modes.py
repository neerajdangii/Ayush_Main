from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0045_move_invoice_title_bar_to_middle"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesinvoice",
            name="discount_mode",
            field=models.CharField(
                choices=[("amount", "₹"), ("percent", "%")],
                default="amount",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="tcs_is_deduction",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="tcs_mode",
            field=models.CharField(
                choices=[("amount", "₹"), ("percent", "%")],
                default="percent",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="salesinvoice",
            name="tcs_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
            ),
        ),
    ]

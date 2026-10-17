from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0041_delete_invoicepartyheadermaster_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="salesinvoice",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="po_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salesinvoice",
            name="eway_number",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]

import re

from django.db import migrations


TITLE_TABLE = re.compile(
    r"(<table\b(?:(?!<table\b).)*?TAX\s*INVOICE(?:(?!<table\b).)*?</table>)",
    re.IGNORECASE | re.DOTALL,
)


def move_title_bar(apps, schema_editor):
    Header = apps.get_model("bookings", "InvoiceHeaderMaster")
    Middle = apps.get_model("bookings", "InvoiceMiddleMaster")
    header = Header.objects.filter(pk=1).first()
    if not header or not header.content:
        return
    match = TITLE_TABLE.search(header.content)
    if not match:
        return
    middle = Middle.objects.filter(pk=1).first()
    if not middle:
        middle = Middle.objects.create(pk=1, content="")
    title_bar = match.group(1)
    header.content = header.content[:match.start()] + header.content[match.end():]
    middle.content = title_bar + ("\n" + middle.content if middle.content else "")
    header.save(update_fields=["content"])
    middle.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0044_companybilling_invoice_number_defaults"),
    ]

    operations = [
        migrations.RunPython(move_title_bar, migrations.RunPython.noop),
    ]

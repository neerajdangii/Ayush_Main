from datetime import date, datetime

from django.utils import timezone

from .models import ChangeAuditEntry


def _display(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        if isinstance(value, datetime) and timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%d/%m/%Y %H:%M" if isinstance(value, datetime) else "%d/%m/%Y")
    return str(value)


def booking_snapshot(booking):
    snapshot = {}
    for field in booking._meta.concrete_fields:
        if field.name in {"id", "created_at", "updated_at", "created_by", "updated_by", "approved_by", "approved_at"}:
            continue
        value = getattr(booking, field.attname)
        if field.is_relation:
            related = getattr(booking, field.name, None)
            display = _display(related) if related else ""
        else:
            display = _display(value)
        snapshot[field.name] = (value, str(field.verbose_name).capitalize(), display)
    tests = list(booking.test_to_be_performed.order_by("name").values_list("name", flat=True))
    snapshot["test_to_be_performed"] = (tuple(tests), "Tests to be performed", ", ".join(tests))
    return snapshot


def coa_snapshot(report):
    fields = {
        "ceo_content": (report.ceo_content, "COA result content", report.ceo_content or ""),
        "report_template": (
            report.report_template_id,
            "Report template",
            str(report.report_template) if report.report_template_id else "",
        ),
        "selected_remark": (
            report.selected_remark_id,
            "Selected remark",
            str(report.selected_remark) if report.selected_remark_id else "",
        ),
        "final_outcome": (report.final_outcome, "Final outcome", report.get_final_outcome_display()),
        "remark_text": (report.remark_text, "Remark text", report.remark_text or ""),
        "manual_certificate_no": (
            report.booking.manual_certificate_no,
            "Certificate number",
            report.booking.manual_certificate_no or "",
        ),
    }
    return fields


def record_changes(*, booking, area, before, after, user, report_id=None):
    entries = []
    for name, old in before.items():
        new = after.get(name)
        if new is None or old[0] == new[0]:
            continue
        entries.append(
            ChangeAuditEntry(
                booking=booking,
                report_id_value=report_id,
                booking_code=booking.tracking_code,
                area=area,
                field_name=name,
                field_label=old[1],
                old_value=old[2],
                new_value=new[2],
                changed_by=user,
            )
        )
    if entries:
        ChangeAuditEntry.objects.bulk_create(entries)


def record_coa_edit(*, booking, report_id, user):
    """Record that a COA was saved without exposing its editable content."""
    ChangeAuditEntry.objects.create(
        booking=booking,
        report_id_value=report_id,
        booking_code=booking.tracking_code,
        area=ChangeAuditEntry.Area.COA,
        field_name="coa_edited",
        field_label="COA edited",
        old_value="",
        new_value="COA edited",
        changed_by=user,
    )

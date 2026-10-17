from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models
from django.db.models import Max
from django.db.models.functions import Cast
from django.utils import timezone


class ActiveMasterModel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CustomerMaster(ActiveMasterModel):
    address = models.TextField(blank=True)
    consignee_address = models.TextField(blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)


class SubmitterMaster(ActiveMasterModel):
    pass


class ManufacturerMaster(ActiveMasterModel):
    pass


class SampleNameMaster(ActiveMasterModel):
    class Discipline(models.TextChoices):
        NABL = "NABL", "NABL"
        PHARMA = "Pharma", "Pharma"

    class TestGroup(models.TextChoices):
        BIOLOGICAL = "Biological Section", "Biological Section"
        CHEMICAL_INSTRUMENT = "Chemical/Instrument Section", "Chemical/Instrument Section"

    class SampleType(models.TextChoices):
        API = "API", "API"
        FG = "FG", "FG"
        FOOD = "Food", "Food"
        RM = "RM", "RM"

    generic_name = models.CharField(max_length=255, blank=True)
    discipline = models.CharField(max_length=40, choices=Discipline.choices, blank=True)
    test_group = models.CharField(max_length=80, choices=TestGroup.choices, blank=True)
    sample_type = models.CharField(max_length=20, choices=SampleType.choices, blank=True)
    method = models.CharField(max_length=255, blank=True)
    rate = models.CharField(max_length=100, blank=True)
    observationsheet_prefix = models.CharField(max_length=100, blank=True)
    customer = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    limits = models.TextField(blank=True)

    @property
    def display_name(self) -> str:
        generic = (self.generic_name or "").strip()
        return f"{self.name} ({generic})" if generic else self.name

    def __str__(self) -> str:
        return self.display_name


class TestMaster(ActiveMasterModel):
    report_template = models.ForeignKey(
        "reports.ReportTemplate",
        on_delete=models.SET_NULL,
        related_name="linked_tests",
        null=True,
        blank=True,
    )


class ProtocolMaster(ActiveMasterModel):
    pass


class UOMMaster(ActiveMasterModel):
    pass


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"

    class SampleType(models.TextChoices):
        API = "API", "API"
        FG = "FG", "FG"
        FOOD = "Food", "Food"
        RM = "RM", "RM"
        STABILITY = "Stability", "Stability"

    class BookingType(models.TextChoices):
        REGULATORY = "regulatory", "Regulatory"
        GENERAL = "general", "General"

    booking_date = models.DateTimeField(default=timezone.now)
    letter_date = models.DateTimeField(null=True, blank=True)
    sampling_upto = models.DateTimeField(null=True, blank=True)
    sample_receipt_date = models.DateTimeField(null=True, blank=True)
    customer = models.ForeignKey(
        CustomerMaster, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    submitter = models.ForeignKey(
        SubmitterMaster, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    manufacturer = models.ForeignKey(
        ManufacturerMaster, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    sample_name = models.ForeignKey(
        SampleNameMaster, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    sample_type = models.CharField(max_length=20, choices=SampleType.choices, blank=True)
    test_to_be_performed = models.ManyToManyField(TestMaster, related_name="bookings", blank=True)
    protocol = models.ForeignKey(
        ProtocolMaster, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True
    )
    uom = models.ForeignKey(UOMMaster, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True)
    booking_type = models.CharField(max_length=20, choices=BookingType.choices, default=BookingType.GENERAL)
    tracking_code = models.CharField(max_length=16, unique=True, editable=False, blank=True, default="")
    sample_reg_no = models.CharField(max_length=32, unique=True, null=True, blank=True)
    manual_certificate_no = models.CharField(max_length=64, blank=True, null=True)
    certificate_serial = models.PositiveIntegerField(null=True, blank=True, editable=False)
    sample_qty = models.CharField(max_length=100, blank=True)
    sample_location = models.CharField(max_length=255, blank=True)
    packaging_mode = models.CharField(max_length=255, blank=True)
    sample_condition = models.CharField(max_length=255, blank=True)
    batch_no = models.CharField(max_length=100, blank=True)
    batch_size = models.CharField(max_length=100, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_retest_date = models.DateField(null=True, blank=True)
    license_no = models.CharField(max_length=255, blank=True)
    customer_sr_no = models.CharField(max_length=128, blank=True)
    collected_by_name = models.CharField(max_length=255, blank=True)
    sampling_procedure = models.CharField(max_length=255, blank=True)
    analysis_start_date = models.DateTimeField(null=True, blank=True)
    analysis_end_date = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_bookings",
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_bookings",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("view_data_sheet", "Can view Data Sheet"),
            ("assign_booking", "Can assign bookings"),
        ]

    @property
    def booking_type_code(self) -> str:
        return "REG" if self.booking_type == self.BookingType.REGULATORY else "GEN"

    @property
    def certificate_no(self) -> str:
        """Return the booking certificate number using its assigned serial."""
        if self.manual_certificate_no:
            return self.manual_certificate_no

        receipt_date = self.sample_receipt_date or self.booking_date
        if not receipt_date:
            return "-"

        if timezone.is_aware(receipt_date):
            receipt_date = timezone.localtime(receipt_date)

        numbering_mode = self._certificate_numbering_mode()

        sequence = self.certificate_serial or self._calculate_certificate_serial(numbering_mode)

        if numbering_mode == "continuous":
            return f"ARL/{self.booking_type_code}/{receipt_date.strftime('%y%m%d')}{sequence:04d}"

        return f"ARL/{self.booking_type_code}/{receipt_date.strftime('%y%m%d')}{sequence:03d}"

    @staticmethod
    def _certificate_numbering_mode():
        try:
            from django.apps import apps

            SystemSetting = apps.get_model("accounts", "SystemSetting")
            return SystemSetting.current().certificate_numbering_mode
        except Exception:
            return None

    def _calculate_certificate_serial(self, numbering_mode=None) -> int:
        """Calculate the serial only when initially assigning it to a booking."""
        if not self.pk:
            return 1

        if numbering_mode == "continuous":
            return Booking.objects.filter(
                booking_type=self.booking_type,
                pk__lte=self.pk,
            ).count()

        receipt_date = self.sample_receipt_date or self.booking_date
        if not receipt_date:
            return 1
        if timezone.is_aware(receipt_date):
            receipt_date = timezone.localtime(receipt_date)

        date_field = "sample_receipt_date" if self.sample_receipt_date else "booking_date"
        # The serial is per calendar day, not per timestamp. A booking entered
        # later can legitimately have an earlier clock time on its received
        # date; use that day's highest assigned serial so it always continues.
        last_serial = (
            Booking.objects.filter(**{f"{date_field}__date": receipt_date.date()})
            .exclude(pk=self.pk)
            .aggregate(max_serial=Max("certificate_serial"))
            .get("max_serial")
        )
        return (last_serial or 0) + 1

    @staticmethod
    def _certificate_calendar_date(value):
        if not value:
            return None
        if hasattr(value, "tzinfo") and timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date() if hasattr(value, "date") else value

    @property
    def sample_registration_no(self) -> str:
        source_date = self.sample_receipt_date or self.booking_date
        if not source_date:
            return "-"

        if hasattr(source_date, "tzinfo") and timezone.is_aware(source_date):
            source_date = timezone.localtime(source_date)

        reg_no = self.sample_reg_no or ""
        try:
            sequence = int(reg_no.rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            try:
                sequence = int(self.tracking_code)
            except (TypeError, ValueError):
                sequence = self.pk or 1

        return f"ARLPL/R/{source_date.strftime('%d-%m-%Y')}/{sequence:04d}"

    @classmethod
    def _next_sequence(cls, booking_date, booking_type):
        year = booking_date.year
        prefix = f"ARL/{year}/{ 'REG' if booking_type == cls.BookingType.REGULATORY else 'GEN' }/"
        max_reg = (
            cls.objects.filter(sample_reg_no__startswith=prefix)
            .aggregate(max_reg=Max("sample_reg_no"))
            .get("max_reg")
        )
        if not max_reg:
            return 1
        try:
            return int(max_reg.rsplit("/", 1)[-1]) + 1
        except (TypeError, ValueError):
            return 1

    def generate_sample_reg_no(self) -> str:
        sequence = self._next_sequence(self.booking_date, self.booking_type)
        return f"ARL/{self.booking_date.year}/{self.booking_type_code}/{sequence:04d}"

    @classmethod
    def generate_tracking_code(cls) -> str:
        numeric_codes = cls.objects.filter(tracking_code__regex=r"^\d+$").aggregate(
            max_code=Max(Cast("tracking_code", models.BigIntegerField()))
        )
        last_value = numeric_codes.get("max_code") or 999
        next_value = last_value + 1
        return str(next_value)

    @classmethod
    def get_last_similar_booking(cls, sample_name_id, customer_id):
        """Fetch the most recent booking with the same sample name and customer."""
        if not sample_name_id or not customer_id:
            return None
        return cls.objects.filter(
            sample_name_id=sample_name_id,
            customer_id=customer_id
        ).exclude(
            sample_name_id__isnull=True,
            customer_id__isnull=True
        ).order_by("-created_at").first()

    def save(self, *args, **kwargs):
        previous_receipt_date = None
        if self.pk:
            previous_receipt_date = type(self).objects.filter(pk=self.pk).values_list(
                "sample_receipt_date", flat=True
            ).first()
        receipt_date_changed = (
            self._certificate_calendar_date(previous_receipt_date)
            != self._certificate_calendar_date(self.sample_receipt_date)
        )
        if not self.tracking_code:
            self.tracking_code = self.generate_tracking_code()
        if self.sample_reg_no:
            super().save(*args, **kwargs)
            self._assign_certificate_serial_if_needed(receipt_date_changed=receipt_date_changed)
            return

        for _ in range(3):
            self.sample_reg_no = self.generate_sample_reg_no()
            try:
                super().save(*args, **kwargs)
                self._assign_certificate_serial_if_needed(receipt_date_changed=receipt_date_changed)
                return
            except IntegrityError:
                self.sample_reg_no = None
                self.tracking_code = self.generate_tracking_code()
                continue
        raise IntegrityError("Unable to generate unique sample registration number.")

    def _assign_certificate_serial_if_needed(self, *, receipt_date_changed=False):
        """Assign or move a daily serial when its received date changes."""
        if not self.pk:
            return

        numbering_mode = self._certificate_numbering_mode()
        if self.certificate_serial and (
            numbering_mode == "continuous" or not receipt_date_changed
        ):
            return
        # A daily certificate must be sequenced against its received date. A
        # booking may be created before that date is entered, so wait instead
        # of reserving a serial from the unrelated booking date.
        if numbering_mode != "continuous" and not self.sample_receipt_date:
            return

        self.certificate_serial = self._calculate_certificate_serial(numbering_mode)
        type(self).objects.filter(pk=self.pk).update(certificate_serial=self.certificate_serial)

    def approve(self, user):
        self.status = self.Status.APPROVED
        self.approved_by = user
        self.updated_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "updated_by", "approved_at", "updated_at"])
        # Keep report workflow in sync with approved bookings.
        from reports.models import Report

        Report.objects.get_or_create(booking=self, defaults={"created_by": user})

    @property
    def updated_by_display(self) -> str:
        actor = self.updated_by or self.approved_by or self.created_by
        if not actor:
            return "-"
        return actor.get_full_name() or actor.username

    @property
    def report_object(self):
        try:
            return self.report
        except ObjectDoesNotExist:
            return None

    @property
    def is_reported(self) -> bool:
        report = self.report_object
        return bool(report and report.status != "draft")

    def __str__(self) -> str:
        return self.sample_reg_no or self.tracking_code or f"Booking-{self.pk}"


class ChangeAuditEntry(models.Model):
    """Field-level booking and COA edit history, visible only by permission."""

    class Area(models.TextChoices):
        BOOKING = "booking", "Booking"
        COA = "coa", "COA"

    booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name="change_audit_entries"
    )
    report_id_value = models.PositiveIntegerField(null=True, blank=True)
    booking_code = models.CharField(max_length=16, db_index=True)
    area = models.CharField(max_length=20, choices=Area.choices)
    field_name = models.CharField(max_length=100)
    field_label = models.CharField(max_length=150)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="change_audit_entries",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-pk"]
        permissions = [("view_booking_change_audit", "Can view booking and COA change audit")]
        indexes = [models.Index(fields=["booking_code", "-changed_at"], name="bookings_ch_bookin_8cd1_idx")]


class BillingRecord(models.Model):
    """Audit entry created when a passed report is confirmed for billing."""

    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        related_name="billing_record",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="confirmed_billings",
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField(default=timezone.now)
    bill_number = models.CharField(max_length=100)
    letter_date = models.DateField(null=True, blank=True)
    billing_done_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-confirmed_at", "-pk"]
        verbose_name = "Billing record"
        verbose_name_plural = "Billing records"

    def __str__(self) -> str:
        return f"Billing: {self.booking.tracking_code}"


class BillingUndoRecord(models.Model):
    """Audit history for a billing confirmation that was undone."""

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="billing_undo_records")
    bill_number = models.CharField(max_length=100)
    letter_date = models.DateField(null=True, blank=True)
    billing_done_date = models.DateField(null=True, blank=True)
    confirmed_at = models.DateTimeField()
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="confirmed_billing_undo_records",
        null=True,
        blank=True,
    )
    undone_at = models.DateTimeField(default=timezone.now)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="undone_billing_records",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-undone_at", "-pk"]
        verbose_name = "Billing undo record"
        verbose_name_plural = "Billing undo records"


class CompanyBillingSettings(models.Model):
    """Company supplied details used on GST invoices; intentionally blank by default."""
    legal_name = models.CharField(max_length=255, default="Ayush Research Laboratories Private Limited")
    invoice_number_prefix = models.CharField(max_length=30, default="ARL/IN")
    invoice_number_suffix = models.CharField(max_length=20, blank=True, default="")
    invoice_next_sequence = models.PositiveIntegerField(default=1)
    address = models.TextField(blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    pan = models.CharField(max_length=20, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    logo = models.ImageField(upload_to="invoice/company/", blank=True, null=True)
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    bank_ifsc = models.CharField(max_length=20, blank=True)
    bank_branch = models.CharField(max_length=255, blank=True)
    upi_id = models.CharField(max_length=255, blank=True)
    bank_1_account_name = models.CharField(max_length=255, blank=True)
    bank_1_name = models.CharField(max_length=255, blank=True)
    bank_1_ifsc = models.CharField(max_length=20, blank=True)
    bank_1_swift = models.CharField(max_length=20, blank=True)
    bank_1_micr = models.CharField(max_length=20, blank=True)
    bank_1_account_number = models.CharField(max_length=100, blank=True)
    bank_1_branch = models.CharField(max_length=255, blank=True)
    bank_1_upi_id = models.CharField(max_length=255, blank=True)
    bank_2_account_name = models.CharField(max_length=255, blank=True)
    bank_2_name = models.CharField(max_length=255, blank=True)
    bank_2_ifsc = models.CharField(max_length=20, blank=True)
    bank_2_swift = models.CharField(max_length=20, blank=True)
    bank_2_micr = models.CharField(max_length=20, blank=True)
    bank_2_account_number = models.CharField(max_length=100, blank=True)
    bank_2_branch = models.CharField(max_length=255, blank=True)
    bank_2_upi_id = models.CharField(max_length=255, blank=True)
    bank_3_account_name = models.CharField(max_length=255, blank=True)
    bank_3_name = models.CharField(max_length=255, blank=True)
    bank_3_ifsc = models.CharField(max_length=20, blank=True)
    bank_3_swift = models.CharField(max_length=20, blank=True)
    bank_3_micr = models.CharField(max_length=20, blank=True)
    bank_3_account_number = models.CharField(max_length=100, blank=True)
    bank_3_branch = models.CharField(max_length=255, blank=True)
    bank_3_upi_id = models.CharField(max_length=255, blank=True)
    bank_4_account_name = models.CharField(max_length=255, blank=True)
    bank_4_name = models.CharField(max_length=255, blank=True)
    bank_4_ifsc = models.CharField(max_length=20, blank=True)
    bank_4_swift = models.CharField(max_length=20, blank=True)
    bank_4_micr = models.CharField(max_length=20, blank=True)
    bank_4_account_number = models.CharField(max_length=100, blank=True)
    bank_4_branch = models.CharField(max_length=255, blank=True)
    bank_4_upi_id = models.CharField(max_length=255, blank=True)
    bank_5_account_name = models.CharField(max_length=255, blank=True)
    bank_5_name = models.CharField(max_length=255, blank=True)
    bank_5_ifsc = models.CharField(max_length=20, blank=True)
    bank_5_swift = models.CharField(max_length=20, blank=True)
    bank_5_micr = models.CharField(max_length=20, blank=True)
    bank_5_account_number = models.CharField(max_length=100, blank=True)
    bank_5_branch = models.CharField(max_length=255, blank=True)
    bank_5_upi_id = models.CharField(max_length=255, blank=True)
    bank_6_account_name = models.CharField(max_length=255, blank=True)
    bank_6_name = models.CharField(max_length=255, blank=True)
    bank_6_ifsc = models.CharField(max_length=20, blank=True)
    bank_6_swift = models.CharField(max_length=20, blank=True)
    bank_6_micr = models.CharField(max_length=20, blank=True)
    bank_6_account_number = models.CharField(max_length=100, blank=True)
    bank_6_branch = models.CharField(max_length=255, blank=True)
    bank_6_upi_id = models.CharField(max_length=255, blank=True)
    print_upi_qr = models.BooleanField(default=True)
    upi_qr_include_amount = models.BooleanField(default=True)
    certification = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [("manage_company_billing_settings", "Can manage invoice company settings")]

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class InvoiceHeaderMaster(models.Model):
    """Standalone rich-text header used only by Sales Invoice documents."""
    content = models.TextField(blank=True, verbose_name="Custom Company Header")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class InvoiceMiddleMaster(models.Model):
    """Editable rich-text body section for Sales Invoice documents."""
    content = models.TextField(blank=True, verbose_name="Middle Invoice Template")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class InvoiceFooterMaster(models.Model):
    """Footer display defaults and optional rich text for Sales Invoice documents."""
    show_bank_details = models.BooleanField(default=True)
    show_payment_qr = models.BooleanField(default=True)
    show_terms = models.BooleanField(default=True)
    content = models.TextField(blank=True, verbose_name="Additional Invoice Footer Content")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class InvoicePrintTemplateMaster(models.Model):
    """Separate repeating page header and invoice body templates."""
    header_content = models.TextField(blank=True)
    content = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


class InvoiceCustomerMaster(models.Model):
    class CompanyType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        VENDOR = "vendor", "Vendor"
        BOTH = "both", "Customer / Vendor"

    class RegistrationType(models.TextChoices):
        UNREGISTERED = "unregistered", "Unregistered"
        REGULAR = "regular", "Regular"
        COMPOSITION = "composition", "Composition"

    class BalanceType(models.TextChoices):
        DEBIT = "debit", "Dr"
        CREDIT = "credit", "Cr"

    name = models.CharField(max_length=255)
    company_type = models.CharField(max_length=12, choices=CompanyType.choices, default=CompanyType.CUSTOMER)
    registration_type = models.CharField(max_length=20, choices=RegistrationType.choices, default=RegistrationType.UNREGISTERED, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    consignee_address = models.TextField(blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=100, blank=True, default="India")
    state_name = models.CharField(max_length=120, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    pincode = models.CharField(max_length=20, blank=True)
    distance_from_lab_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    customer_group = models.CharField(max_length=120, blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    balance_type = models.CharField(max_length=6, choices=BalanceType.choices, default=BalanceType.DEBIT)
    license_no = models.CharField(max_length=120, blank=True)
    custom_field_1 = models.CharField(max_length=255, blank=True)
    custom_field_2 = models.CharField(max_length=255, blank=True)
    rate_no = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    due_days = models.PositiveIntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        permissions = [("manage_invoice_customers", "Can manage Sales Invoice customers")]

    @property
    def invoice_billing_address(self):
        return ", ".join(value for value in (self.address, self.landmark, self.city, self.state_name, self.pincode, self.country) if value)

    def __str__(self):
        return self.name


class SalesInvoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINALIZED = "finalized", "Finalized"

    class PaymentType(models.TextChoices):
        CREDIT = "credit", "Credit"
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"
        ONLINE = "online", "Online"

    class AdjustmentMode(models.TextChoices):
        AMOUNT = "amount", "₹"
        PERCENT = "percent", "%"

    invoice_number = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    invoice_date = models.DateField(default=timezone.localdate)
    invoice_type = models.CharField(max_length=80, blank=True, default="Regular")
    claim_number = models.CharField(max_length=100, blank=True)
    po_number = models.CharField(max_length=100, blank=True)
    po_date = models.DateField(null=True, blank=True)
    lr_number = models.CharField(max_length=100, blank=True)
    eway_number = models.CharField(max_length=100, blank=True)
    challan_number = models.CharField(max_length=100, blank=True)
    challan_date = models.DateField(null=True, blank=True)
    delivery_mode = models.CharField(max_length=120, blank=True)
    due_date = models.DateField(null=True, blank=True)
    payment_type = models.CharField(max_length=12, choices=PaymentType.choices, default=PaymentType.CREDIT)
    terms_title = models.CharField(max_length=255, blank=True, default="Terms and Conditions")
    terms_detail = models.TextField(blank=True)
    document_remarks = models.TextField(blank=True)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount_mode = models.CharField(max_length=8, choices=AdjustmentMode.choices, default=AdjustmentMode.AMOUNT)
    discount_is_addition = models.BooleanField(default=False)
    tcs_rate = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tcs_mode = models.CharField(max_length=8, choices=AdjustmentMode.choices, default=AdjustmentMode.PERCENT)
    tcs_is_deduction = models.BooleanField(default=False)
    additional_charges = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    round_off_enabled = models.BooleanField(default=False)
    buyer = models.ForeignKey(CustomerMaster, on_delete=models.PROTECT, related_name="sales_invoices", null=True, blank=True)
    invoice_customer = models.ForeignKey(InvoiceCustomerMaster, on_delete=models.PROTECT, related_name="sales_invoices", null=True, blank=True)
    buyer_snapshot = models.JSONField(default=dict, blank=True)
    company_snapshot = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="finalized_sales_invoices")
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        permissions = [("finalize_salesinvoice", "Can finalize sales invoices"), ("manage_sales_invoices", "Can create and edit sales invoices")]

    @property
    def taxable_total(self):
        return sum((line.taxable_value for line in self.lines.all()), Decimal("0.00"))

    @property
    def tax_total(self):
        return sum((line.cgst_amount + line.sgst_amount + line.igst_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def items_total(self):
        return self.taxable_total + self.tax_total

    @property
    def tcs_amount(self):
        from decimal import ROUND_HALF_UP
        amount = self.tcs_rate
        if self.tcs_mode == self.AdjustmentMode.PERCENT:
            amount = self.taxable_total * self.tcs_rate / Decimal("100")
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def discount_total(self):
        from decimal import ROUND_HALF_UP
        amount = self.discount_amount
        if self.discount_mode == self.AdjustmentMode.PERCENT:
            amount = self.taxable_total * self.discount_amount / Decimal("100")
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def total_before_round_off(self):
        tcs = -self.tcs_amount if self.tcs_is_deduction else self.tcs_amount
        discount = self.discount_total if self.discount_is_addition else -self.discount_total
        return self.taxable_total + self.tax_total + discount + self.additional_charges + tcs

    @property
    def round_off_amount(self):
        if not self.round_off_enabled:
            return Decimal("0.00")
        return self.grand_total - self.total_before_round_off

    @property
    def cgst_total(self):
        return sum((line.cgst_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def sgst_total(self):
        return sum((line.sgst_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def igst_total(self):
        return sum((line.igst_amount for line in self.lines.all()), Decimal("0.00"))

    @property
    def grand_total(self):
        total = self.total_before_round_off
        if self.round_off_enabled:
            from decimal import ROUND_HALF_UP
            return total.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))
        return total


class SalesInvoiceLine(models.Model):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="lines")
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, null=True, blank=True, related_name="invoice_lines")
    description = models.CharField(max_length=500, blank=True)
    item_note = models.TextField(blank=True)
    sample_id = models.CharField(max_length=100, blank=True)
    hsn_sac = models.CharField(max_length=20, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True, default=None)
    uom = models.CharField(max_length=40, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    rate = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, default=None)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, default=None)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=None)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=None)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=None)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    @property
    def taxable_value(self):
        from decimal import Decimal, ROUND_HALF_UP
        gross = ((self.quantity or Decimal("0")) * (self.rate or Decimal("0"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return max(Decimal("0.00"), gross - (self.discount_amount or Decimal("0")))

    def _tax(self, rate):
        from decimal import Decimal, ROUND_HALF_UP
        return (self.taxable_value * (rate or Decimal("0")) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def cgst_amount(self): return self._tax(self.cgst_rate)
    @property
    def sgst_amount(self): return self._tax(self.sgst_rate)
    @property
    def igst_amount(self): return self._tax(self.igst_rate)
    @property
    def total(self): return self.taxable_value + self.cgst_amount + self.sgst_amount + self.igst_amount

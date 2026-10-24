from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import timedelta
from io import BytesIO
import base64
import re
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template import Context, Template, TemplateSyntaxError, VariableDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from reports.models import Report
from .models import Booking, CompanyBillingSettings, InvoiceCustomerMaster, InvoicePrintTemplateMaster, SalesInvoice, SalesInvoiceLine
from .invoice_template_defaults import DEFAULT_INVOICE_HEADER, DEFAULT_INVOICE_TEMPLATE

BANK_DETAIL_FIELDS = (
    "account_name", "name", "ifsc", "swift", "micr", "account_number", "branch", "upi_id",
)
BANK_DETAIL_LABELS = {
    "account_name": "Account Name", "name": "Bank Name", "ifsc": "Bank IFSC",
    "swift": "Swift Code", "micr": "MICR Code", "account_number": "Account Number",
    "branch": "Branch Name", "upi_id": "UPI ID",
}


def _invoice_fy_suffix(invoice_date):
    start_year = invoice_date.year if invoice_date.month >= 4 else invoice_date.year - 1
    end_year = start_year + 1
    return f"{start_year % 100:02d}-{end_year % 100:02d}"


def _invoice_number_defaults(invoice_date):
    settings = CompanyBillingSettings.current()
    prefix = settings.invoice_number_prefix.strip().strip("/") or "ARL/IN"
    suffix = settings.invoice_number_suffix.strip().strip("/") or _invoice_fy_suffix(invoice_date)
    return prefix, suffix, settings.invoice_next_sequence


def _next_invoice_sequence(invoice_date, prefix=None, suffix=None):
    default_prefix, default_suffix, configured_sequence = _invoice_number_defaults(invoice_date)
    prefix = (prefix or default_prefix).strip().strip("/")
    suffix = (suffix or default_suffix).strip().strip("/")
    highest = 0
    for number in SalesInvoice.objects.values_list("invoice_number", flat=True):
        parts = number.rsplit("/", 2)
        if len(parts) == 3 and parts[0] == prefix and parts[2] == suffix and parts[1].isdigit():
            highest = max(highest, int(parts[1]))
    return f"{max(highest + 1, configured_sequence):04d}"


def _format_invoice_number(prefix, sequence, suffix):
    prefix = str(prefix or "ARL/IN").strip().strip("/")
    sequence = str(sequence or "").strip()
    suffix = str(suffix or "").strip().strip("/")
    return f"{prefix}/{sequence.zfill(4)}/{suffix}"


class InvoiceCreateForm(forms.Form):
    invoice_customer = forms.ModelChoiceField(queryset=InvoiceCustomerMaster.objects.none(), label="Customer / Vendor")
    invoice_type = forms.ChoiceField(
        choices=(("Regular", "Regular"), ("Bill of Supply", "Bill of Supply")),
        initial="Regular",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    invoice_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    challan_number = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    challan_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    po_number = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    po_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    lr_number = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    eway_number = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    delivery_mode = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    claim_number = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    payment_type = forms.ChoiceField(choices=SalesInvoice.PaymentType.choices, required=False, widget=forms.Select(attrs={"class": "form-select"}))
    terms_title = forms.CharField(required=False, initial="Terms and Conditions", widget=forms.TextInput(attrs={"class": "form-control"}))
    terms_detail = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    document_remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    discount_amount = forms.DecimalField(required=False, min_value=0, max_digits=14, decimal_places=2, initial=0, widget=forms.NumberInput(attrs={"class": "form-control adjustment-value", "step": "0.01", "min": "0"}))
    discount_mode = forms.ChoiceField(required=False, choices=SalesInvoice.AdjustmentMode.choices, initial=SalesInvoice.AdjustmentMode.AMOUNT, widget=forms.Select(attrs={"class": "form-select adjustment-mode", "aria-label": "Discount unit"}))
    discount_is_addition = forms.BooleanField(required=False, widget=forms.HiddenInput())
    tcs_rate = forms.DecimalField(required=False, min_value=0, max_digits=14, decimal_places=2, initial=0, widget=forms.NumberInput(attrs={"class": "form-control adjustment-value", "step": "0.01", "min": "0"}))
    tcs_mode = forms.ChoiceField(required=False, choices=SalesInvoice.AdjustmentMode.choices, initial=SalesInvoice.AdjustmentMode.PERCENT, widget=forms.Select(attrs={"class": "form-select adjustment-mode", "aria-label": "TCS unit"}))
    tcs_is_deduction = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    additional_charges = forms.DecimalField(required=False, min_value=0, max_digits=14, decimal_places=2, initial=0, widget=forms.NumberInput(attrs={"class": "form-control adjustment-value", "step": "0.01", "min": "0"}))
    round_off_enabled = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice_customer"].widget.attrs.update({"class": "form-select"})
        self.fields["invoice_date"].widget.attrs.update({"class": "form-control"})
        self.fields["invoice_customer"].queryset = InvoiceCustomerMaster.objects.filter(is_active=True, company_type__in=(InvoiceCustomerMaster.CompanyType.CUSTOMER, InvoiceCustomerMaster.CompanyType.BOTH)).order_by("name")
        self.available_bookings = Booking.objects.filter(report__final_outcome=Report.FinalOutcome.PASS).select_related("customer", "sample_name").distinct()
        self.fields["invoice_date"].initial = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        buyer = cleaned.get("invoice_customer")
        keys = ("item_description", "item_sample_id", "item_hsn_sac", "item_quantity", "item_uom", "item_batch_number", "item_rate", "item_discount", "item_tax_type", "item_tax_rate", "item_note", "item_booking_id")
        posted = {key: self.data.getlist(key) for key in keys}
        self.manual_rows = []
        booking_ids = set()
        for raw_id in posted["item_booking_id"]:
            try:
                if raw_id.strip():
                    booking_ids.add(int(raw_id))
            except ValueError:
                pass
        available_bookings = self.available_bookings.filter(pk__in=booking_ids).in_bulk()
        row_count = max((len(values) for values in posted.values()), default=0)
        for index in range(row_count):
            row = {key: (values[index].strip() if index < len(values) else "") for key, values in posted.items()}
            if not any(row.values()):
                continue
            self.manual_rows.append(row)
            row_number = index + 1
            if row["item_booking_id"]:
                try:
                    booking_id = int(row["item_booking_id"])
                except ValueError:
                    self.add_error(None, f"Invalid selected sample on item row {row_number}.")
                    continue
                booking = available_bookings.get(booking_id)
                if not booking:
                    self.add_error(None, f"The selected sample on item row {row_number} is no longer available for billing.")
                    continue
                if buyer and (not booking.customer or booking.customer.name.strip().casefold() != buyer.name.strip().casefold()):
                    self.add_error(None, f"The selected sample on item row {row_number} belongs to a different customer.")
                    continue
                row["booking_id"] = booking_id
            if not row["item_description"]:
                self.add_error(None, f"Product name is required on item row {row_number}.")
                continue
            try:
                if row["item_quantity"]:
                    quantity = Decimal(row["item_quantity"])
                    if quantity <= 0:
                        raise InvalidOperation
                elif row.get("booking_id"):
                    quantity = None
                else:
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                self.add_error(None, f"Enter a quantity greater than zero on item row {row_number}.")
                continue
            try:
                if row["item_rate"]:
                    rate = Decimal(row["item_rate"])
                    if rate < 0:
                        raise InvalidOperation
                elif row.get("booking_id"):
                    rate = None
                else:
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                self.add_error(None, f"Enter a valid price of zero or more on item row {row_number}.")
                continue
            try:
                discount_percent = Decimal(row["item_discount"] or "0") if quantity is not None and rate is not None else None
                if discount_percent is not None and (discount_percent < 0 or discount_percent > 100):
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                self.add_error(None, f"Enter a discount percentage from 0 to 100 on item row {row_number}.")
                continue
            tax_type = row["item_tax_type"]
            if tax_type not in ("", "split", "integrated"):
                self.add_error(None, f"Select a valid GST type on item row {row_number}.")
                continue
            if tax_type and not row["item_tax_rate"]:
                self.add_error(None, f"Enter a GST rate on item row {row_number}.")
                continue
            if row["item_tax_rate"] and not tax_type:
                self.add_error(None, f"Select a GST type on item row {row_number}.")
                continue
            try:
                tax_rate = Decimal(row["item_tax_rate"] or "0")
                if tax_rate < 0 or tax_rate > 100:
                    raise InvalidOperation
            except (InvalidOperation, TypeError):
                self.add_error(None, f"Enter a GST rate from 0 to 100 on item row {row_number}.")
                continue
            discount_amount = None
            if quantity is not None and rate is not None:
                discount_amount = (quantity * rate * (discount_percent or Decimal("0")) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            row.update(quantity=quantity, rate=rate, discount_amount=discount_amount, tax_rate=tax_rate)
        if not self.manual_rows:
            self.add_error(None, "Add at least one invoice item.")
        cleaned["manual_items"] = self.manual_rows
        return cleaned


class InvoiceCustomerMasterForm(forms.ModelForm):
    class Meta:
        model = InvoiceCustomerMaster
        exclude = ("created_at",)
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "company_type": forms.Select(attrs={"class": "form-select"}),
            "registration_type": forms.Select(attrs={"class": "form-select"}),
            "gstin": forms.TextInput(attrs={"class": "form-control"}),
            "pan": forms.TextInput(attrs={"class": "form-control"}),
            "contact_person": forms.TextInput(attrs={"class": "form-control"}),
            "telephone": forms.TextInput(attrs={"class": "form-control", "type": "tel"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "consignee_address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "landmark": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "state_name": forms.TextInput(attrs={"class": "form-control"}),
            "state_code": forms.TextInput(attrs={"class": "form-control", "maxlength": 2}),
            "pincode": forms.TextInput(attrs={"class": "form-control"}),
            "distance_from_lab_km": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "customer_group": forms.TextInput(attrs={"class": "form-control"}),
            "opening_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "balance_type": forms.Select(attrs={"class": "form-select"}),
            "license_no": forms.TextInput(attrs={"class": "form-control"}),
            "custom_field_1": forms.TextInput(attrs={"class": "form-control"}),
            "custom_field_2": forms.TextInput(attrs={"class": "form-control"}),
            "rate_no": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "due_days": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = SalesInvoiceLine
        fields = ("description", "item_note", "sample_id", "hsn_sac", "quantity", "uom", "batch_number", "rate", "discount_amount", "cgst_rate", "sgst_rate", "igst_rate")
        widgets = {"item_note": forms.Textarea(attrs={"rows": 2, "class": "form-control form-control-sm", "placeholder": "Tests / item note"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False


class SalesInvoiceDetailsForm(forms.ModelForm):
    invoice_type = forms.ChoiceField(
        choices=(("Regular", "Regular"), ("Bill of Supply", "Bill of Supply")),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = SalesInvoice
        fields = (
            "invoice_type", "invoice_date", "claim_number", "po_number", "po_date", "lr_number", "eway_number",
            "challan_number", "challan_date", "due_date", "delivery_mode", "payment_type",
            "terms_title", "terms_detail", "document_remarks", "discount_amount", "discount_mode", "discount_is_addition", "tcs_rate",
            "tcs_mode", "tcs_is_deduction", "additional_charges", "round_off_enabled",
        )
        widgets = {
            "invoice_type": forms.TextInput(attrs={"class": "form-control"}),
            "invoice_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "claim_number": forms.TextInput(attrs={"class": "form-control"}),
            "po_number": forms.TextInput(attrs={"class": "form-control"}),
            "po_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "lr_number": forms.TextInput(attrs={"class": "form-control"}),
            "eway_number": forms.TextInput(attrs={"class": "form-control"}),
            "challan_number": forms.TextInput(attrs={"class": "form-control"}),
            "challan_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "delivery_mode": forms.TextInput(attrs={"class": "form-control"}),
            "payment_type": forms.Select(attrs={"class": "form-select"}),
            "terms_title": forms.TextInput(attrs={"class": "form-control"}),
            "terms_detail": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "document_remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "discount_amount": forms.NumberInput(attrs={"class": "form-control adjustment-value", "step": "0.01", "min": "0"}),
            "discount_mode": forms.Select(attrs={"class": "form-select adjustment-mode", "aria-label": "Discount unit"}),
            "tcs_rate": forms.NumberInput(attrs={"class": "form-control adjustment-value", "step": "0.01", "min": "0"}),
            "tcs_mode": forms.Select(attrs={"class": "form-select adjustment-mode", "aria-label": "TCS unit"}),
            "tcs_is_deduction": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "additional_charges": forms.NumberInput(attrs={"class": "form-control adjustment-value", "step": "0.01", "min": "0"}),
            "round_off_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_type = self.instance.invoice_type
        if current_type and current_type not in dict(self.fields["invoice_type"].choices):
            self.fields["invoice_type"].choices = (*self.fields["invoice_type"].choices, (current_type, current_type))


class InvoiceBuyerSnapshotForm(forms.Form):
    name = forms.CharField(label="Customer / Vendor", max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(label="Address", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    contact_person = forms.CharField(label="Contact Person", required=False, max_length=255, widget=forms.TextInput(attrs={"class": "form-control"}))
    telephone = forms.CharField(label="Phone No.", required=False, max_length=50, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(label="Email", required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    gstin = forms.CharField(label="GSTIN", required=False, max_length=20, widget=forms.TextInput(attrs={"class": "form-control"}))
    pan = forms.CharField(label="PAN", required=False, max_length=20, widget=forms.TextInput(attrs={"class": "form-control"}))
    state_name = forms.CharField(label="State", required=False, max_length=120, widget=forms.TextInput(attrs={"class": "form-control"}))
    state_code = forms.CharField(label="State Code", required=False, max_length=2, widget=forms.TextInput(attrs={"class": "form-control", "maxlength": 2}))
    consignee_address = forms.CharField(label="Shipping Address", required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))

    def __init__(self, *args, snapshot=None, **kwargs):
        kwargs.setdefault("initial", snapshot or {})
        super().__init__(*args, **kwargs)

    def save_to_snapshot(self, snapshot):
        updated = dict(snapshot)
        updated.update(self.cleaned_data)
        return updated


class InvoiceBankDetailsForm(forms.Form):
    selected_bank_detail = forms.ChoiceField(required=False, label="Bank", widget=forms.Select(attrs={"class": "form-select"}))

    for number in range(1, 7):
        for field, label in BANK_DETAIL_LABELS.items():
            locals()[f"bank_{number}_{field}"] = forms.CharField(
                required=False,
                label=label,
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )

    def __init__(self, *args, snapshot=None, **kwargs):
        super().__init__(*args, **kwargs)
        snapshot = snapshot or {}
        self.fields["selected_bank_detail"].widget.attrs["class"] = "form-select"
        banks = list(snapshot.get("bank_details") or [])
        if not banks and any(snapshot.get(key) for key in ("bank_name", "bank_account_name", "bank_account_number", "bank_ifsc", "bank_branch", "upi_id")):
            banks = [{
                "name": snapshot.get("bank_name", ""),
                "account_name": snapshot.get("bank_account_name", ""),
                "account_number": snapshot.get("bank_account_number", ""),
                "ifsc": snapshot.get("bank_ifsc", ""),
                "branch": snapshot.get("bank_branch", ""),
                "upi_id": snapshot.get("upi_id", ""),
            }]
        bank_choices = [("", "Use all configured bank details")]
        for index, bank in enumerate(banks[:6], start=1):
            bank_number = int(bank.get("number") or index)
            bank_label = bank.get("name") or f"Bank Detail {bank_number}"
            if bank.get("account_number"):
                bank_label += f" — {bank['account_number']}"
            bank_choices.append((str(bank_number), bank_label))
        self.fields["selected_bank_detail"].choices = bank_choices
        self.fields["selected_bank_detail"].initial = str(snapshot.get("selected_bank_detail") or (bank_choices[1][0] if len(bank_choices) > 1 else ""))
        for index, bank in enumerate(banks[:6], start=1):
            number = int(bank.get("number") or index)
            for field in BANK_DETAIL_FIELDS:
                self.fields[f"bank_{number}_{field}"].initial = bank.get(field, "")

    def save_to_snapshot(self, snapshot):
        updated = dict(snapshot)
        accounts = []
        for number in range(1, 7):
            account = {field: self.cleaned_data.get(f"bank_{number}_{field}", "").strip() for field in BANK_DETAIL_FIELDS}
            if any(account.values()):
                account["number"] = number
                accounts.append(account)
        updated["bank_details"] = accounts
        updated["selected_bank_detail"] = self.cleaned_data.get("selected_bank_detail", "")
        return updated


class CompanyBillingSettingsForm(forms.ModelForm):
    class Meta:
        model = CompanyBillingSettings
        exclude = ("bank_name", "bank_account_name", "bank_account_number", "bank_ifsc", "bank_branch", "upi_id", "print_upi_qr", "upi_qr_include_amount", "certification")
        labels = {
            **{f"bank_{number}_{field}": f"Bank Detail {number} — {label}" for number in range(1, 7) for field, label in BANK_DETAIL_LABELS.items()},
            "invoice_number_prefix": "Bill number prefix",
            "invoice_number_suffix": "Bill number suffix",
            "invoice_next_sequence": "Next bill number sequence",
        }
        help_texts = {
            "invoice_number_suffix": "Leave blank to use the current financial year, such as 26-27.",
            "invoice_next_sequence": "New bills use this sequence or the next sequence after an existing bill number, whichever is higher.",
            "terms": "This text is added to new bills by default. You can change it on an individual bill before saving.",
        }
        widgets = {
            "invoice_number_prefix": forms.TextInput(attrs={"class": "form-control", "maxlength": 30}),
            "invoice_number_suffix": forms.TextInput(attrs={"class": "form-control", "maxlength": 20}),
            "invoice_next_sequence": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "terms": forms.Textarea(attrs={"rows": 3}),
            "certification": forms.Textarea(attrs={"rows": 2}),
            "address": forms.Textarea(attrs={"rows": 3}),
            **{f"bank_{number}_{field}": forms.TextInput(attrs={"class": "form-control"}) for number in range(1, 7) for field in BANK_DETAIL_FIELDS},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")

    def clean_invoice_number_prefix(self):
        value = self.cleaned_data["invoice_number_prefix"].strip().strip("/")
        if not value:
            raise forms.ValidationError("Enter a bill number prefix.")
        return value

    def clean_invoice_number_suffix(self):
        value = self.cleaned_data["invoice_number_suffix"].strip().strip("/")
        if "/" in value:
            raise forms.ValidationError("The bill number suffix must not contain a slash.")
        return value


class CompanyBrandingForm(forms.ModelForm):
    class Meta:
        model = CompanyBillingSettings
        fields = ("legal_name", "logo")
        labels = {"legal_name": "Company name", "logo": "Company logo"}
        help_texts = {
            "legal_name": "This name appears in the application header.",
            "logo": "This logo appears beside the company name in the application header.",
        }
        widgets = {"legal_name": forms.TextInput(attrs={"class": "form-control"})}


class InvoiceCustomerMasterListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "bookings.manage_invoice_customers"
    model = InvoiceCustomerMaster
    template_name = "bookings/invoice_customer_list.html"
    context_object_name = "customers"
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(gstin__icontains=search) | Q(telephone__icontains=search) | Q(contact_person__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context


class InvoiceCustomerMasterCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "bookings.manage_invoice_customers"
    model = InvoiceCustomerMaster
    form_class = InvoiceCustomerMasterForm
    template_name = "bookings/invoice_customer_form.html"

    def get_success_url(self):
        messages.success(self.request, "Sales Invoice customer saved.")
        return reverse("bookings:invoice_customer_list")


class InvoiceCustomerMasterUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "bookings.manage_invoice_customers"
    model = InvoiceCustomerMaster
    form_class = InvoiceCustomerMasterForm
    template_name = "bookings/invoice_customer_form.html"

    def get_success_url(self):
        messages.success(self.request, "Sales Invoice customer updated.")
        return reverse("bookings:invoice_customer_list")


def _split_legacy_invoice_header(source):
    """Pull the first outer table out of a pre-split invoice template."""
    depth = 0
    start = None
    for match in re.finditer(r"</?table\b[^>]*>", source, flags=re.IGNORECASE):
        if match.group(0).lstrip().startswith("</"):
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    header = source[start:match.end()]
                    body = (source[:start] + source[match.end():]).strip()
                    return header, body
        else:
            if depth == 0:
                start = match.start()
            depth += 1
    return "", source


class InvoicePrintTemplateForm(forms.ModelForm):
    class Meta:
        model = InvoicePrintTemplateMaster
        fields = ("header_content", "content")
        widgets = {
            "header_content": forms.Textarea(attrs={"class": "form-control", "rows": 12, "data-editor": "tinymce"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 30, "data-editor": "tinymce"}),
        }

    def clean_header_content(self):
        content = self.cleaned_data["header_content"]
        try:
            Template(content)
        except (TemplateSyntaxError, VariableDoesNotExist) as error:
            raise forms.ValidationError(f"Header template syntax error: {error}") from error
        return content

    def clean_content(self):
        content = self.cleaned_data["content"]
        try:
            Template(content)
        except (TemplateSyntaxError, VariableDoesNotExist) as error:
            raise forms.ValidationError(f"Template syntax error: {error}") from error
        return content


class InvoicePrintTemplateMasterView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "bookings.manage_company_billing_settings"
    form_class = InvoicePrintTemplateForm
    template_name = "bookings/invoice_print_template_master.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = InvoicePrintTemplateMaster.current()
        kwargs["instance"] = instance
        if self.request.method == "GET":
            if instance.header_content:
                kwargs["initial"] = {"header_content": instance.header_content, "content": instance.content or DEFAULT_INVOICE_TEMPLATE}
            elif instance.content:
                legacy_header, body = _split_legacy_invoice_header(instance.content)
                kwargs["initial"] = {
                    "header_content": legacy_header or DEFAULT_INVOICE_HEADER,
                    "content": body if legacy_header else instance.content,
                }
            else:
                kwargs["initial"] = {"header_content": DEFAULT_INVOICE_HEADER, "content": DEFAULT_INVOICE_TEMPLATE}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["default_template"] = DEFAULT_INVOICE_TEMPLATE
        return context

    def form_valid(self, form):
        template = form.save(commit=False)
        template.pk = 1
        template.save()
        messages.success(self.request, "The repeating invoice header and invoice body template were saved.")
        return redirect("bookings:sales_invoice_list")


class SalesInvoicePrintView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "bookings.view_salesinvoice"
    template_name = "bookings/sales_invoice_print.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = get_object_or_404(SalesInvoice.objects.prefetch_related("lines"), pk=self.kwargs["pk"])
        settings = CompanyBillingSettings.current()
        company = _new_invoice_company_snapshot(settings)
        company.update(invoice.company_snapshot or {})
        company["terms"] = company.get("terms") or settings.terms
        company["show_terms"] = bool(invoice.terms_detail or company.get("terms"))
        buyer = {key: "" for key in ("name", "address", "consignee_address", "contact_person", "telephone", "email", "gstin", "pan", "state_name", "state_code")}
        buyer.update(invoice.buyer_snapshot or {})
        if not company.get("logo_url") and settings.logo:
            try:
                company["logo_url"] = settings.logo.url
            except ValueError:
                company["logo_url"] = ""
        banks = list(company.get("bank_details") or _bank_details_for(settings))
        selected_bank = str(company.get("selected_bank_detail") or "")
        if selected_bank:
            selected = [bank for bank in banks if str(bank.get("number", "")) == selected_bank]
            if selected:
                banks = selected
        lines = invoice.lines.all()
        qr_data = _invoice_qr_data(invoice, company)
        values = {
            "invoice": invoice,
            "buyer": buyer,
            "company": company,
            "lines": lines,
            "bank_details": banks,
            "qr_data": qr_data,
            "total_words": _amount_words(invoice.grand_total),
        }
        master = InvoicePrintTemplateMaster.current()
        source = master.content.strip()
        header_source = master.header_content.strip()
        if not header_source and source:
            legacy_header, source_without_header = _split_legacy_invoice_header(source)
            if legacy_header:
                header_source = legacy_header
                source = source_without_header
        if not header_source:
            header_source = DEFAULT_INVOICE_HEADER
        if not source:
            source = DEFAULT_INVOICE_TEMPLATE
        try:
            rendered = Template(source).render(Context(values))
            rendered_header = Template(header_source).render(Context(values))
        except TemplateSyntaxError as error:
            context["template_error"] = str(error)
            rendered = ""
            rendered_header = ""
        context["rendered_invoice"] = mark_safe(rendered)
        context["rendered_header"] = mark_safe(rendered_header)
        context["invoice"] = invoice
        return context


class SalesInvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "bookings.view_salesinvoice"
    model = SalesInvoice
    template_name = "bookings/sales_invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().annotate(total_quantity=Sum("lines__quantity"))
        status = self.request.GET.get("status", "").strip()
        if status in {SalesInvoice.Status.DRAFT, SalesInvoice.Status.FINALIZED}:
            queryset = queryset.filter(status=status)
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=query)
                | Q(buyer_snapshot__name__icontains=query)
                | Q(challan_number__icontains=query)
                | Q(po_number__icontains=query)
            )
        return queryset.order_by("-invoice_date", "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        selected_status = self.request.GET.get("status", "").strip()
        context["selected_status"] = selected_status if selected_status in {SalesInvoice.Status.DRAFT, SalesInvoice.Status.FINALIZED} else ""
        return context


class SalesInvoiceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "bookings.manage_sales_invoices"

    def post(self, request, pk):
        with transaction.atomic():
            invoice = get_object_or_404(SalesInvoice.objects.select_for_update(), pk=pk)
            invoice_label = invoice.invoice_number or f"Draft #{invoice.pk}"
            if invoice.status == SalesInvoice.Status.FINALIZED and invoice.invoice_number:
                number_settings, _ = CompanyBillingSettings.objects.get_or_create(pk=1)
                number_settings = CompanyBillingSettings.objects.select_for_update().get(pk=number_settings.pk)
                parts = invoice.invoice_number.rsplit("/", 2)
                configured_prefix = number_settings.invoice_number_prefix.strip().strip("/") or "ARL/IN"
                if len(parts) == 3 and parts[0] == configured_prefix and parts[1].isdigit():
                    number_settings.invoice_next_sequence = max(number_settings.invoice_next_sequence, int(parts[1]) + 1)
                    number_settings.save(update_fields=["invoice_next_sequence", "updated_at"])
            invoice.delete()
        messages.success(request, f"{invoice_label} was deleted.")
        return redirect("bookings:sales_invoice_list")


class SalesInvoiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "bookings.manage_sales_invoices"
    form_class = InvoiceCreateForm
    template_name = "bookings/sales_invoice_create.html"

    def get_initial(self):
        initial = super().get_initial()
        settings = CompanyBillingSettings.current()
        initial.update(
            payment_type=SalesInvoice.PaymentType.CREDIT,
            terms_title="Terms and Conditions",
            terms_detail=settings.terms,
        )
        requested_ids = self.request.GET.getlist("booking_id")
        selected = list(Booking.objects.filter(
            pk__in=requested_ids,
            report__final_outcome=Report.FinalOutcome.PASS,
        ).select_related("customer"))
        if selected:
            party_name = selected[0].customer.name if selected[0].customer_id else ""
            if party_name and all(booking.customer and booking.customer.name.strip().casefold() == party_name.strip().casefold() for booking in selected):
                matched_customer = InvoiceCustomerMaster.objects.filter(
                    is_active=True,
                    company_type__in=(InvoiceCustomerMaster.CompanyType.CUSTOMER, InvoiceCustomerMaster.CompanyType.BOTH),
                    name__iexact=party_name,
                ).first()
                if matched_customer:
                    initial["invoice_customer"] = matched_customer.pk
                    if matched_customer.due_days:
                        initial["due_date"] = timezone.localdate() + timedelta(days=matched_customer.due_days)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        buyer_initial = {}
        selected_customer_note = ""
        customer_id = form["invoice_customer"].value()
        if customer_id:
            customer = form.fields["invoice_customer"].queryset.filter(pk=customer_id).first()
            if customer:
                selected_customer_note = customer.note
                buyer_initial = {
                    "name": customer.name,
                    "address": customer.invoice_billing_address,
                    "consignee_address": customer.consignee_address or customer.invoice_billing_address,
                    "gstin": customer.gstin,
                    "pan": customer.pan,
                    "state_code": customer.state_code,
                    "state_name": customer.state_name,
                    "contact_person": customer.contact_person,
                    "telephone": customer.telephone,
                    "email": customer.email,
                }
        context["buyer_form"] = kwargs.get("buyer_form") or InvoiceBuyerSnapshotForm(initial=buyer_initial)
        context["selected_customer_note"] = selected_customer_note
        company_snapshot = _new_invoice_company_snapshot(CompanyBillingSettings.current())
        context["bank_form"] = kwargs.get("bank_form") or InvoiceBankDetailsForm(snapshot=company_snapshot)
        draft_query = self.request.GET.get("draft_q", "").strip()
        drafts = SalesInvoice.objects.filter(status=SalesInvoice.Status.DRAFT).order_by("-updated_at", "-pk")
        if draft_query:
            drafts = drafts.filter(
                Q(invoice_number__icontains=draft_query)
                | Q(buyer_snapshot__name__icontains=draft_query)
                | Q(challan_number__icontains=draft_query)
                | Q(po_number__icontains=draft_query)
            )
        context["draft_invoices"] = drafts[:100]
        context["draft_search_query"] = draft_query
        rows = getattr(form, "manual_rows", []) if form.is_bound else []
        if not form.is_bound:
            selected_ids = self.request.GET.getlist("booking_id")
            selected_bookings = form.available_bookings.filter(pk__in=selected_ids).prefetch_related("test_to_be_performed")
            for booking in selected_bookings:
                booking_id = str(booking.pk)
                tests = ", ".join(test.name for test in booking.test_to_be_performed.all())
                rows.append({
                    "item_description": booking.sample_name.display_name if booking.sample_name else "Laboratory service",
                    "item_note": f"Tests: {tests}" if tests else "",
                    "item_batch_number": booking.batch_no,
                    "item_booking_id": booking_id,
                })
        context["item_rows"] = rows or [{}]
        context["from_data_sheet"] = self.request.GET.get("from_data_sheet") == "1"
        context["selected_sample_count"] = sum(bool(row.get("item_booking_id")) for row in rows)
        return context

    def form_invalid(self, form):
        settings = CompanyBillingSettings.current()
        company_snapshot = _new_invoice_company_snapshot(settings)
        return self.render_to_response(self.get_context_data(
            form=form,
            buyer_form=InvoiceBuyerSnapshotForm(self.request.POST),
            bank_form=InvoiceBankDetailsForm(self.request.POST, snapshot=company_snapshot),
        ))

    def form_valid(self, form):
        save_action = self.request.POST.get("save_action", "draft")
        finalize_now = save_action == "finalize"
        if finalize_now and not self.request.user.has_perm("bookings.finalize_salesinvoice"):
            raise PermissionDenied

        buyer = form.cleaned_data["invoice_customer"]
        settings = CompanyBillingSettings.current()
        company_data = _new_invoice_company_snapshot(settings)
        buyer_form = InvoiceBuyerSnapshotForm(self.request.POST)
        bank_form = InvoiceBankDetailsForm(self.request.POST, snapshot=company_data)
        if not buyer_form.is_valid() or not bank_form.is_valid():
            return self.render_to_response(self.get_context_data(form=form, buyer_form=buyer_form, bank_form=bank_form))
        buyer_data = buyer_form.save_to_snapshot({})
        buyer_data["note"] = buyer.note
        company_data = bank_form.save_to_snapshot(company_data)
        if finalize_now:
            if not company_data.get("gstin"):
                form.add_error(None, "Company GSTIN is required to finalize the invoice.")
            if not buyer_data.get("gstin"):
                form.add_error(None, "Customer GSTIN is required to finalize the invoice.")
            rows = form.cleaned_data["manual_items"]
            if any(
                not item["item_description"].strip()
                or not item["item_hsn_sac"].strip()
                or item["quantity"] is None or item["quantity"] <= 0
                or item["rate"] is None or item["rate"] <= 0
                or not item["item_tax_type"]
                for item in rows
            ):
                form.add_error(None, "To finalize, every item needs a product name, HSN/SAC, positive quantity and rate, and GST type and rate.")
            if form.errors:
                return self.render_to_response(self.get_context_data(form=form, buyer_form=buyer_form, bank_form=bank_form))
        with transaction.atomic():
            number_settings = CompanyBillingSettings.objects.select_for_update().get(pk=settings.pk)
            number_prefix = number_settings.invoice_number_prefix.strip().strip("/") or "ARL/IN"
            number_suffix = number_settings.invoice_number_suffix.strip().strip("/") or _invoice_fy_suffix(form.cleaned_data["invoice_date"])
            invoice_number = _format_invoice_number(
                number_prefix,
                _next_invoice_sequence(form.cleaned_data["invoice_date"], number_prefix, number_suffix),
                number_suffix,
            )
            invoice = SalesInvoice.objects.create(
                invoice_customer=buyer,
                invoice_date=form.cleaned_data["invoice_date"],
                invoice_type=form.cleaned_data["invoice_type"],
                invoice_number=invoice_number,
                claim_number=form.cleaned_data["claim_number"],
                challan_number=form.cleaned_data["challan_number"],
                challan_date=form.cleaned_data["challan_date"],
                po_number=form.cleaned_data["po_number"],
                po_date=form.cleaned_data["po_date"],
                lr_number=form.cleaned_data["lr_number"],
                eway_number=form.cleaned_data["eway_number"],
                delivery_mode=form.cleaned_data["delivery_mode"],
                due_date=form.cleaned_data["due_date"] or (form.cleaned_data["invoice_date"] + timedelta(days=buyer.due_days or 0) if buyer.due_days else None),
                payment_type=form.cleaned_data["payment_type"] or SalesInvoice.PaymentType.CREDIT,
                discount_amount=form.cleaned_data.get("discount_amount") or Decimal("0.00"),
                discount_mode=form.cleaned_data.get("discount_mode") or SalesInvoice.AdjustmentMode.AMOUNT,
                discount_is_addition=form.cleaned_data.get("discount_is_addition", False),
                tcs_rate=form.cleaned_data.get("tcs_rate") or Decimal("0.00"),
                tcs_mode=form.cleaned_data.get("tcs_mode") or SalesInvoice.AdjustmentMode.PERCENT,
                tcs_is_deduction=form.cleaned_data.get("tcs_is_deduction", False),
                additional_charges=form.cleaned_data.get("additional_charges") or Decimal("0.00"),
                round_off_enabled=form.cleaned_data.get("round_off_enabled", False),
                terms_title=form.cleaned_data["terms_title"] or "Terms and Conditions",
                terms_detail=form.cleaned_data["terms_detail"] or settings.terms,
                document_remarks=form.cleaned_data["document_remarks"],
                buyer_snapshot=buyer_data,
                company_snapshot=company_data,
                created_by=self.request.user,
            )
            for index, item in enumerate(form.cleaned_data["manual_items"]):
                tax_type = item["item_tax_type"]
                tax_rate = item["tax_rate"]
                tax_fields = {"cgst_rate": None, "sgst_rate": None, "igst_rate": None}
                if tax_type == "split":
                    tax_fields.update(cgst_rate=tax_rate / Decimal("2"), sgst_rate=tax_rate / Decimal("2"), igst_rate=Decimal("0"))
                elif tax_type == "integrated":
                    tax_fields.update(cgst_rate=Decimal("0"), sgst_rate=Decimal("0"), igst_rate=tax_rate)
                SalesInvoiceLine.objects.create(
                    invoice=invoice,
                    booking_id=item["booking_id"] if item.get("booking_id") else None,
                    description=item["item_description"],
                    item_note=item["item_note"],
                    sample_id=item["item_sample_id"],
                    hsn_sac=item["item_hsn_sac"],
                    quantity=item["quantity"],
                    uom=item["item_uom"],
                    batch_number=item["item_batch_number"],
                    rate=item["rate"],
                    discount_amount=item["discount_amount"] if item["item_discount"] else None,
                    position=index,
                    **tax_fields,
                )
            if finalize_now:
                invoice.status = SalesInvoice.Status.FINALIZED
                invoice.finalized_by = self.request.user
                invoice.finalized_at = timezone.now()
                invoice.save(update_fields=["invoice_number", "status", "finalized_by", "finalized_at", "updated_at"])
        if finalize_now:
            messages.success(self.request, "Invoice finalized and added to the sales invoice list.")
        else:
            messages.success(self.request, "Draft invoice saved and added to the sales invoice list.")
        return redirect("bookings:sales_invoice_list")


class InvoiceBatchSampleLookupView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "bookings.manage_sales_invoices"

    def get(self, request):
        batch_number = request.GET.get("batch", "").strip()
        customer_id = request.GET.get("customer", "").strip()
        if not batch_number or not customer_id:
            return JsonResponse({"items": [], "error": "Choose a customer and enter a batch number."}, status=400)
        customer = get_object_or_404(
            InvoiceCustomerMaster.objects.filter(is_active=True),
            pk=customer_id,
        )
        bookings = Booking.objects.filter(
            batch_no__iexact=batch_number,
            report__final_outcome=Report.FinalOutcome.PASS,
            customer__name__iexact=customer.name,
        ).select_related("sample_name").prefetch_related("test_to_be_performed").distinct()
        items = []
        for booking in bookings:
            tests = [test.name for test in booking.test_to_be_performed.all()]
            items.append({
                "booking_id": booking.pk,
                "description": booking.sample_name.display_name if booking.sample_name else "Laboratory service",
                "note": f"Tests: {', '.join(tests)}" if tests else "",
                "batch_number": booking.batch_no,
            })
        return JsonResponse({"items": items})


class SalesInvoiceEditView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "bookings.manage_sales_invoices"
    template_name = "bookings/sales_invoice_edit.html"

    def dispatch(self, request, *args, **kwargs):
        self.invoice = get_object_or_404(SalesInvoice, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            invoice=self.invoice,
            line_forms=[InvoiceLineForm(instance=line, prefix=f"line-{line.pk}") for line in self.invoice.lines.all()],
            bank_form=InvoiceBankDetailsForm(snapshot=self.invoice.company_snapshot),
            buyer_form=InvoiceBuyerSnapshotForm(snapshot=self.invoice.buyer_snapshot),
            total_words=_amount_words(self.invoice.grand_total),
            invoice_form=SalesInvoiceDetailsForm(instance=self.invoice),
        )
        return context

    def post(self, request, *args, **kwargs):
        add_line = bool(request.POST.get("add_line"))
        save_action = request.POST.get("save_action", "draft")
        finalize_now = save_action == "pass"
        lines = list(self.invoice.lines.all())
        forms = [InvoiceLineForm(request.POST, instance=line, prefix=f"line-{line.pk}") for line in lines]
        bank_form = InvoiceBankDetailsForm(request.POST, snapshot=self.invoice.company_snapshot)
        buyer_form = InvoiceBuyerSnapshotForm(request.POST, snapshot=self.invoice.buyer_snapshot)
        invoice_form = SalesInvoiceDetailsForm(request.POST, instance=self.invoice)
        if all(form.is_valid() for form in forms) and bank_form.is_valid() and buyer_form.is_valid() and invoice_form.is_valid():
            if finalize_now and not request.user.has_perm("bookings.finalize_salesinvoice"):
                raise PermissionDenied
            if finalize_now:
                company_snapshot = bank_form.save_to_snapshot(self.invoice.company_snapshot)
                buyer_snapshot = buyer_form.save_to_snapshot(self.invoice.buyer_snapshot)
                has_invalid_line = any(
                    not (form.cleaned_data.get("description") or "").strip()
                    or not form.cleaned_data.get("hsn_sac")
                    or form.cleaned_data.get("quantity") is None or form.cleaned_data["quantity"] <= 0
                    or form.cleaned_data.get("rate") is None or form.cleaned_data["rate"] <= 0
                    or form.cleaned_data.get("cgst_rate") is None
                    or form.cleaned_data.get("sgst_rate") is None
                    or form.cleaned_data.get("igst_rate") is None
                    for form in forms
                )
                if not company_snapshot.get("gstin"):
                    invoice_form.add_error(None, "Company GSTIN is required to pass the invoice.")
                if not buyer_snapshot.get("gstin"):
                    invoice_form.add_error(None, "Customer GSTIN is required to pass the invoice.")
                if not forms or has_invalid_line:
                    invoice_form.add_error(None, "Each item needs a product name, HSN/SAC, positive quantity and rate, and CGST, SGST, and IGST rates (enter 0 for non-applicable taxes).")
                if invoice_form.errors:
                    return self.render_to_response(self.get_context_data(line_forms=forms, bank_form=bank_form, buyer_form=buyer_form, invoice_form=invoice_form))

            with transaction.atomic():
                for form in forms:
                    form.save()
                invoice_form.save()
                self.invoice.buyer_snapshot = buyer_form.save_to_snapshot(self.invoice.buyer_snapshot)
                self.invoice.company_snapshot = bank_form.save_to_snapshot(self.invoice.company_snapshot)
                if finalize_now:
                    number_settings, _ = CompanyBillingSettings.objects.get_or_create(pk=1)
                    CompanyBillingSettings.objects.select_for_update().get(pk=number_settings.pk)
                    if not self.invoice.invoice_number:
                        prefix, suffix, _ = _invoice_number_defaults(self.invoice.invoice_date)
                        self.invoice.invoice_number = _format_invoice_number(
                            prefix,
                            _next_invoice_sequence(self.invoice.invoice_date, prefix, suffix),
                            suffix,
                        )
                    self.invoice.status = SalesInvoice.Status.FINALIZED
                    self.invoice.finalized_by = request.user
                    self.invoice.finalized_at = timezone.now()
                update_fields = ["buyer_snapshot", "company_snapshot", "updated_at"]
                if finalize_now:
                    update_fields.extend(["invoice_number", "status", "finalized_by", "finalized_at"])
                self.invoice.save(update_fields=update_fields)
            if add_line:
                SalesInvoiceLine.objects.create(invoice=self.invoice, description="", position=self.invoice.lines.count())
                return redirect("bookings:sales_invoice_edit", pk=self.invoice.pk)
            if finalize_now:
                messages.success(request, "Invoice passed and finalized.")
            elif self.invoice.status == SalesInvoice.Status.FINALIZED:
                messages.success(request, "Invoice changes saved.")
            else:
                messages.success(request, "Draft invoice saved.")
            return redirect("bookings:sales_invoice_list")
        return self.render_to_response(self.get_context_data(line_forms=forms, bank_form=bank_form, buyer_form=buyer_form, invoice_form=invoice_form))


def _bank_details_for(settings):
    details = []
    for number in range(1, 7):
        account = {field: getattr(settings, f"bank_{number}_{field}", "") or "" for field in BANK_DETAIL_FIELDS}
        account["number"] = number
        if number == 1:
            account["account_name"] = account["account_name"] or settings.bank_account_name
            account["name"] = account["name"] or settings.bank_name
            account["ifsc"] = account["ifsc"] or settings.bank_ifsc
            account["account_number"] = account["account_number"] or settings.bank_account_number
            account["branch"] = account["branch"] or settings.bank_branch
            account["upi_id"] = account["upi_id"] or settings.upi_id
        if any(account.values()):
            details.append(account)
    return details


def _new_invoice_company_snapshot(settings):
    company = {
        field: getattr(settings, field)
        for field in (
            "legal_name", "address", "contact_person", "phone", "email", "website", "pan", "gstin",
            "state_code", "bank_name", "bank_account_name", "bank_account_number", "bank_ifsc", "bank_branch",
            "upi_id", "terms",
        )
    }
    company["bank_details"] = _bank_details_for(settings)
    company["selected_bank_detail"] = str(company["bank_details"][0]["number"]) if company["bank_details"] else ""
    if settings.logo:
        try:
            company["logo_url"] = settings.logo.url
        except ValueError:
            company["logo_url"] = ""
    return company


def _invoice_qr_data(invoice, company):
    upi_id = str(company.get("upi_id") or "").strip()
    if not upi_id:
        banks = company.get("bank_details") or []
        upi_id = next((str(bank.get("upi_id") or "").strip() for bank in banks if bank.get("upi_id")), "")
    if not upi_id:
        return ""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
        params = {"pa": upi_id, "pn": company.get("legal_name", ""), "cu": "INR", "tn": invoice.invoice_number or f"Draft {invoice.pk}", "am": f"{invoice.grand_total:.2f}"}
        stream = BytesIO()
        qrcode.make("upi://pay?" + urlencode(params), image_factory=SvgPathImage).save(stream)
        return "data:image/svg+xml;base64," + base64.b64encode(stream.getvalue()).decode("ascii")
    except ImportError:
        return ""


class SalesInvoiceFinalizeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "bookings.finalize_salesinvoice"

    def post(self, request, pk):
        with transaction.atomic():
            invoice = get_object_or_404(SalesInvoice.objects.select_for_update(), pk=pk)
            if invoice.status != SalesInvoice.Status.DRAFT:
                messages.error(request, "This invoice is already finalized and cannot be changed.")
                return redirect("bookings:sales_invoice_list")
            lines = list(invoice.lines.all())
            errors = []
            company = invoice.company_snapshot
            if not company.get("gstin"): errors.append("Company GSTIN is required")
            if not invoice.buyer_snapshot.get("gstin"): errors.append("Buyer GSTIN is required")
            if not lines: errors.append("At least one line item is required")
            if any(not line.description.strip() or not line.hsn_sac or line.rate is None or line.rate <= 0 or line.quantity is None or line.quantity <= 0 or line.cgst_rate is None or line.sgst_rate is None or line.igst_rate is None for line in lines): errors.append("Each line needs a product name, HSN/SAC, a positive quantity and rate, and explicit CGST, SGST, and IGST rates (enter 0 for non-applicable components)")
            if errors:
                messages.error(request, "; ".join(errors) + ".")
                return redirect("bookings:sales_invoice_edit", pk=pk)
            CompanyBillingSettings.objects.select_for_update().get_or_create(pk=1)
            if not invoice.invoice_number:
                prefix, suffix, _ = _invoice_number_defaults(invoice.invoice_date)
                invoice.invoice_number = _format_invoice_number(
                    prefix,
                    _next_invoice_sequence(invoice.invoice_date, prefix, suffix),
                    suffix,
                )
            invoice.status = SalesInvoice.Status.FINALIZED
            invoice.finalized_by = request.user
            invoice.finalized_at = timezone.now()
            invoice.save(update_fields=["invoice_number", "status", "finalized_by", "finalized_at", "updated_at"])
        messages.success(request, "Invoice finalized and assigned an invoice number.")
        return redirect(f"{reverse('bookings:sales_invoice_list')}?status={SalesInvoice.Status.FINALIZED}")


class CompanyBillingSettingsView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "bookings.manage_company_billing_settings"
    form_class = CompanyBillingSettingsForm
    template_name = "bookings/invoice_settings.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = CompanyBillingSettings.current()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        context["numbering_fields"] = [form[name] for name in ("invoice_number_prefix", "invoice_next_sequence", "invoice_number_suffix")]
        company_field_names = ("legal_name", "address", "contact_person", "phone", "email", "website", "pan", "gstin", "state_code", "logo")
        context["company_fields"] = [form[name] for name in company_field_names if name in form.fields]
        context["bank_groups"] = []
        for number in range(1, 7):
            fields = [form[f"bank_{number}_{field}"] for field in BANK_DETAIL_FIELDS]
            context["bank_groups"].append({
                "number": number,
                "fields": fields,
                "has_data": any(field.value() for field in fields),
                "has_errors": any(field.errors for field in fields),
            })
        context["default_terms_field"] = form["terms"] if "terms" in form.fields else None
        return context

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Invoice company settings saved. They apply to new invoices.")
        return redirect("bookings:sales_invoice_list")


class CompanyBrandingMasterView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "bookings.manage_company_billing_settings"
    form_class = CompanyBrandingForm
    template_name = "bookings/company_branding_master.html"

    def has_permission(self):
        return (
            super().has_permission()
            or self.request.user.groups.filter(name="Admin").exists()
        )

    def get_object(self, queryset=None):
        return CompanyBillingSettings.current()

    def get_success_url(self):
        return reverse("dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Company name and logo updated.")
        return super().form_valid(form)


def _amount_words(amount):
    ones = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
    def under_thousand(n):
        out = []
        if n >= 100:
            out.extend((ones[n // 100], "hundred")); n %= 100
        if n >= 20:
            out.append(tens[n // 10]); n %= 10
        if n:
            out.append(ones[n])
        return " ".join(out)
    n = int(Decimal(amount))
    if not n:
        words = "zero"
    else:
        parts = []
        for size, name in ((10000000, "crore"), (100000, "lakh"), (1000, "thousand"), (1, "")):
            value, n = divmod(n, size)
            if value:
                parts.append((under_thousand(value) + (" " + name if name else "")).strip())
        words = " ".join(parts)
    paise = int((Decimal(amount) % 1 * 100).quantize(Decimal("1")))
    return f"{words.title()} Rupees" + (f" and {under_thousand(paise).title()} Paise" if paise else " Only")

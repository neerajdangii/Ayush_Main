from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CustomerMaster, SalesInvoice, SalesInvoiceLine


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SalesInvoiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="invoice-user", password="test")
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label="bookings", codename__in=("view_salesinvoice", "manage_sales_invoices", "finalize_salesinvoice")))
        self.client.force_login(self.user)
        buyer = CustomerMaster.objects.create(name="Example Party", gstin="27ABCDE1234F1Z5", state_code="27")
        self.invoice = SalesInvoice.objects.create(buyer=buyer, buyer_snapshot={"name": "Example Party", "gstin": "27ABCDE1234F1Z5"}, company_snapshot={"legal_name": "Ayush Research Laboratories Private Limited", "gstin": "27ABCDE1234F1Z5"}, created_by=self.user)
        self.line = SalesInvoiceLine.objects.create(invoice=self.invoice, description="Laboratory analysis", sample_id="ARL/GEN/0001", hsn_sac="998346", quantity=Decimal("2"), rate=Decimal("100.00"), cgst_rate=Decimal("9"), sgst_rate=Decimal("9"), igst_rate=Decimal("0"))

    def test_decimal_totals_are_server_calculated(self):
        self.assertEqual(self.line.taxable_value, Decimal("200.00"))
        self.assertEqual(self.line.cgst_amount, Decimal("18.00"))
        self.assertEqual(self.line.sgst_amount, Decimal("18.00"))
        self.assertEqual(self.invoice.grand_total, Decimal("236.00"))

    def test_finalize_requires_explicit_post(self):
        response = self.client.get(reverse("bookings:sales_invoice_finalize", args=[self.invoice.pk]))
        self.assertEqual(response.status_code, 405)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, SalesInvoice.Status.DRAFT)

    def test_explicit_finalize_assigns_number(self):
        response = self.client.post(reverse("bookings:sales_invoice_finalize", args=[self.invoice.pk]))
        self.assertRedirects(response, f"{reverse('bookings:sales_invoice_list')}?status=finalized")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, SalesInvoice.Status.FINALIZED)
        self.assertEqual(self.invoice.invoice_number, f"ARL/{self.invoice.invoice_date.year}/0001")


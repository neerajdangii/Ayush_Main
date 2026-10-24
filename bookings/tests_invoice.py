from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CompanyBillingSettings, CustomerMaster, InvoiceCustomerMaster, SalesInvoice, SalesInvoiceLine


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

    def test_create_finalize_requires_dedicated_permission(self):
        manager = get_user_model().objects.create_user(username="invoice-manager", password="test")
        manage_permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="manage_sales_invoices",
        )
        manager.user_permissions.add(manage_permission)
        self.client.force_login(manager)

        response = self.client.post(reverse("bookings:sales_invoice_create"), self._invoice_create_payload())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SalesInvoice.objects.count(), 1)

    def test_user_with_finalize_permission_can_finalize_during_creation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("bookings:sales_invoice_create"),
            self._invoice_create_payload(),
        )

        self.assertRedirects(response, reverse("bookings:sales_invoice_list"))
        created_invoice = SalesInvoice.objects.exclude(pk=self.invoice.pk).get()
        self.assertEqual(created_invoice.status, SalesInvoice.Status.FINALIZED)
        self.assertEqual(created_invoice.finalized_by, self.user)

    def _invoice_create_payload(self):
        buyer = InvoiceCustomerMaster.objects.create(
            name="Create Invoice Buyer",
            gstin="27ABCDE1234F1Z5",
            state_code="27",
        )
        CompanyBillingSettings.objects.update_or_create(pk=1, defaults={"gstin": "27ABCDE1234F1Z5"})
        return {
            "invoice_customer": buyer.pk,
            "invoice_type": "Regular",
            "invoice_date": "2026-10-23",
            "terms_title": "Terms and Conditions",
            "name": buyer.name,
            "gstin": buyer.gstin,
            "state_code": buyer.state_code,
            "selected_bank_detail": "",
            "item_description": ["Laboratory analysis"],
            "item_sample_id": ["ARL/GEN/0002"],
            "item_hsn_sac": ["998346"],
            "item_quantity": ["1"],
            "item_uom": ["Nos"],
            "item_batch_number": [""],
            "item_rate": ["100.00"],
            "item_discount": ["0"],
            "item_tax_type": ["split"],
            "item_tax_rate": ["18"],
            "item_note": [""],
            "item_booking_id": [""],
            "save_action": "finalize",
        }


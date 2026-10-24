from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from urllib.parse import urlsplit

from bookings.models import Booking, CustomerMaster, SampleNameMaster

from .models import Report, ReportVerificationPortal
from .verification_portal import render_verification_layout
from .views import _get_report_render_context


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ReportVerificationPortalTests(TestCase):
    def setUp(self):
        customer = CustomerMaster.objects.create(name="Portal Customer")
        sample = SampleNameMaster.objects.create(name="Portal Sample")
        self.booking = Booking.objects.create(
            customer=customer,
            sample_name=sample,
            manual_certificate_no="CERT-PORTAL-01",
            status=Booking.Status.APPROVED,
        )
        self.report = Report.objects.create(
            booking=self.booking,
            status=Report.Status.MANAGER_APPROVED,
            final_outcome=Report.FinalOutcome.PASS,
        )

    def test_qr_url_shows_verification_portal_then_public_report(self):
        portal_response = self.client.get(reverse("reports:coa_public", args=[self.report.pk]))

        self.assertEqual(portal_response.status_code, 200)
        self.assertContains(portal_response, "Test Certificate Authenticity Portal")
        self.assertContains(portal_response, "CERT-PORTAL-01")
        self.assertContains(
            portal_response,
            reverse("reports:coa_public_report", args=[self.report.pk]),
        )
        self.assertContains(portal_response, "View Report")
        self.assertNotContains(portal_response, "Edit Report")

        report_response = self.client.get(reverse("reports:coa_public_report", args=[self.report.pk]))
        self.assertEqual(report_response.status_code, 200)
        self.assertNotContains(report_response, "Edit Report")

        test_report_page = self.client.get(
            reverse("reports:coa_public", args=[self.report.pk]),
            {"doc": "test", "plain": "1"},
        )
        self.assertContains(test_report_page, "doc=test&amp;plain=1")

    def test_report_qr_payload_targets_the_verification_portal(self):
        context = _get_report_render_context(
            self.report,
            RequestFactory().get("/reports/1/coa/print/"),
            preview_mode=True,
            auto_print=False,
            is_plain_doc=False,
            is_test_report=False,
        )

        self.assertEqual(
            urlsplit(context["qr_payload"]).path,
            reverse("reports:coa_public", args=[self.report.pk]),
        )

    def test_unapproved_report_stays_hidden_from_public_portal(self):
        self.report.status = Report.Status.DRAFT
        self.report.save(update_fields=["status"])

        self.assertEqual(
            self.client.get(reverse("reports:coa_public", args=[self.report.pk])).status_code,
            404,
        )

    def test_existing_letterhead_manager_permission_controls_portal_master(self):
        user = get_user_model().objects.create_user(username="portal-manager", password="test-password")
        permission = Permission.objects.get(
            content_type__app_label="reports",
            codename="manage_letterheads",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("reports:verification_portal_master")).status_code, 200)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, reverse("reports:verification_portal_master"))

        user.user_permissions.clear()
        self.assertEqual(self.client.get(reverse("reports:verification_portal_master")).status_code, 403)

    def test_internal_report_print_keeps_its_edit_action(self):
        user = get_user_model().objects.create_user(username="report-manager", password="test-password")
        manager_role, _ = Group.objects.get_or_create(name="Manager")
        user.groups.add(manager_role)
        permission = Permission.objects.get(content_type__app_label="reports", codename="view_report")
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(reverse("reports:coa_print", args=[self.report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Report")

    def test_portal_master_updates_only_its_presentation_settings(self):
        user = get_user_model().objects.create_user(username="portal-editor", password="test-password")
        permission = Permission.objects.get(
            content_type__app_label="reports",
            codename="manage_letterheads",
        )
        user.user_permissions.add(permission)
        self.client.force_login(user)
        portal = ReportVerificationPortal.current()
        portal.title = "Original Portal Title"
        portal.save()
        data = {
            field: getattr(portal, field)
            for field in (
                "title", "verified_label", "order_label", "report_label", "customer_label", "sample_label",
                "instruction", "view_report_label", "page_background_color", "panel_background_color",
                "title_background_color", "accent_color", "button_color", "button_text_color", "layout_html",
            )
        }
        data["layout_html"] = "<p>{{SAMPLE_NAME}}</p>"
        data["button_color"] = "#2266CC"
        data["verification_page_enabled"] = "on"
        data["public_report_enabled"] = "on"

        response = self.client.post(reverse("reports:verification_portal_master"), data)

        self.assertRedirects(response, reverse("dashboard"))
        portal.refresh_from_db()
        self.assertEqual(portal.title, "Original Portal Title")
        self.assertEqual(portal.layout_html, "<p>{{SAMPLE_NAME}}</p>")
        self.assertEqual(portal.button_color, "#1673E8")
        self.assertEqual(self.report.certificate_no, "CERT-PORTAL-01")

    def test_verification_only_hides_and_blocks_public_report(self):
        portal = ReportVerificationPortal.current()
        portal.verification_page_enabled = True
        portal.public_report_enabled = False
        portal.save()

        verification = self.client.get(reverse("reports:coa_public", args=[self.report.pk]))
        public_report = self.client.get(reverse("reports:coa_public_report", args=[self.report.pk]))

        self.assertEqual(verification.status_code, 200)
        self.assertNotContains(verification, reverse("reports:coa_public_report", args=[self.report.pk]))
        self.assertEqual(public_report.status_code, 404)

    def test_report_only_redirects_qr_to_report(self):
        portal = ReportVerificationPortal.current()
        portal.verification_page_enabled = False
        portal.public_report_enabled = True
        portal.save()

        verification = self.client.get(reverse("reports:coa_public", args=[self.report.pk]))
        public_report = self.client.get(reverse("reports:coa_public_report", args=[self.report.pk]))

        self.assertRedirects(verification, reverse("reports:coa_public_report", args=[self.report.pk]), fetch_redirect_response=False)
        self.assertEqual(public_report.status_code, 200)

    def test_both_public_options_disabled_return_404(self):
        portal = ReportVerificationPortal.current()
        portal.verification_page_enabled = False
        portal.public_report_enabled = False
        portal.save()

        self.assertEqual(self.client.get(reverse("reports:coa_public", args=[self.report.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("reports:coa_public_report", args=[self.report.pk])).status_code, 404)

    def test_master_exposes_tinymce_and_data_placeholder_help(self):
        user = get_user_model().objects.create_user(username="layout-editor", password="test-password")
        permission = Permission.objects.get(content_type__app_label="reports", codename="manage_letterheads")
        user.user_permissions.add(permission)
        self.client.force_login(user)

        response = self.client.get(reverse("reports:verification_portal_master"))

        self.assertContains(response, 'data-editor="tinymce"')
        self.assertNotContains(response, "Configure the page visitors see")
        self.assertNotContains(response, "Available placeholders:")
        self.assertNotContains(response, "where report data or the report link should appear")
        self.assertNotContains(response, "Portal colors")
        self.assertNotContains(response, "Page background color")

    def test_custom_layout_renders_data_and_report_link_safely(self):
        portal = ReportVerificationPortal.current()
        portal.layout_html = (
            '<h1>{{CUSTOMER_NAME}}</h1><p>{{SAMPLE_NAME}} / {{ORDER_CODE}} / {{REPORT_NUMBER}}</p>'
            '<a href="{{VIEW_REPORT_URL}}">View report</a><script>alert(1)</script>'
            '<p onclick="alert(1)" style="background-image:url(javascript:alert(1));color:#123456">Safe text</p>'
        )
        portal.save()
        response = self.client.get(reverse("reports:coa_public", args=[self.report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal Customer")
        self.assertContains(response, "Portal Sample")
        self.assertContains(response, self.report.certificate_no)
        self.assertContains(response, reverse("reports:coa_public_report", args=[self.report.pk]))
        self.assertNotContains(response, "<script>")
        self.assertNotContains(response, "onclick=")
        self.assertNotContains(response, "javascript:")

    def test_custom_layout_escapes_dynamic_report_values(self):
        self.booking.customer.name = '<img src=x onerror="alert(1)">'
        self.booking.customer.save(update_fields=["name"])

        rendered = render_verification_layout(
            "<p>{{CUSTOMER_NAME}}</p>", self.report, "https://example.test/report/"
        )

        self.assertIn("&lt;img", rendered)
        self.assertNotIn("<img", rendered)

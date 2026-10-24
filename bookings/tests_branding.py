from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import CompanyBillingSettings


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class CompanyBrandingMasterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="branding-admin", password="test-password")
        permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="manage_company_billing_settings",
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

    def test_dashboard_links_to_simple_company_branding_master(self):
        CompanyBillingSettings.objects.update_or_create(
            pk=1,
            defaults={"legal_name": "Example Laboratory"},
        )

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Example Laboratory")
        self.assertContains(response, "Company Name &amp; Logo")
        self.assertContains(response, reverse("bookings:branding_master"))

    def test_master_updates_only_company_name_and_logo(self):
        settings, _ = CompanyBillingSettings.objects.update_or_create(
            pk=1,
            defaults={
                "legal_name": "Old Company Name",
                "invoice_number_prefix": "LAB/INV",
                "bank_1_name": "Existing Bank",
            },
        )

        response = self.client.post(
            reverse("bookings:branding_master"),
            {"legal_name": "New Company Name", "logo": ""},
        )

        self.assertRedirects(response, reverse("dashboard"))
        settings.refresh_from_db()
        self.assertEqual(settings.legal_name, "New Company Name")
        self.assertEqual(settings.invoice_number_prefix, "LAB/INV")
        self.assertEqual(settings.bank_1_name, "Existing Bank")

    def test_user_without_settings_permission_cannot_open_master(self):
        user = get_user_model().objects.create_user(username="regular-user", password="test-password")
        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("bookings:branding_master")).status_code, 403)

    def test_admin_role_can_manage_branding_without_invoice_settings_access(self):
        admin_role, _ = Group.objects.get_or_create(name="Admin")
        admin_user = get_user_model().objects.create_user(
            username="role-admin",
            password="test-password",
        )
        admin_user.groups.add(admin_role)
        self.client.force_login(admin_user)

        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Company Name &amp; Logo")
        self.assertContains(dashboard, reverse("bookings:branding_master"))
        self.assertEqual(self.client.get(reverse("bookings:branding_master")).status_code, 200)
        self.assertEqual(self.client.get(reverse("bookings:invoice_settings")).status_code, 403)

    def test_uploaded_logo_is_displayed_in_the_dashboard_header(self):
        image_bytes = BytesIO()
        Image.new("RGB", (2, 2), color="navy").save(image_bytes, format="PNG")
        logo = SimpleUploadedFile("company.png", image_bytes.getvalue(), content_type="image/png")

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("bookings:branding_master"),
                {"legal_name": "Logo Test Laboratory", "logo": logo},
            )
            self.assertEqual(response.status_code, 302)

            dashboard = self.client.get(reverse("dashboard"))

        self.assertContains(dashboard, "Logo Test Laboratory")
        self.assertContains(dashboard, 'class="navbar-brand-logo"')

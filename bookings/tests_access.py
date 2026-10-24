from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Booking, CustomerMaster, SampleNameMaster
from .roles import ROLE_PERMISSIONS


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class BookingReadPermissionTests(TestCase):
    def setUp(self):
        self.customer = CustomerMaster.objects.create(name="Access Test Customer")
        self.sample = SampleNameMaster.objects.create(name="Access Test Sample")
        self.booking = Booking.objects.create(customer=self.customer, sample_name=self.sample)
        self.list_url = reverse("bookings:list")
        self.detail_url = reverse("bookings:detail", args=[self.booking.pk])
        self.similar_url = reverse("bookings:api_similar_booking_data")
        self.user = get_user_model().objects.create_user(username="booking-reader", password="test-password")

    def test_authenticated_user_without_booking_permission_is_denied(self):
        self.client.force_login(self.user)

        for url in (
            self.list_url,
            self.detail_url,
            f"{self.similar_url}?sample_name_id={self.sample.pk}&customer_id={self.customer.pk}",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_role_user_with_booking_permission_can_read_booking_routes(self):
        permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_booking",
        )
        self.assertIn("bookings.view_booking", ROLE_PERMISSIONS["Analyst"])
        role, _ = Group.objects.get_or_create(name="Analyst")
        role.permissions.add(permission)
        self.user.groups.add(role)
        self.client.force_login(self.user)

        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        similar = self.client.get(
            self.similar_url,
            {"sample_name_id": self.sample.pk, "customer_id": self.customer.pk},
        )
        self.assertEqual(similar.status_code, 200)
        self.assertTrue(similar.json()["found"])
        self.assertEqual(similar.json()["sample_name_id"], self.sample.pk)

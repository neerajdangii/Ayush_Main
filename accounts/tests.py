from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase

from .forms import AdminUserCreateForm, LoginForm
from .models import UserProfile
from .password_validators import MaximumPasswordLengthValidator


class LoginLockoutTests(TestCase):
    def test_third_wrong_password_deactivates_the_account(self):
        user = get_user_model().objects.create_user(username="locked-user", password="valid-password")

        for _ in range(3):
            form = LoginForm(data={"username": user.username, "password": "wrong-password"})
            self.assertFalse(form.is_valid())

        user.refresh_from_db()
        profile = UserProfile.objects.get(user=user)
        self.assertFalse(user.is_active)
        self.assertEqual(profile.failed_login_attempts, 3)

    def test_password_length_policy_rejects_more_than_sixteen_characters(self):
        with self.assertRaisesMessage(ValidationError, "at most 16 characters"):
            MaximumPasswordLengthValidator().validate("a" * 17)


class DelegatedBillingPermissionTests(TestCase):
    def test_view_only_grantor_cannot_enable_billing_management_grant(self):
        grantor = get_user_model().objects.create_user(username="billing-viewer", password="test")
        view_permission = Permission.objects.get(
            content_type__app_label="bookings",
            codename="view_billingrecord",
        )
        grantor.user_permissions.add(view_permission)

        form = AdminUserCreateForm(grantor=grantor)

        self.assertTrue(form.fields["can_manage_billing"].disabled)

    def test_grantor_with_all_billing_permissions_can_still_delegate_them(self):
        grantor = get_user_model().objects.create_user(username="billing-manager", password="test")
        permissions = Permission.objects.filter(
            content_type__app_label="bookings",
            codename__in=("add_billingrecord", "delete_billingrecord", "view_billingrecord"),
        )
        self.assertEqual(permissions.count(), 3)
        grantor.user_permissions.add(*permissions)

        form = AdminUserCreateForm(grantor=grantor)

        self.assertFalse(form.fields["can_manage_billing"].disabled)

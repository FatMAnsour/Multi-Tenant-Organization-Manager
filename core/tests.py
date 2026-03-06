import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from core.models import Organization, Membership, Role, Item
from core.models import Item
from core.models import Item, Membership, Role
from core.models import Membership





User = get_user_model()


pytestmark = [pytest.mark.django_db]


# --- Authentication ---
class TestAuthentication:
    def test_register_creates_user(self, api_client):
        resp = api_client.post(
            "/auth/register",
            {"email": "new@example.com", "password": "StrongPass123!", "full_name": "New User"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "email" in resp.data
        assert resp.data["email"] == "new@example.com"
        assert User.objects.filter(email="new@example.com").exists()
        user = User.objects.get(email="new@example.com")
        assert user.check_password("StrongPass123!")

    def test_login_returns_jwt(self, api_client, user):
        resp = api_client.post(
            "/auth/login",
            {"email": "user@example.com", "password": "StrongPassword123"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access_token" in resp.data
        assert resp.data.get("token_type") == "bearer"

    def test_login_invalid_credentials_401(self, api_client, user):
        resp = api_client.post(
            "/auth/login",
            {"email": "user@example.com", "password": "WrongPassword"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# --- RBAC ---
class TestRBAC:
    def test_create_organization_requires_auth(self, api_client):
        resp = api_client.post(
            "/organization",
            {"org_name": "My Org"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_organization_as_authenticated_user(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            "/organization",
            {"org_name": "Electro Pi"},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "org_id" in resp.data

    def test_invite_user_admin_only(self, api_client, user, org, admin_user):
        api_client.force_authenticate(user=user)
        resp = api_client.post(
            f"/organization/{org.id}/user",
            {"email": "other@example.com", "role": "member"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_invite_user_as_admin_succeeds(self, api_client, admin_user, org, user):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            f"/organization/{org.id}/user",
            {"email": user.email, "role": "member"},
            format="json",
        )
        assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)
        if resp.status_code == 201:
            assert Membership.objects.filter(organization=org, user=user).exists()

    def test_list_org_users_admin_only(self, api_client, user, org, member_in_org):
        api_client.force_authenticate(user=user)
        resp = api_client.get(f"/organizations/{org.id}/users")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_audit_logs_admin_only(self, api_client, user, org, member_in_org):
        api_client.force_authenticate(user=user)
        resp = api_client.get(f"/organizations/{org.id}/audit-logs")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# --- Organization isolation ---
class TestOrganizationIsolation:
    def test_member_sees_only_own_items(self, api_client, user, org, member_in_org, admin_user):
        api_client.force_authenticate(user=user)
        item1 = Item.objects.create(organization=org, created_by=user, details={"a": 1})
        Item.objects.create(organization=org, created_by=admin_user, details={"b": 2})
        resp = api_client.get(f"/organizations/{org.id}/item")
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", [])
        assert len(results) == 1
        assert results[0]["id"] == item1.id

    def test_admin_sees_all_items(self, api_client, admin_user, org, user, member_in_org):
        api_client.force_authenticate(user=admin_user)
        Item.objects.create(organization=org, created_by=user, details={"a": 1})
        Item.objects.create(organization=org, created_by=admin_user, details={"b": 2})
        resp = api_client.get(f"/organizations/{org.id}/item")
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", [])
        assert len(results) == 2

    def test_cannot_access_other_org_data(self, api_client, admin_user, user, db):
        org1 = Organization.objects.create(name="Org 1")
        org2 = Organization.objects.create(name="Org 2")
        Membership.objects.create(user=admin_user, organization=org1, role=Role.ADMIN)
        Membership.objects.create(user=user, organization=org2, role=Role.MEMBER)
        Item.objects.create(organization=org2, created_by=user, details={"secret": True})
        api_client.force_authenticate(user=admin_user)
        resp = api_client.get(f"/organizations/{org2.id}/item")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

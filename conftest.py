"""
Pytest configuration. Uses testcontainers (Postgres) when running tests.
"""
import os
import pytest
from rest_framework.test import APIClient
from testcontainers.postgres import PostgresContainer
from django.contrib.auth import get_user_model
from django.contrib.auth import get_user_model
from core.models import Organization, Membership, Role
from core.models import Membership, Role


def _start_postgres_container():
    postgres = PostgresContainer("postgres:16-alpine")
    postgres.with_env("POSTGRES_DB", "test_org_manager")
    postgres.start()
    return postgres


@pytest.fixture(scope="session")
def postgres_container():
    """Start Postgres once per test session and set env for Django."""
    if os.environ.get("USE_TESTCONTAINERS", "1") != "1":
        yield None
        return
    container = _start_postgres_container()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    os.environ["POSTGRES_HOST"] = host
    os.environ["POSTGRES_PORT"] = port
    os.environ["POSTGRES_DB"] = "test_org_manager"
    os.environ["POSTGRES_USER"] = "postgres"
    os.environ["POSTGRES_PASSWORD"] = "postgres"
    yield container
    container.stop()


@pytest.fixture(scope="session")
def django_db_setup(postgres_container):
    """Configure Django to use testcontainers Postgres."""
    if postgres_container:
        pass


@pytest.fixture
def api_client():
    """DRF API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    User = get_user_model()
    return User.objects.create_user(
        email="user@example.com",
        password="StrongPassword123",
        full_name="Test User",
    )


@pytest.fixture
def admin_user(db):
    """Create a second user (admin of an org)."""
    User = get_user_model()
    return User.objects.create_user(
        email="admin@example.com",
        password="StrongPassword123",
        full_name="Admin User",
    )


@pytest.fixture
def org(admin_user, db):
    """Create an organization with admin_user as Admin."""
    org = Organization.objects.create(name="Test Org")
    Membership.objects.create(user=admin_user, organization=org, role=Role.ADMIN)
    return org


@pytest.fixture
def member_in_org(user, org, db):
    """Add user as member to org."""
    Membership.objects.create(user=user, organization=org, role=Role.MEMBER)
    return org

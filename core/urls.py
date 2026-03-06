"""
API URL configuration.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("auth/register", views.register),
    path("auth/login", views.login),
    # Organization
    path("organization", views.OrganizationCreateView.as_view()),
    path("organization/<int:id>/user", views.OrganizationInviteUserView.as_view()),
    path("organizations/<int:id>/users", views.OrganizationUsersListView.as_view()),
    path("organizations/<int:id>/users/search", views.OrganizationUsersSearchView.as_view()),
    # Items (GET list, POST create on same path)
    path("organizations/<int:id>/item", views.ItemListCreateView.as_view()),
    # Audit & chatbot
    path("organizations/<int:id>/audit-logs", views.AuditLogListView.as_view()),
    path("organizations/<int:id>/audit-logs/ask", views.AuditAskView.as_view()),
]

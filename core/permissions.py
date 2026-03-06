from rest_framework import permissions
from .models import Membership, Role


def get_membership(user, organization_id):
    if not user or not user.is_authenticated:
        return None
    try:
        return Membership.objects.get(user=user, organization_id=organization_id)
    except Membership.DoesNotExist:
        return None


class IsAuthenticated(permissions.IsAuthenticated):
    pass


class IsOrgAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org_id = view.kwargs.get("id") or view.kwargs.get("pk")
        if not org_id:
            return False
        m = get_membership(request.user, org_id)
        return m is not None and m.role == Role.ADMIN


class IsOrgMember(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org_id = view.kwargs.get("id") or view.kwargs.get("pk")
        if not org_id:
            return False
        m = get_membership(request.user, org_id)
        return m is not None


def require_org_membership(view_func):
    # Used via IsOrgMember / IsOrgAdmin on API views
    return view_func

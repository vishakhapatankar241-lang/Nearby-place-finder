from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrAdminReadOnly(BasePermission):
    """Owners can do everything with their place. Admins (is_staff) may only *view* others' places."""

    def has_object_permission(self, request, view, obj):
        if obj.owner_id == request.user.id:
            return True
        return bool(request.user.is_staff and request.method in SAFE_METHODS)

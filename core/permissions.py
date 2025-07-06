from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'Admin'

class IsAccountantUser(BasePermission):
    """
    Allows access only to accountant users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'Accountant'

class IsTraderUser(BasePermission):
    """
    Allows access only to trader users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'Trader'

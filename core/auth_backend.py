from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from core.models import ShopApplication

User = get_user_model()

class ShopApprovalBackend(ModelBackend):
    def user_can_authenticate(self, user):

        # Super admin always allowed
        if user.is_superuser or user.is_staff:
            return True

        # Customers always allowed
        if not user.is_company_admin:
            return True

        # Company admins (shops):
        # 🔥 Allow login even if NOT approved
        # 🔥 But block login only if suspended
        try:
            shop = ShopApplication.objects.get(user=user)
            if shop.is_suspended:
                return False   # suspended = BLOCK
            return True        # allow login even if not approved
        except ShopApplication.DoesNotExist:
            return True


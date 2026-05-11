
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Product, ShopApplication, Complaint, Notification

# ------------------- CUSTOM USER ADMIN ------------------- #
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'full_name',
        'company_name',
        'is_company_admin',
        'is_super_company',
        'payfast_merchant_id',
        'merchant_key',
    )

    list_filter = ("is_super_company", "is_company_admin")

    fieldsets = UserAdmin.fieldsets + (
        (None, {
            "fields": (
                "full_name", "company_name",
                "is_super_company", "is_company_admin",
                "payfast_merchant_id", "merchant_key",
            )
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {
            "fields": (
                "full_name", "company_name",
                "is_super_company", "is_company_admin",
                "payfast_merchant_id", "merchant_key",
            )
        }),
    )


# ------------------- PRODUCT ADMIN ------------------- #
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "barcode", "price", "stock", "company", "created_at")
    search_fields = ("name", "barcode")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.is_company_admin:
            return qs.filter(company=request.user)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and request.user.is_company_admin:
            obj.company = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        if request.user.is_company_admin:
            return ["company"]
        return super().get_readonly_fields(request, obj)


# ------------------- SHOP APPLICATION ADMIN ------------------- #
@admin.register(ShopApplication)
class ShopApplicationAdmin(admin.ModelAdmin):
    list_display = ("business_name", "town", "province", "is_approved", "is_suspended", "created_at")
    list_filter = ("is_approved", "is_suspended", "province")
    search_fields = ("business_name", "town", "province", "user__email")
    ordering = ("-created_at",)


# ------------------- COMPLAINT ADMIN ------------------- #
@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("uuid", "source", "from_user", "about_user", "shop", "status", "created_at")
    list_filter = ("status", "source")
    search_fields = ("uuid", "title", "message", "from_user__username", "about_user__username", "shop__username")


# ------------------- NOTIFICATION ADMIN ------------------- #
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("uuid", "sender", "target_type", "target_user", "title", "created_at")
    list_filter = ("target_type",)
    search_fields = ("title", "message")
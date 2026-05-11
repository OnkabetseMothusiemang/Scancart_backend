from django.contrib import admin
from .models import Order
from core.models import Product

from .models import Receipt, ReceiptItem, ReturnRequest

# Admin for Orders
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "status", "payment_method", "m_payment_id", "created_at")
    search_fields = ("user__username", "m_payment_id")
    list_filter = ("status", "created_at")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "shop", "total", "date", "created_at")
    search_fields = ("user__username", "shop__username", "id")

@admin.register(ReceiptItem)
class ReceiptItemAdmin(admin.ModelAdmin):
    list_display = ("id", "receipt", "name", "price", "qty")
    search_fields = ("name",)

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "receipt", "requester", "status", "return_number", "return_code", "created_at")
    list_filter = ("status",)
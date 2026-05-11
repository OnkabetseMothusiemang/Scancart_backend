import random
import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class CustomUser(AbstractUser):
    # ROLE CHOICES
    ROLE_CHOICES = (
        ('company', 'Head Office'),
        ('warehouse', 'Warehouse Manager'),
        ('branch', 'Branch Manager'),
        ('teller', 'Teller (Returns Staff)'),
        ('guard', 'Security Guard'),  # ← new role
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='company')
    full_name = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)

    # Hierarchy Links
    # If role is Teller, this links them to their specific branch
    assigned_branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name="staff")
    # If role is Warehouse Manager, this links them to their warehouse
    assigned_warehouse = models.ForeignKey('Warehouse', on_delete=models.SET_NULL, null=True, blank=True, related_name="staff")

    is_super_company = models.BooleanField(default=False)
    is_company_admin = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    # Security: Working ID for Tellers (e.g., BR1-T01)
    working_id = models.CharField(max_length=50, unique=True, null=True, blank=True)



    # Payment Integration
    payfast_merchant_id = models.CharField(max_length=50, blank=True, null=True)
    merchant_key = models.CharField(max_length=255, blank=True, null=True)

    groups = models.ManyToManyField(Group, related_name="customuser_set", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="customuser_set", blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class ShopApplication(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=255, blank=True, null=True)
    town = models.CharField(max_length=255, blank=True, null=True)
    province = models.CharField(max_length=255, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.business_name or f"ShopApplication #{self.id}"


class Warehouse(models.Model):
    company = models.ForeignKey(User, on_delete=models.CASCADE, related_name="warehouses")
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    company = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="branches",
        limit_choices_to={"is_company_admin": True}
    )
    name = models.CharField(max_length=255)
    province = models.CharField(max_length=100)
    town = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    wifi_ssid = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.town})"


class Product(models.Model):
    UNIT_CHOICES = [
        ("mg", "Milligram"), ("g", "Gram"), ("kg", "Kilogram"),
        ("ml", "Milliliter"), ("l", "Liter"), ("pcs", "Pieces"),
        ("dozen", "Dozen"), ("box", "Box"), ("pack", "Pack"),
        ("set", "Set"), ("mm", "Millimeter"), ("cm", "Centimeter"),
        ("m", "Meter"), ("sqm", "Square Meter"), ("tube", "Tube"),
        ("bottle", "Bottle"), ("jar", "Jar"), ("bag", "Bag"),
        ("carton", "Carton"), ("can", "Can"),
    ]
    name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=20, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)  # legacy
    unit = models.CharField(max_length=12, choices=UNIT_CHOICES, default="pcs")

    branches = models.ManyToManyField(
        Branch, 
        through='BranchStock', 
        related_name='products'
    )

    
    company = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={"is_company_admin": True},
        related_name="products"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Stock(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_records"
    )
    # Stock can live in a Warehouse OR a Branch
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.IntegerField(default=0)

    def __str__(self):
        if self.warehouse:
            return f"{self.product.name} @ Warehouse: {self.warehouse.name}"
        if self.branch:
            return f"{self.product.name} @ Branch: {self.branch.name}"
        return f"{self.product.name} - Unallocated"


class Complaint(models.Model):
    SOURCE_CHOICES = (("shop", "shop"), ("customer", "customer"))
    STATUS_CHOICES = (("open", "Open"), ("in_review", "In review"), ("resolved", "Resolved"), ("dismissed", "Dismissed"))

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES)
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_complaints")
    about_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_complaints", null=True, blank=True)
    shop = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="shop_complaints")
    title = models.CharField(max_length=255)
    message = models.TextField()
    attachment = models.FileField(upload_to="complaint_attachments/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_response = models.TextField(null=True, blank=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="responses_to_complaints")

    def mark_resolved(self, responder=None, note=None):
        self.status = "resolved"
        if note:
            self.admin_response = note
        self.responded_by = responder
        self.save()


class Notification(models.Model):
    TARGET_TYPE = (("shop", "shop"), ("customer", "customer"), ("all", "all"))
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_notifications")
    target_type = models.CharField(max_length=12, choices=TARGET_TYPE, default="all")
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(null=True, blank=True)

    def mark_read(self):
        self.is_read = True
        self.save()


# Add this to your models.py

class WarehouseStock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stocks")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('warehouse', 'product') # One entry per product per warehouse

    def __str__(self):
        return f"{self.product.name} at {self.warehouse.name}: {self.quantity}"

# Update your BranchStock model in models.py
class BranchStock(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="stocks")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    
    # NEW FIELDS FOR SPECIALS
    special_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    special_expiry = models.DateField(null=True, blank=True)
    
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'product')

    @property
    def current_price(self):
        """Returns the special price if it's active, otherwise the master price."""
        from django.utils import timezone
        if self.special_price and self.special_expiry:
            if self.special_expiry >= timezone.now().date():
                return self.special_price
        return self.product.price

    def __str__(self):
        return f"{self.product.name} at {self.branch.name}"


class Sale(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="sales")
    teller = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    receipt_number = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"Sale {self.receipt_number} - R{self.total_amount}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

class Special(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    special_price = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    active = models.BooleanField(default=True)


class StoreSession(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_ssid = models.CharField(max_length=255, null=True, blank=True)
    session_token = models.UUIDField(default=uuid.uuid4, editable=False)

    def expire_session(self):
        self.is_active = False
        self.save()

    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            self.expire_session()
            return True
        return False
    
class BranchSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class BranchQR(models.Model):
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)

class RewardsCard(models.Model):
    card_number = models.CharField(max_length=50, unique=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.card_number} - {self.branch.name}"


class RewardsPricing(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    reward_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.reward_price}"
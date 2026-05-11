from django.db import models
from django.conf import settings
import uuid
from django.utils import timezone
from core.models import Product as CoreProduct
import random


class CustomerProfile(models.Model):
    """
    Handles OTP and verification for mobile customers only.
    Linked to the main CustomUser via a One-to-One relationship.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='customer_profile'
    )
    
    # OTP Fields
    email_otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def generate_otp(self):
        """Generates a 6-digit code and sets expiry for 10 minutes."""
        otp = str(random.randint(100000, 999999))
        self.email_otp = otp
        self.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
        self.save()
        return otp

    def is_otp_valid(self, otp_input):
        """Checks if the OTP matches and hasn't expired."""
        if (self.email_otp == otp_input and 
            self.otp_expiry and 
            timezone.now() < self.otp_expiry):
            return True
        return False

    def __str__(self):
        return f"Profile for {self.user.username} (Verified: {self.is_verified})"

class Product(models.Model):
    name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField()
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_company_admin': True},
        null=True,
        blank=True,
        related_name="products_products"  # ✅ unique reverse accessor
    )
    created_at = models.DateTimeField(auto_now_add=True)



class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    company = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_orders',
        null=True,           # <-- FIXED
        blank=True           # <-- FIXED
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=64, blank=True, null=True)
    m_payment_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    exit_pass_code = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def get_item_count(self):
        receipt = Receipt.objects.filter(self.user).last()
        if receipt:
            return sum(item.qty for item in receipt.items.all()) 
        return 0

    def generate_exit_pass(self):
        self.exit_pass_code = str(uuid.uuid4())
        self.save()
        return self.exit_pass_code

class Receipt(models.Model):
    """
    A recorded receipt when a user buys items from a shop (company).
    Frontend expects shop grouping, items and returns.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="receipts")
    shop = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shop_receipts",
                             null=True, blank=True, help_text="Company (shop) who sold the items")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateTimeField(default=timezone.now)
    title = models.CharField(max_length=255, blank=True, null=True)  # optional label
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt #{self.id} - {self.shop or 'Unknown shop'} - {self.user}"

class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(CoreProduct, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.PositiveIntegerField(default=1)

    def line_total(self):
        return self.price * self.qty

    def __str__(self):
        return f"{self.name} x{self.qty} ({self.receipt.id})"

class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )

    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="returns")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    items = models.ManyToManyField(ReceiptItem, blank=True, related_name="return_requests")
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    # generated codes
    return_code = models.CharField(max_length=64, blank=True, null=True, unique=True)
    return_number = models.CharField(max_length=32, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # expiry window for the return (from -> to)
    expires_from = models.DateTimeField(blank=True, null=True)
    expires_to = models.DateTimeField(blank=True, null=True)
    qr_payload = models.JSONField(blank=True, null=True)

    def generate_codes(self):
        # generate a unique code and number; you can use uuid or custom formatting
        self.return_code = uuid.uuid4().hex.upper()
        # human-friendly number (e.g. YYMMDD + short uuid)
        self.return_number = timezone.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6].upper()

    def set_expiry_window(self, days=15):
        self.expires_from = timezone.now()
        self.expires_to = self.expires_from + timezone.timedelta(days=days)

    def mark_approved(self, days_valid=15, qr_payload=None):
        self.status = 'approved'
        self.generate_codes()
        self.set_expiry_window(days=days_valid)
        self.qr_payload = qr_payload or {"return_code": self.return_code, "return_number": self.return_number}
        self.save()

    def __str__(self):
        return f"ReturnRequest #{self.id} - {self.status}"

class Store(models.Model):
        name = models.CharField(max_length=255)
        geofence = models.JSONField()  # e.g., {"lat_min": ..., "lat_max": ..., "lng_min": ..., "lng_max": ...}
        bluetooth_beacons = models.JSONField(blank=True, null=True)  # list of beacon IDs
        products = models.ManyToManyField('Product', blank=True)
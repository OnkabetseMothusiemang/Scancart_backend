

from django.contrib.auth import get_user_model
from products.models import Receipt, ReceiptItem
from django.utils import timezone
import random

User = get_user_model()

def run():
    # ---------------------------
    # CREATE TEST CUSTOMER
    # ---------------------------
    customer, created = User.objects.get_or_create(
        username="testcustomer",
        defaults={"email": "customer@test.com"}
    )
    if created:
        customer.set_password("1234")
        customer.save()

    # ---------------------------
    # CREATE TEST SHOP (COMPANY ADMIN)
    # ---------------------------
    shop, created = User.objects.get_or_create(
        username="testshop",
        defaults={
            "email": "shop@test.com",
            "is_company_admin": True  # << THIS MATCHES YOUR MODEL
        }
    )
    if created:
        shop.set_password("1234")
        shop.save()

    # ---------------------------
    # CREATE RECEIPTS + ITEMS
    # ---------------------------
    for i in range(5):
        receipt = Receipt.objects.create(
            user=customer,
            shop=shop,
            title=f"Test Receipt {i+1}",
            total=random.randint(80, 400),
            date=timezone.now() - timezone.timedelta(days=random.randint(0, 10))
        )

        for _ in range(random.randint(3, 6)):
            price = random.randint(10, 80)
            qty = random.randint(1, 3)

            ReceiptItem.objects.create(
                receipt=receipt,
                name=random.choice(["Bread", "Milk", "Juice", "Eggs", "Meat", "Sweets"]),
                price=price,
                qty=qty
            )

    print("===============================")
    print("✓ TEST RECEIPTS CREATED SUCCESSFULLY")
    print("Login as customer: testcustomer / 1234")
    print("Login as shop: testshop / 1234")
    print("===============================")
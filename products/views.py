# ==================== IMPORTS ==================== #
import csv, io, uuid, urllib.parse, hashlib
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings
from .models import CustomerProfile
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail

from rest_framework import generics
from core.models import Product as CoreProduct, CustomUser, Special
from .serializers import ProductSerializer, OrderSerializer, RegisterSerializer


from core.models import Product as CoreProduct, CustomUser, RewardsCard, RewardsPricing
from .models import Order, Product
from .serializers import (
    ProductSerializer,
    ProductCreateSerializer,
    OrderSerializer,
    RegisterSerializer
)



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Prefetch

from .models import Receipt, ReceiptItem, ReturnRequest
from .serializers import ReceiptSerializer, ReturnRequestSerializer
from core.models import Product as CoreProduct
from django.utils import timezone
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone



from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterSerializer

from .models import Receipt, ReceiptItem, ReturnRequest
from .serializers import ReceiptSerializer, ReturnRequestSerializer
# ==================== PAYFAST ==================== #
def generate_payfast_url(data):
    """
    Generates a PayFast payment URL based on merchant data and cart info.
    """
    base_url = "https://www.payfast.co.za/eng/process"
    params = {
        'merchant_id': data['merchant_id'],
        'merchant_key': data['merchant_key'],
        'amount': f"{data['amount']:.2f}",
        'item_name': data['item_name'],
        'return_url': data['return_url'],
        'cancel_url': data['cancel_url'],
    }
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"

# ==================== REGISTER ==================== #

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    
    if serializer.is_valid():
        # This creates the user and handles password encryption 
        # (if your RegisterSerializer has the create method set up)
        user = serializer.save()
        
        # If your serializer doesn't automatically encrypt, do it here:
        if not user.password.startswith('pbkdf2_'):
            user.set_password(request.data.get('password'))
            user.save()

        return Response({
            "success": True, 
            "message": "Registration successful!"
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            "success": False, 
            "message": "Validation Error", 
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
# ==================== VERIFY OTP ==================== #

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_view(request):
    """
    Verifies the OTP and activates the user account.
    """
    email = request.data.get('email')
    otp_input = request.data.get('otp')

    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(email=email)
        profile = user.customer_profile
    except (User.DoesNotExist, AttributeError):
        return Response({"success": False, "message": "User or Profile not found"}, status=404)

    if profile.is_otp_valid(otp_input):
        profile.is_verified = True
        profile.save()
        
        user.is_active = True
        user.save()
        
        return Response({"success": True, "message": "Account verified successfully!"}, status=200)
    else:
        return Response({"success": False, "message": "Invalid or expired OTP"}, status=400)
# ==================== PROFILE ==================== #
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email
    })

# ==================== PRODUCTS ==================== #
class ProductListView(generics.ListAPIView):
    """
    List all products (read-only) for customers
    """
    queryset = CoreProduct.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                name__icontains=search
            ) | qs.filter(
                barcode__icontains=search
            ) | qs.filter(
                category__icontains=search
            )
        return qs

class ProductDetailView(generics.RetrieveAPIView):
    """
    Retrieve a product by its barcode.
    Handles accidental spaces and leading zeros.
    """
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    lookup_field = "barcode"

    def get_object(self):
        barcode = self.kwargs.get('barcode', '').strip()
        product = CoreProduct.objects.filter(barcode=barcode).first()
        if not product:
            normalized_barcode = barcode.lstrip('0')
            product = CoreProduct.objects.filter(barcode=normalized_barcode).first()
        if not product:
            raise get_object_or_404(CoreProduct, barcode=barcode)
        return product

# ==================== ORDERS ==================== #
class CreateOrderView(generics.CreateAPIView):
    """
    Create a new order
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# ==================== CSV UPLOAD ==================== #
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_csv_view(request):
    if not request.user.is_staff:
        return Response({"error": "Unauthorized"}, status=403)

    csv_file = request.FILES.get('file')
    if not csv_file or not csv_file.name.endswith('.csv'):
        return Response({'error': 'A CSV file is required'}, status=400)

    try:
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        company_admin = CustomUser.objects.filter(is_company_admin=True).first()
        if not company_admin:
            return Response({"error": "No company admin found"}, status=400)

        created_count, errors = 0, []

        for row in reader:
            try:
                barcode = row.get('barcode', '').strip()
                if CoreProduct.objects.filter(barcode=barcode).exists():
                    errors.append(f"Product with barcode {barcode} already exists")
                    continue

                CoreProduct.objects.create(
                    barcode=barcode,
                    name=row.get('name', '').strip(),
                    price=float(row.get('price', 0)),
                    stock=int(row.get('stock', 0)),
                    description=row.get('description', '').strip() if 'description' in row else '',
                    category=row.get('category', '').strip() if 'category' in row else '',
                    company=company_admin,
                    created_at=timezone.now()
                )
                created_count += 1
            except Exception as e:
                errors.append(f"Error processing row: {str(e)}")

        return Response({
            'message': f'Successfully created {created_count} products',
            'created': created_count,
            'errors': errors
        })

    except Exception as e:
        return Response({'error': f'Error processing CSV: {str(e)}'}, status=400)

# ==================== PAYFAST CHECKOUT ==================== #
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payfast_checkout(request):
    cart_items = request.data.get('cart_items', [])
    if not cart_items:
        return Response({"error": "Cart is empty"}, status=400)

    first_item = cart_items[0]
    product = CoreProduct.objects.get(id=first_item['id'])
    company = product.company

    amount = sum(float(item['price']) * item.get('qty', 1) for item in cart_items)

    payfast_data = {
        'merchant_id': company.payfast_merchant_id,
        'merchant_key': company.merchant_key,
        'amount': amount,
        'item_name': 'Cart Purchase',
        'return_url': f'https://yourapp.com/payfast-success/{company.id}',
        'cancel_url': f'https://yourapp.com/payfast-cancel/{company.id}',
    }

    payfast_url = generate_payfast_url(payfast_data)
    return Response({"payfast_url": payfast_url})

@api_view(['GET'])
def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)
    except Exception:
        return Response({"error": "Invalid link"}, status=400)

    if default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        return Response({"message": "Email verified successfully"}, status=200)
    else:
        return Response({"error": "Invalid token"}, status=400)


@api_view(['POST'])
def password_reset_request(request):
    email = request.data.get('email')
    user = CustomUser.objects.filter(email=email).first()
    if user:
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        link = f"http://<your-frontend-domain>/reset-password/{uid}/{token}/"

        send_mail(
            subject="Reset your password",
            message=f"Click here to reset your password: {link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

    # Always return success to prevent email enumeration
    return Response({"message": "If this email exists, a password reset link has been sent."})


#---payfast notifyer


# products/views.py (skeleton of notify)
@api_view(['POST'])
@permission_classes([AllowAny])
def payfast_notify(request):
    # This must be secured/validated. PayFast sends merchant_id etc.
    m_payment_id = request.data.get('m_payment_id')
    pf_payment_id = request.data.get('pf_payment_id')
    payment_status = request.data.get('payment_status')  # spec depends on PayFast
    # Find order and mark paid (this is app-specific)
    try:
        order = Order.objects.get(m_payment_id=m_payment_id)
        order.status = 'paid'
        order.m_payment_id = pf_payment_id or m_payment_id
        order.save()
        return Response({'ok': True})
    except Order.DoesNotExist:
        return Response({'ok': False, 'message': 'order not found'}, status=404)

# --- Verify barcode endpoint (checks product exists and stock) ---

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username') # or 'email'
    password = request.data.get('password')
    
    # Use the variable you actually defined
    user = authenticate(request, username=username, password=password)

    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user_id': user.id,
            'username': user.username
        })
    else:
        return Response({'error': 'Invalid credentials'}, status=401)

@api_view(['GET'])
def verify_barcode(request, barcode):
    barcode = (barcode or '').strip()

    store_id = request.query_params.get("store_id")
    if not store_id:
        return Response(
            {"ok": False, "message": "Store not detected"},
            status=400
        )

    # 🔥 THIS IS WHERE IT GOES
    product = CoreProduct.objects.filter(
        barcode=barcode,
        company_id=store_id
    ).first()

    if not product:
        return Response(
            {'ok': False, 'message': 'Product not found in this store'},
            status=404
        )

    if product.stock <= 0:
        return Response(
            {'ok': False, 'message': 'Out of stock'},
            status=400
        )

    serializer = ProductSerializer(product)
    return Response({'ok': True, 'product': serializer.data})

# --- Generate exit pass (after payment) ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_exit_pass(request):
    """
    POST { order_id: <id> } -> returns { exit_pass_code, qr_payload }
    """
    order_id = request.data.get('order_id')
    if not order_id:
        return Response({'ok': False, 'message': 'order_id required'}, status=400)
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status != 'paid':
        return Response({'ok': False, 'message': 'Order not paid'}, status=400)
    code = order.generate_exit_pass()
    # For QR payload you can include minimal JSON (order id + code) or a URL scanned by exit gate
    qr_payload = {'order_id': order.id, 'exit_pass': code}
    return Response({'ok': True, 'exit_pass_code': code, 'qr_payload': qr_payload})





# GET /api/receipts/shops/
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receipts_shops(request):
    """
    Return distinct shops (companies) the current user has receipts with.
    Response shape: [{shop_id, shop_name, last_visit}, ...]
    """
    user = request.user
    qs = Receipt.objects.filter(user=user).select_related('shop').order_by('-date')
    # collect unique shops in order of most recent
    seen = set()
    shops = []
    for r in qs:
        sid = r.shop.id if r.shop else None
        if sid and sid not in seen:
            shops.append({
                "shop_id": sid,
                "shop": r.shop.company_name or r.shop.username,
                "last_visit": r.date.isoformat()
            })
            seen.add(sid)
    return Response(shops)

# GET /api/receipts/shop/<shopId>/
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receipts_by_shop(request, shop_id):
    user = request.user
    receipts = Receipt.objects.filter(user=user, shop_id=shop_id).order_by('-date')
    serializer = ReceiptSerializer(receipts, many=True, context={'request': request})
    return Response(serializer.data)

# ... (receipts_shops and receipts_by_shop from earlier)

# GET /api/receipts/<receiptId>/
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def receipt_detail(request, receipt_id):
    user = request.user
    try:
        receipt = Receipt.objects.prefetch_related('items', 'returns').get(id=receipt_id, user=user)
    except Receipt.DoesNotExist:
        return Response({"detail": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)
    serializer = ReceiptSerializer(receipt, context={'request': request})
    # For returns, include serialized returns too (use ReturnRequestSerializer)
    returns_qs = receipt.returns.all().order_by('-created_at')
    returns_ser = ReturnRequestSerializer(returns_qs, many=True, context={'request': request})
    data = serializer.data
    data['returns'] = returns_ser.data
    return Response(data)


# POST /api/returns/request/
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def returns_request(request):
    """
    Expected payload:
    {
      "receipt_id": 123,
      "items": [receipt_item_id1, receipt_item_id2, ...],
      "reason": "Item damaged"
    }
    """
    user = request.user
    payload = request.data
    receipt_id = payload.get('receipt_id')
    items_ids = payload.get('items', [])
    reason = payload.get('reason', '')

    if not receipt_id:
        return Response({"detail": "receipt_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        receipt = Receipt.objects.get(id=receipt_id, user=user)
    except Receipt.DoesNotExist:
        return Response({"detail": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)

    # create return request
    rr = ReturnRequest.objects.create(receipt=receipt, requester=user, reason=reason)

    # attach items (if provided). Ensure they belong to this receipt.
    if items_ids:
        valid_items = ReceiptItem.objects.filter(id__in=items_ids, receipt=receipt)
        rr.items.set(valid_items)

    # Business rule: allow auto-approval if within allowed days
    # You said you wanted something like 10-15 days. We'll default to 15 days. 
    allowed_days = 15
    if (timezone.now() - receipt.date).days <= allowed_days:
        # approve immediately
        rr.mark_approved(days_valid=allowed_days, qr_payload={
            "return_code": None,  # mark_approved will set return_code
            "return_number": None
        })
        # mark_approved saved the instance and generated codes; update qr_payload properly
        # Re-write qr_payload to include actual codes
        rr.qr_payload = {"return_code": rr.return_code, "return_number": rr.return_number}
        rr.save()
    else:
        # leave as pending; admin/shop can later approve
        rr.status = 'pending'
        rr.save()

    ser = ReturnRequestSerializer(rr, context={'request': request})
    return Response(ser.data, status=status.HTTP_201_CREATED)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user

    if request.method == "GET":
        return Response({
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "date_joined": user.date_joined,
        })

    if request.method == "PATCH":
        if "email" in request.data:
            return Response(
                {"message": "Email change requires verification"},
                status=403
            )

        user.username   = request.data.get("username", user.username)
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name  = request.data.get("last_name", user.last_name)
        user.phone      = request.data.get("phone", user.phone)
        user.save()

    return Response({"message": "Updated successfully"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old = request.data.get("old_password")
    new = request.data.get("new_password")

    if not user.check_password(old):
        return Response({"message": "Old password incorrect"}, status=400)

    user.set_password(new)
    user.save()

    return Response({"message": "Password changed successfully"})

# ==================== VERIFY OTP ==================== #
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_view(request):
    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response(
            {"success": False, "message": "Email and OTP are required"},
            status=400
        )

    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=404
        )

    # Check OTP validity
    if user.otp_code != otp:
        return Response({"success": False, "message": "Invalid OTP"}, status=400)

    if user.otp_expiry and user.otp_expiry < timezone.now():
        return Response(
            {"success": False, "message": "OTP expired"},
            status=400
        )

    # Activate user after success
    user.is_active = True
    user.email_otp = None
    user.otp_expiry = None
    user.save()

    return Response(
        {"success": True, "message": "OTP verified successfully"},
        status=200
    )


from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



# ==================== RESEND OTP ==================== #
# core/views.py
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()

@api_view(['POST'])
def resend_otp_view(request):
    email = request.data.get('email')
    
    if not email:
        return Response({"success": False, "message": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"success": False, "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    # Generate new OTP
    otp = get_random_string(length=6, allowed_chars='0123456789')
    user.otp_code = otp  # Make sure your CustomUser model has a field like otp_code = models.CharField(max_length=6, blank=True)
    user.is_active = False  # temporarily set inactive until verified
    user.save()

    # Send email
    try:
        send_mail(
            subject='Your OTP Code',
            message=f'Your OTP code is: {otp}',
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
            fail_silently=False,
        )
        return Response({"success": True, "message": "OTP sent successfully"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"success": False, "message": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
def detect_store(request):
    lat = request.data.get('lat')
    lng = request.data.get('lng')
    barcode = request.data.get('barcode')
    beacon_id = request.data.get('beaconId')

    # 1️⃣ Check beacon first
    store = Store.objects.filter(bluetooth_beacons__contains=[beacon_id]).first()

    # 2️⃣ If no beacon match, check barcode
    if not store and barcode:
        product = CoreProduct.objects.filter(barcode=barcode).first()
        if product:
            store = product.company.store  # or a way to map product → store

    # 3️⃣ If still no match, check geofence
    if not store and lat and lng:
        for s in Store.objects.all():
            geo = s.geofence
            if geo['lat_min'] <= lat <= geo['lat_max'] and geo['lng_min'] <= lng <= geo['lng_max']:
                store = s
                break

    if store:
        return Response({'success': True, 'store': store.name})
    return Response({'success': False, 'store': None})

from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import BranchStock, Product, RewardsCard, RewardsPricing


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_cart(request):
    branch_id = request.data.get("branch_id")
    items = request.data.get("items", [])
    reward_card_number = request.data.get("reward_card_number")
    use_rewards = request.data.get("use_rewards", False)

    # ✅ Validate reward card if provided
    reward_card = None
    if use_rewards and reward_card_number:
        try:
            reward_card = RewardsCard.objects.get(
                card_number=reward_card_number,
                branch_id=branch_id,
                is_active=True
            )
        except RewardsCard.DoesNotExist:
            reward_card = None  # Invalid card → ignore rewards

    verified_items = []
    rejected_items = []
    total_amount = Decimal("0.00")

    for item in items:
        p_id = item.get("product_id")
        qty = int(item.get("quantity", 1))

        # ✅ Fetch stock record
        stock_record = BranchStock.objects.filter(
            branch_id=branch_id,
            product_id=p_id
        ).select_related('product').first()

        if not stock_record:
            rejected_items.append({
                "product_id": p_id,
                "reason": "This item is not sold in this branch."
            })
            continue

        if stock_record.quantity < qty:
            rejected_items.append({
                "product_id": p_id,
                "reason": f"Insufficient stock. Only {stock_record.quantity} left."
            })
            continue

        # ✅ Base price
        price = stock_record.current_price
        old_price = price

        # 🔥 Apply rewards pricing if card exists
        if reward_card:
            reward_price_record = RewardsPricing.objects.filter(
                product_id=p_id,
                branch_id=branch_id
            ).first()
            if reward_price_record:
                price = reward_price_record.reward_price

        line_total = price * qty
        total_amount += line_total

        verified_items.append({
            "product_id": stock_record.product.id,
            "name": stock_record.product.name,
            "price": str(price),
            "old_price": str(old_price) if old_price != price else None,
            "quantity": qty,
            "total": str(line_total)
        })

    return Response({
        "verified_items": verified_items,
        "rejected_items": rejected_items,
        "total_amount": str(total_amount)
    })


from django.utils.crypto import get_random_string

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def request_email_change(request):
    new_email = request.data.get("email")

    if not new_email:
        return Response({"message": "Email required"}, status=400)

    if CustomUser.objects.filter(email=new_email).exists():
        return Response({"message": "Email already in use"}, status=400)

    user = request.user
    otp = get_random_string(length=6, allowed_chars="0123456789")

    user.pending_email = new_email
    user.email_change_otp = otp
    user.email_change_expiry = timezone.now() + timezone.timedelta(minutes=10)
    user.save()

    send_mail(
        subject="Verify your new email",
        message=f"Your OTP code is: {otp}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[new_email],
    )

    return Response({"message": "OTP sent to new email"})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_email_change(request):
    otp = request.data.get("otp")

    user = request.user

    if not otp:
        return Response({"message": "OTP required"}, status=400)

    if user.email_change_otp != otp:
        return Response({"message": "Invalid OTP"}, status=400)

    if user.email_change_expiry < timezone.now():
        return Response({"message": "OTP expired"}, status=400)

    # ✅ Apply email change
    user.email = user.pending_email
    user.pending_email = None
    user.email_change_otp = None
    user.email_change_expiry = None
    user.save()

    return Response({"message": "Email updated successfully"})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_exit_pass(request):
    order_id = request.data.get('order_id')
    order = get_object_or_404(Order, id=order_id, user=request.user) 
    
    if order.status != 'paid': 
        return Response({'ok': False, 'message': 'Order not paid'}, status=400)
        
    code = order.generate_exit_pass()
    item_count = order.get_item_count() # Using the new method above
    
    # We bundle the items into the payload for the QR code
    qr_payload = {
        'order_id': order.id,
        'pass_code': code,
        'total_items': item_count # This is what the exit gate will scan
    }
    return Response({'ok': True, 'exit_pass_code': code, 'qr_payload': qr_payload}) 


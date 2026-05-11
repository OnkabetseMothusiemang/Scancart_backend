from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models import Product as CoreProduct
from .models import Order
from .models import Receipt, ReceiptItem, ReturnRequest


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['m_payment_id', 'created_at', 'exit_pass_code', 'status']

class ExitPassSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    exit_pass_code = serializers.CharField(read_only=True)


User = get_user_model()


# ------------------ USER SERIALIZERS ------------------ #
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'first_name', 'last_name']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')

        # ✅ explicitly hash password
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        
        user.save()
        return user


# ------------------ PRODUCT SERIALIZERS ------------------ #
class ProductSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.company_name', read_only=True)

    class Meta:
        model = CoreProduct
        fields = [
            'id', 'barcode', 'name', 'price', 'stock',
            'company_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoreProduct
        fields = ['barcode', 'name', 'price', 'stock', 'image', 'description', 'category']

    def validate_barcode(self, value):
        if CoreProduct.objects.filter(barcode=value).exists():
            raise serializers.ValidationError("Product with this barcode already exists")
        return value


# ------------------ ORDER SERIALIZERS ------------------ #
class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['m_payment_id', 'created_at']


class ReceiptItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True, default=None)
    class Meta:
        model = ReceiptItem
        fields = ['id', 'product_id', 'name', 'price', 'qty']

class ReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptItemSerializer(many=True, read_only=True)
    shop_name = serializers.CharField(source='shop.company_name', read_only=True)
    class Meta:
        model = Receipt
        fields = ['id', 'user', 'shop', 'shop_name', 'total', 'date', 'title', 'items']

class ReturnRequestSerializer(serializers.ModelSerializer):
    items = ReceiptItemSerializer(many=True, read_only=True)
    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'receipt', 'requester', 'items', 'reason', 'status',
            'return_code', 'return_number', 'expires_from', 'expires_to', 'qr_payload', 'created_at'
        ]
        read_only_fields = ['status', 'return_code', 'return_number', 'expires_from', 'expires_to', 'qr_payload', 'created_at']


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from rest_framework import serializers

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get("username")
        password = attrs.get("password")

        print("LOGIN ATTEMPT:", username_or_email, password)

        from django.contrib.auth import authenticate
        user = authenticate(username=username_or_email, password=password)


        print("AUTH RESULT:", user)

        if user is None:
            raise serializers.ValidationError({"error": "Invalid username/email or password"})

        data = super().validate(attrs)
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
        return data

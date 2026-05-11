from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # ==================== AUTH ==================== #
    path('auth/register/', views.register_view, name='register'),
    path('auth/login/', views.CustomLoginView.as_view(), name='login'),
    path('auth/verify-otp/', views.verify_otp_view, name='verify_otp'), # Unified here
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/resend-otp/', views.resend_otp_view, name='resend_otp'),

    # ==================== PROFILE ==================== #
    path('auth/profile/', views.user_profile_view, name='user_profile'),
    path('profile/', views.profile_view, name='profile_view'),
    path('change-password/', views.change_password, name='change_password'),
    
    # ==================== STORE & PRODUCTS ==================== #
    path('api/store/detect/', views.detect_store, name='detect_store'),
    path('products/<str:barcode>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('verify_barcode/<str:barcode>/', views.verify_barcode, name='verify-barcode'),
    path('verify_cart/', views.verify_cart, name='verify_cart'), # Added trailing slash

    # ==================== PAYFAST ==================== #
    path('payfast_notify/', views.payfast_notify, name='payfast_notify'),
    path('payfast_checkout/', views.payfast_checkout, name='payfast_checkout'),
    path('generate_exit_pass/', views.generate_exit_pass, name='generate_exit_pass'),

    # ==================== EMAIL VERIFICATION (Legacy/Link-based) ==================== #
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),

    # ==================== RECEIPTS ==================== #
    path('receipts/shops/', views.receipts_shops, name='receipts_shops'),
    path('receipts/shop/<int:shop_id>/', views.receipts_by_shop, name='receipts_by_shop'),
    path('receipts/<int:receipt_id>/', views.receipt_detail, name='receipt_detail'),
    path('verify-cart/', views.verify_cart, name='verify_cart'),
    # ==================== RETURNS ==================== #
    path('returns/request/', views.returns_request, name='returns_request'),

]
from django.urls import path
from . import views
from .views import CustomPasswordResetView

urlpatterns = [
    path('', views.auth_page, name='auth_page'),
    path('register/', views.register_business_admin, name='register_admin'),
    path('login/', views.auth_page, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # --- Management Paths ---
    path('dashboard/warehouses/', views.manage_warehouses, name='manage_warehouses'), # added this
    path('dashboard/branches/', views.branches_page, name='branches_page'),
    path('dashboard/products/', views.products_page, name='products_page'),
    path('dashboard/stats/', views.stats_page, name='stats_page'),
    path('dashboard/returns/', views.returns_page, name='returns_page'),
    
    # --- Auth & Account ---
    path('logout/', views.logout, name='logout'),
    
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),

    # --- Super Admin ---
    path('super-admin/dashboard/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('super-admin/shops/', views.super_admin_shops, name='super_admin_shops'),
    path('super-admin/shops/<int:shop_id>/approve/', views.super_admin_approve_shop, name='super_admin_approve_shop'),
    path('super-admin/shops/<int:shop_id>/suspend/', views.super_admin_suspend_shop, name='super_admin_suspend_shop'),
    path('super-admin/complaints/', views.super_admin_complaints, name='super_admin_complaints'),
    path('super-admin/complaints/<int:pk>/reply/', views.super_admin_reply_complaint, name='super_admin_reply_complaint'),
    path('super-admin/notifications/send/', views.super_admin_send_notification, name='super_admin_send_notification'),
    path('dashboard/staff/', views.manage_staff, name='manage_staff'),
    path('dashboard/warehouse/inventory/', views.warehouse_inventory, name='warehouse_inventory'),
    path('dashboard/warehouse/allocate/', views.allocate_stock, name='allocate_stock'),
    path('dashboard/branch/inventory/', views.branch_inventory, name='branch_inventory'),
    path('dashboard/branch/manage_tellers/', views.manage_tellers, name='manage_tellers'),
    path('dashboard/branch/branch_specials/', views.branch_specials, name='branch_specials'),
    path('dashboard/branch/pos_terminal/', views.pos_terminal, name='pos_terminal'),
    path('dashboard/branch/verify_return/', views.verify_return, name='verify_return'),
    path('dashboard/branch/stats_page/', views.stats_page, name='stats_page'),
    path('dashboard/staff/delete/<int:user_id>/', views.delete_staff, name='delete_staff'),
    path('dashboard/branch/delete/<int:branch_id>/', views.delete_branch, name='delete_branch'),
    path('dashboard/warehouse/delete/<int:warehouse_id>/', views.delete_warehouse, name='delete_warehouse'),
    path('dashboard/branch/teller/delete/<int:teller_id>/', views.delete_teller, name='delete_teller'),
    path("branch/qr/", views.branch_qr_page, name="branch_qr_page"),
    path("branch/qr/image/", views.generate_branch_qr, name="generate_branch_qr"),
    path('branch/guards/', views.manage_guards, name='manage_guards'),
    path('branch/guards/delete/<int:guard_id>/', 
     views.delete_guard, 
     name='delete_guard'),
    path("guard/login/", views.guard_login, name="guard_login"),
    path("guard/guard_dashboard/", views.guard_dashboard, name="guard_dashboard"),
    # --- API ---
    path('api/returns/verify/', views.api_verify_return_code, name='api_verify_return_code'),
    path('api/returns/verify/', views.api_verify_return_code, name='api_verify_return_code'),
    path('api/guard/login/', views.guard_login, name='guard-login'),
]


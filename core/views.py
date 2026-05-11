from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout as auth_logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.views import PasswordResetView
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from products.models import ReturnRequest
# Look for your existing imports and ensure Warehouse is included:
from .models import CustomUser, Product, ShopApplication, Complaint, Notification, Branch, Warehouse, WarehouseStock, BranchStock, Sale, SaleItem
import csv, io, json
from django.db.models import Q
import pandas as pd
import ssl
from .forms import CompanyRegisterForm


# Disable SSL verification for development (temporary fix for email)

User = get_user_model()


# ===================================================================
# HELPERS
# ===================================================================
def is_super_business_user(user):
    return user.is_superuser or getattr(user, "is_super_company", False)


# ===================================================================
# EMAIL VERIFICATION
# ===================================================================



# ===================================================================
# SHOP REGISTRATION → PENDING APPROVAL
# ===================================================================
def register_shop(request):
    if request.method == "POST":
        owner = request.POST.get("owner_name")
        shop = request.POST.get("shop_name")
        email = request.POST.get("email")
        username = request.POST.get("username")

        if ShopApplication.objects.filter(email=email).exists():
            messages.error(request, "Email already used.")
            return redirect("auth_page")

        if ShopApplication.objects.filter(username=username).exists():
            messages.error(request, "Username already used.")
            return redirect("auth_page")

        ShopApplication.objects.create(
            owner_name=owner,
            shop_name=shop,
            email=email,
            username=username
        )

        messages.success(request, "Your application was sent. Waiting for approval.")
        return redirect("auth_page")

    return redirect("auth_page")


# ===================================================================
# BUSINESS ADMIN REGISTRATION
# ===================================================================
def register_business_admin(request):
    if request.method == "POST":
        business_name = request.POST.get("business_name")
        town = request.POST.get("town")
        province = request.POST.get("province")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("auth_page")

        # Create user first
        user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        is_company_admin=True, # Ensure this is True [cite: 2]
        role='company',        # Explicitly set the role 
        company_name=business_name,
        full_name=business_name,
        is_active=True
        )
        # Create shop application
        ShopApplication.objects.create(
            user=user,
            business_name=business_name,
            town=town,
            province=province,
            is_approved=False,
        )

        messages.success(request, "Registration successful! Wait for approval.")
        return redirect("auth_page")

    return render(request, "core/register_admin.html")
# ===================================================================
# AUTH PAGE (LOGIN + REGISTER)
# ===================================================================
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, get_user_model
from django.contrib import messages
from .forms import CompanyRegisterForm

User = get_user_model()

# ===================================================================
# AUTH PAGE (LOGIN + REGISTER)
# ===================================================================
# ===================================================================
# AUTH PAGE (LOGIN + REGISTER)
# ===================================================================
def auth_page(request):
    # Redirect authenticated users based on role
    if request.user.is_authenticated:
        redirect_map = {
            "company": "dashboard",
            "branch": "branch_inventory",
            "warehouse": "warehouse_inventory",
            "teller": "pos_terminal",
            "guard": "guard_dashboard"
        }
        return redirect(redirect_map.get(request.user.role, "auth_page"))

    form = CompanyRegisterForm()

    if request.method == "POST":
        action = request.GET.get("action")

        # ---------------- LOGIN ----------------
        if action == "login":
            email = request.POST.get("email")
            password = request.POST.get("password")
            user = authenticate(request, username=email, password=password)

            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                redirect_map = {
                    "company": "dashboard",
                    "branch": "branch_inventory",
                    "warehouse": "warehouse_inventory",
                    "teller": "pos_terminal",
                    "guard": "guard_dashboard"
                }
                return redirect(redirect_map.get(user.role, "auth_page"))
            else:
                messages.error(request, "Invalid email or password.")
                return render(request, "core/register_admin.html", {"form": form})

        # ---------------- REGISTER ----------------
        elif action == "register":
            form = CompanyRegisterForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                user.username = form.cleaned_data.get('email')
                user.is_active = True
                user.save()

                # Create shop application
                ShopApplication.objects.create(
                    user=user,
                    business_name=user.company_name,
                    is_approved=True  # or False if using approval flow
                )

                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                redirect_map = {
                    "company": "dashboard",
                    "branch": "branch_inventory",
                    "warehouse": "warehouse_inventory",
                    "teller": "pos_terminal",
                    "guard": "guard_dashboard"
                }
                return redirect(redirect_map.get(user.role, "auth_page"))
            else:
                return render(request, "core/register_admin.html", {"form": form})

    # ---------------- GET / fallback ----------------
    return render(request, "core/register_admin.html", {"form": form})

# ---------------- LOGOUT ----------------
from django.contrib.auth import logout as auth_logout

def logout(request):
    """
    Logs out any authenticated user and redirects to the auth page.
    """
    auth_logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("auth_page")

# DASHBOARD
# ===================================================================
@login_required(login_url='auth_page')
def dashboard(request):
    user = request.user
    branches = Branch.objects.filter(company=user)
    # ADD THIS: Pull warehouses for the dashboard
    warehouses = Warehouse.objects.filter(company=user) 
    recent_products = Product.objects.filter(company=user).order_by("-created_at")

    context = {
        "branches": branches,
        "warehouses": warehouses, # Add this to the context
        "recent_products": recent_products,
        "active": "dashboard",
    }
    return render(request, "core/dashboard.html", context)
# PRODUCTS PAGE
# ===================================================================
@login_required(login_url='/login/')
def products_page(request):
    user = request.user

    shop = ShopApplication.objects.filter(user=user).first()
    if not shop:
        messages.error(request, "Shop profile missing. Contact support.")
        return redirect("dashboard")

    if shop.is_suspended:
        messages.error(request, "Your shop has been suspended. Contact support.")
        auth_logout(request)
        return redirect("auth_page")


    # SAVE MERCHANT DETAILS
    if request.method == "POST" and "save_merchant_details" in request.POST:
        merchant_id = request.POST.get("payfast_merchant_id")
        merchant_key = request.POST.get("merchant_key")

        if merchant_id and merchant_key:
            user.payfast_merchant_id = merchant_id
            user.merchant_key = merchant_key
            user.save()
            messages.success(request, "PayFast details saved!")
        else:
            messages.error(request, "Both merchant fields are required.")
        return redirect("products_page")

    # ADD PRODUCT MANUALLY
    if request.method == "POST" and "add_product" in request.POST:
        name = request.POST.get("name")
        barcode = request.POST.get("barcode")
        unit = request.POST.get("unit", "pcs")
        description = request.POST.get("description", "")

        try:
            price = float(request.POST.get("price") or 0)
        except ValueError:
            price = 0

        try:
            stock = int(request.POST.get("stock") or 0)
        except ValueError:
            stock = 0

        Product.objects.create(
            company=user,
            name=name,
            barcode=barcode,
            price=price,
            stock=stock,
            unit=unit,
            description=description
        )

        messages.success(request, "Product added successfully!")
        return redirect("products_page")

    # FILE UPLOAD (CSV / EXCEL)
    if request.method == "POST" and "upload_products_file" in request.POST:
        upload_file = request.FILES.get("upload_file")

        if not upload_file:
            messages.error(request, "Please upload a file.")
            return redirect("products_page")

        try:
            if upload_file.name.endswith(".csv"):
                df = pd.read_csv(upload_file)
            elif upload_file.name.endswith((".xlsx", ".xls")):
                df = pd.read_excel(upload_file)
            else:
                messages.error(request, "Unsupported file format.")
                return redirect("products_page")

            required_columns = {"name", "barcode", "price", "stock", "unit"}
            if not required_columns.issubset(df.columns):
                messages.error(request, "File must contain columns: name, barcode, price, stock, unit")
                return redirect("products_page")

            created_count = 0

            for _, row in df.iterrows():
                barcode = str(row["barcode"]).strip()

                if not barcode or pd.isna(barcode):
                    continue

                if Product.objects.filter(barcode=barcode, company=user).exists():
                    continue

                Product.objects.create(
                    company=user,
                    name=str(row["name"]).strip(),
                    barcode=barcode,
                    price=row.get("price", 0),
                    stock=row.get("stock", 0),
                    unit=str(row.get("unit", "pcs")).strip(),
                )
                created_count += 1

            messages.success(request, f"{created_count} products uploaded successfully!")

        except Exception as e:
            messages.error(request, f"Upload failed: {e}")

        return redirect("products_page")

    # DELETE PRODUCT
    if request.method == "POST" and "delete_product_id" in request.POST:
        pid = request.POST.get("delete_product_id")
        Product.objects.filter(id=pid, company=user).delete()
        messages.success(request, "Product deleted!")
        return redirect("products_page")

    # PAGE DISPLAY
    products = Product.objects.filter(company=user)

    return render(request, "core/products_upload.html", {
        "products": products,
        "active": "products",
        "shop": shop
    })


# ===================================================================
# STATS PAGE
# ===================================================================
@login_required(login_url='/login/')
def stats_page(request):
    if not getattr(request.user, "is_company_admin", False):
        messages.error(request, "Not authorized.")
        return redirect("dashboard")
    return render(request, "core/stats.html", {"active": "stats"})


# ===================================================================
# RETURNS PAGE
# ===================================================================
@login_required(login_url='/login/')
def returns_page(request):
    if not getattr(request.user, "is_company_admin", False):
        messages.error(request, "Not authorized.")
        return redirect("dashboard")
    return render(request, "core/returns.html", {"active": "returns"})


# ===================================================================
# SUPER ADMIN VIEWS
# ===================================================================
@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_dashboard(request):
    shops_count = User.objects.filter(is_company_admin=True).count()
    pending_shops = ShopApplication.objects.filter(is_approved=False).count()
    customers_count = User.objects.filter(is_company_admin=False, is_superuser=False).count()
    total_returns = ReturnRequest.objects.count()

    context = {
        "active": "dashboard",
        "shops_count": shops_count,
        "pending_shops": pending_shops,
        "customers_count": customers_count,
        "total_returns": total_returns,
    }
    return render(request, "core/dashboard.html", context)


@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_shops(request):
    shops = User.objects.filter(is_company_admin=True)
    applications = ShopApplication.objects.filter(is_approved=False)
    return render(request, "core/super_shops.html", {
        "shops": shops,
        "applications": applications,
        "active": "shops"
    })


@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_approve_shop(request, shop_id):
    app = get_object_or_404(ShopApplication, id=shop_id)

    if app.is_approved:
        messages.warning(request, "Shop already approved.")
        return redirect("super_admin_shops")

    app.is_approved = True
    app.save()

    user = app.user
    user.is_company_admin = True
    user.is_staff = True
    user.is_verified = True
    user.is_active = True
    user.save()

    messages.success(request, f"{user.company_name or user.username} approved successfully.")
    return redirect("super_admin_shops")


@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_suspend_shop(request, shop_id):
    shop_user = get_object_or_404(User, id=shop_id, is_company_admin=True)
    shop_user.is_company_admin = False
    shop_user.is_active = False
    shop_user.save()
    messages.success(request, "Shop suspended/disabled.")
    return redirect("super_admin_shops")


@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_complaints(request):
    qs = Complaint.objects.order_by("-created_at")
    return render(request, "core/super_complaints.html", {"complaints": qs, "active": "complaints"})


@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_reply_complaint(request, pk):
    c = get_object_or_404(Complaint, pk=pk)
    if request.method == "POST":
        note = request.POST.get("response")
        c.admin_response = note
        c.responded_by = request.user
        c.status = "in_review"
        c.save()

        Notification.objects.create(
            sender=request.user,
            target_user=c.from_user,
            target_type="customer" if c.source == "customer" else "shop",
            title=f"Response to your complaint {c.uuid}",
            message=note,
            metadata={"complaint_id": str(c.uuid)}
        )
        messages.success(request, "Response sent.")
        return redirect("super_admin_complaints")
    return render(request, "core/super_reply_complaint.html", {"complaint": c})


# ===================================================================
# SUPER ADMIN NOTIFICATIONS
# ===================================================================
@login_required(login_url='/login/')
@user_passes_test(is_super_business_user, login_url='/login/')
def super_admin_send_notification(request):
    if request.method == "POST":
        target_type = request.POST.get("target_type", "all")
        title = request.POST.get("title")
        message_text = request.POST.get("message")
        province = request.POST.get("province")

        if target_type == "all":
            Notification.objects.create(sender=request.user, target_type="all", title=title, message=message_text)
            messages.success(request, "Notification created for all users.")
        elif target_type == "shop":
            shops = User.objects.filter(is_company_admin=True)
            if province:
                shops = shops.filter(company_name__icontains=province)
            for s in shops:
                Notification.objects.create(sender=request.user, target_type="shop", target_user=s, title=title, message=message_text)
            messages.success(request, "Notifications queued for shops.")
        elif target_type == "customer":
            customers = User.objects.filter(is_company_admin=False, is_superuser=False)
            for c in customers:
                Notification.objects.create(sender=request.user, target_type="customer", target_user=c, title=title, message=message_text)
            messages.success(request, "Notifications queued for customers.")
        return redirect("super_admin_dashboard")

    return render(request, "core/super_send_notification.html", {"active": "notifications"})


# ===================================================================
# PASSWORD RESET
# ===================================================================
class CustomPasswordResetView(PasswordResetView):
    template_name = "core/password_reset_form.html"

    def form_valid(self, form):
        messages.success(self.request, "✅ If an account with that email exists, a reset link has been sent!")
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


# ===================================================================
# API: VERIFY RETURN CODE FOR SHOP SCANNER
# ===================================================================
@csrf_exempt
@login_required(login_url='/login/')
def api_verify_return_code(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode())
        code = body.get("return_code") or body.get("return_number")
    except Exception:
        return JsonResponse({"error": "invalid payload"}, status=400)

    if not code:
        return JsonResponse({"error": "return_code required"}, status=400)

    try:
        rr = ReturnRequest.objects.get(return_code=code)
    except ReturnRequest.DoesNotExist:
        try:
            rr = ReturnRequest.objects.get(return_number=code)
        except ReturnRequest.DoesNotExist:
            return JsonResponse({"valid": False, "reason": "Not found"}, status=404)

    now = timezone.now()
    if getattr(rr, "expires_from", None) and getattr(rr, "expires_to", None):
        if not (rr.expires_from <= now <= rr.expires_to):
            return JsonResponse({"valid": False, "reason": "Expired", "expires_from": rr.expires_from, "expires_to": rr.expires_to})

    if rr.status != "approved":
        return JsonResponse({"valid": False, "reason": f"Not approved ({rr.status})"})

    data = {
        "valid": True,
        "return_number": rr.return_number,
        "return_code": rr.return_code,
        "items": [{"id": i.id, "name": i.name, "qty": i.qty} for i in rr.items.all()],
        "requester": {"id": rr.requester.id, "username": rr.requester.username},
        "expires_from": rr.expires_from,
        "expires_to": rr.expires_to,
    }
    return JsonResponse(data)

@login_required(login_url='auth_page')
def branches_page(request):
    user = request.user
    
    if request.method == "POST":
        name = request.POST.get("name")
        province = request.POST.get("province")
        town = request.POST.get("town")
        
        Branch.objects.create(
            company=user,
            name=name,
            province=province,
            town=town
        )
        messages.success(request, f"Branch '{name}' added successfully!")
        return redirect("branches_page")

    branches = Branch.objects.filter(company=user).order_by("-created_at")
    return render(request, "core/branches.html", {
        "branches": branches,
        "active": "branches"
    })

@login_required
def manage_warehouses(request):
    if request.user.role != 'company':
        messages.error(request, "Access denied. Head Office only.")
        return redirect('dashboard')

    if request.method == "POST":
        name = request.POST.get("name")
        location = request.POST.get("location")
        
        Warehouse.objects.create(
            company=request.user,
            name=name,
            location=location
        )
        messages.success(request, f"Warehouse '{name}' created successfully.")
        return redirect('manage_warehouses')

    warehouses = Warehouse.objects.filter(company=request.user)
    return render(request, "core/warehouse.html", {"warehouses": warehouses})

@login_required
def manage_staff(request):
    if request.user.role != 'company':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if request.method == "POST":
        role = request.POST.get("role")
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        # Ensure these IDs are captured from the hidden selects
        warehouse_id = request.POST.get("warehouse_id")
        branch_id = request.POST.get("branch_id")

        if User.objects.filter(email=email).exists():
            messages.error(request, "A user with this email already exists.")
        else:
            new_staff = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                is_active=True,
                is_verified=True
            )

            # LINKING: This is what makes them visible to the company
            if role == 'warehouse' and warehouse_id:
                new_staff.assigned_warehouse = get_object_or_404(Warehouse, id=warehouse_id, company=request.user)
            elif role == 'branch' and branch_id:
                new_staff.assigned_branch = get_object_or_404(Branch, id=branch_id, company=request.user)
            
            new_staff.save()
            messages.success(request, f"Successfully created {role}: {full_name}")
            return redirect('manage_staff')

    # Data for lists
    warehouses = Warehouse.objects.filter(company=request.user)
    branches = Branch.objects.filter(company=request.user)
    
    # Filter staff so only YOUR company staff show up
    all_staff = User.objects.filter(
        Q(assigned_branch__company=request.user) | 
        Q(assigned_warehouse__company=request.user)
    ).distinct().order_by('-date_joined')

    return render(request, "core/manage_staff.html", {
        "warehouses": warehouses,
        "branches": branches,
        "all_staff": all_staff,
        "active": "staff"
    })

@login_required
def delete_staff(request, user_id):
    # Security check: Ensure the staff belongs to THIS company before deleting
    staff = get_object_or_404(User, id=user_id)
    
    # Check if they are actually staff of this company
    is_warehouse_staff = staff.assigned_warehouse and staff.assigned_warehouse.company == request.user
    is_branch_staff = staff.assigned_branch and staff.assigned_branch.company == request.user

    if is_warehouse_staff or is_branch_staff:
        staff.delete()
        messages.success(request, "Staff member deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this user.")
        
    return redirect('manage_staff')

@login_required
def delete_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id, company=request.user)
    branch.delete()
    messages.success(request, "Branch deleted.")
    return redirect('branches_page')

@login_required
def delete_warehouse(request, warehouse_id):
    warehouse = get_object_or_404(Warehouse, id=warehouse_id, company=request.user)
    warehouse.delete()
    messages.success(request, "Warehouse deleted.")
    return redirect('manage_warehouses')

@login_required
def warehouse_inventory(request):

    # Security check
    if request.user.role not in ['warehouse', 'company']:
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    # Determine warehouse
    if request.user.role == 'warehouse':
        warehouse = request.user.assigned_warehouse
    else:
        warehouse = Warehouse.objects.filter(company=request.user).first()

    if not warehouse:
        messages.warning(request, "No warehouse found. Please create or assign one first.")
        return redirect('manage_warehouses')

    # ---------------- RECEIVE STOCK ----------------
    if request.method == "POST":

        product_ids = request.POST.getlist("product_ids")

        if not product_ids:
            messages.error(request, "Please select at least one product.")
            return redirect("warehouse_inventory")

        for pid in product_ids:
            qty_value = request.POST.get(f"quantity_{pid}")

            try:
                quantity = int(qty_value)

                if quantity <= 0:
                    continue

                stock, created = WarehouseStock.objects.get_or_create(
                    warehouse=warehouse,
                    product_id=pid
                )

                stock.quantity += quantity
                stock.save()

            except (ValueError, TypeError):
                messages.error(request, "Invalid quantity entered.")
                return redirect("warehouse_inventory")

        messages.success(request, "Stock received successfully!")
        return redirect("warehouse_inventory")

    # ---------------- DISPLAY INVENTORY ----------------
    inventory = WarehouseStock.objects.filter(
        warehouse=warehouse
    ).select_related("product")

    # Only show this company's products
    master_products = Product.objects.filter(company=warehouse.company)

    return render(request, "core/warehouse_inventory.html", {
        "inventory": inventory,
        "master_products": master_products,
        "active": "inventory",
        "current_warehouse": warehouse
    })

@login_required
def allocate_stock(request):
    # ---------------- SECURITY ----------------
    if request.user.role not in ['warehouse', 'company']:
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    if request.user.role == 'warehouse':
        warehouse = request.user.assigned_warehouse
    else:
        warehouse = Warehouse.objects.filter(company=request.user).first()

    if not warehouse:
        messages.error(request, "No warehouse found to allocate from.")
        return redirect('manage_warehouses')

    company_owner = warehouse.company

    # ---------------- PROCESS TRANSFER ----------------
    if request.method == "POST":
        product_ids = request.POST.getlist("product_ids")
        branch_id = request.POST.get("branch_id")

        if not product_ids:
            messages.error(request, "Please select at least one product.")
            return redirect("allocate_stock")

        try:
            branch = get_object_or_404(Branch, id=branch_id, company=company_owner)
        except:
            messages.error(request, "Invalid branch selected.")
            return redirect("allocate_stock")

        # Loop through selected products
        for pid in product_ids:
            qty_value = request.POST.get(f"quantity_{pid}")
            try:
                quantity = int(qty_value)
                if quantity <= 0:
                    continue

                # Check warehouse stock
                wh_stock = get_object_or_404(WarehouseStock, warehouse=warehouse, product_id=pid)

                if wh_stock.quantity < quantity:
                    messages.warning(request, f"Not enough stock for {wh_stock.product.name}. Only {wh_stock.quantity} available.")
                    continue

                # Deduct from warehouse
                wh_stock.quantity -= quantity
                wh_stock.save()

                # Add to branch
                br_stock, created = BranchStock.objects.get_or_create(branch=branch, product_id=pid)
                br_stock.quantity += quantity
                br_stock.save()

            except (ValueError, TypeError):
                messages.error(request, "Invalid quantity entered.")
                return redirect("allocate_stock")

        messages.success(request, "Stock successfully allocated!")
        return redirect("allocate_stock")

    # ---------------- DISPLAY DATA ----------------
    inventory = WarehouseStock.objects.filter(warehouse=warehouse, quantity__gt=0)
    branches = Branch.objects.filter(company=company_owner)

    return render(request, "core/allocate_stock.html", {
        "inventory": inventory,
        "branches": branches,
        "active": "allocate",
        "warehouse": warehouse
    })


@login_required
def branch_inventory(request):
    # Ensure only Branch Managers or Head Office can see this
    if request.user.role not in ['branch', 'company']:
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    # Get the branch assigned to this manager
    branch = request.user.assigned_branch
    
    # Get all stock records for this specific branch
    inventory = BranchStock.objects.filter(branch=branch).select_related('product')

    return render(request, "core/branch_inventory.html", {
        "inventory": inventory,
        "branch": branch,
        "active": "inventory"
    })

@login_required
def manage_tellers(request):
    # Security: Only Branch Managers should manage tellers for their branch
    if request.user.role != 'branch':
        messages.error(request, "Access denied. Only Branch Managers can manage tellers.")
        return redirect('dashboard')

    branch = request.user.assigned_branch
    
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # FIX: Check if username/email already exists to prevent the IntegrityError
        if User.objects.filter(username=email).exists():
            messages.error(request, f"Error: A user with the email {email} already exists.")
        else:
            try:
                # Create the teller user
                new_teller = User.objects.create_user(
                    username=email, # Django uses username for uniqueness
                    email=email,
                    password=password,
                    full_name=full_name,
                    role='teller',
                    assigned_branch=branch,
                    is_active=True,
                    is_verified=True
                )
                messages.success(request, f"Teller {full_name} created successfully for {branch.name}.")
                return redirect('manage_tellers')
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")

    # Fetch only tellers assigned to THIS manager's branch
    tellers = User.objects.filter(role='teller', assigned_branch=branch).order_by('-date_joined')
    
    return render(request, "core/manage_tellers.html", {
        "tellers": tellers,
        "branch": branch,
        "active": "tellers"
    })

@login_required
def delete_teller(request, teller_id):
    # Only the branch manager of the specific branch can delete their tellers
    teller = get_object_or_404(User, id=teller_id, role='teller')
    
    if teller.assigned_branch == request.user.assigned_branch:
        teller.delete()
        messages.success(request, "Teller deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this teller.")
        
    return redirect('manage_tellers')

@login_required
def branch_specials(request):
    if request.user.role != 'branch':
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    branch = request.user.assigned_branch

    if request.method == "POST":
        stock_ids = request.POST.getlist("stock_ids")  # List of selected stock item IDs

        for stock_id in stock_ids:
            stock_item = get_object_or_404(BranchStock, id=stock_id, branch=branch)
            special_price = request.POST.get(f"special_price_{stock_id}")
            expiry_date = request.POST.get(f"expiry_date_{stock_id}")

            if special_price:
                stock_item.special_price = special_price
            if expiry_date:
                stock_item.special_expiry = expiry_date

            stock_item.save()

        messages.success(request, "Selected specials updated successfully!")
        return redirect('branch_specials')

    inventory = BranchStock.objects.filter(branch=branch)
    return render(request, "core/branch_specials.html", {
        "inventory": inventory,
        "active": "specials"
    })


@login_required
def pos_terminal(request):
    if request.user.role != 'teller':
        messages.error(request, "Access denied to POS.")
        return redirect('dashboard')

    branch = request.user.assigned_branch

    if request.method == "POST":
        cart_data = json.loads(request.POST.get('cart_data'))
        
        if not cart_data:
            return JsonResponse({"success": False, "error": "Cart is empty"})

        # Create the Sale record
        new_sale = Sale.objects.create(branch=branch, teller=request.user)
        total = 0

        for item in cart_data:
            # item format: {'barcode': '123', 'qty': 2}
            stock = get_object_or_404(BranchStock, branch=branch, product__barcode=item['barcode'])
            
            if stock.quantity < int(item['qty']):
                return JsonResponse({"success": False, "error": f"Shortage of {stock.product.name}"})

            # Use the current_price property (which handles specials!)
            price = stock.current_price
            line_total = price * int(item['qty'])
            total += line_total

            # Create SaleItem
            SaleItem.objects.create(
                sale=new_sale,
                product=stock.product,
                quantity=item['qty'],
                price_at_sale=price
            )

            # Deduct from Branch Stock
            stock.quantity -= int(item['qty'])
            stock.save()

        new_sale.total_amount = total
        new_sale.save()

        return JsonResponse({"success": True, "receipt": new_sale.receipt_number})

    return render(request, "core/pos_terminal.html", {"active": "pos"})


from django.db.models import Sum

@login_required
def stats_page(request):
    if request.user.role != 'company':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    # 2. This is the "Sum" logic
    # It looks at every Sale tied to this company and adds up the 'total_amount'
    stats = Sale.objects.filter(branch__company=request.user).aggregate(
        overall_total=Sum('total_amount')
    )
    
    total_revenue = stats['overall_total'] or 0

    # 3. Getting Branch-specific sums
    branch_performance = []
    branches = Branch.objects.filter(company=request.user)
    for branch in branches:
        branch_total = Sale.objects.filter(branch=branch).aggregate(
            res=Sum('total_amount')
        )['res'] or 0
        
        branch_performance.append({
            'name': branch.name,
            'revenue': branch_total,
            'sales_count': Sale.objects.filter(branch=branch).count()
        })

    return render(request, "core/stats_page.html", {
        "total_revenue": total_revenue,
        "branch_performance": branch_performance,
        "active": "stats"
    })

@login_required
def verify_return(request):
    if request.user.role != 'teller':
        return redirect('dashboard')

    result = None
    if request.method == "POST":
        code = request.POST.get("return_code")
        # Look for the return request in the database
        result = ReturnRequest.objects.filter(return_code=code).first()
        
        if not result:
            messages.error(request, "Invalid Return Code.")

    return render(request, "core/verify_return.html", {
        "result": result,
        "active": "verify"
    })

#branches QR 


import qrcode
from io import BytesIO
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from PIL import Image  # Needed if you’re using reportlab with PIL

@login_required
def generate_branch_qr(request):
    if request.user.role != 'branch':
        return JsonResponse({"error": "Only branch managers"}, status=403)

    branch = request.user.assigned_branch

    # ------------------ Generate QR ------------------
    qr_payload = {
        "branch_id": branch.id,
        "type": "STORE_SESSION"
    }
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(json.dumps(qr_payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # ------------------ Save QR to BytesIO ------------------
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')  # <-- Specify format explicitly
    img_buffer.seek(0)

    # ------------------ Create PDF ------------------
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter

    # Draw the QR image
    pil_img = Image.open(img_buffer)  # PIL Image from buffer
    c.drawInlineImage(pil_img, inch, height - 3*inch, width=2*inch, height=2*inch)

    # Optional: add branch name text
    c.setFont("Helvetica", 14)
    c.drawString(inch, height - 3.5*inch, f"Branch: {branch.name}")

    c.showPage()
    c.save()

    pdf_buffer.seek(0)
    return HttpResponse(pdf_buffer, content_type='application/pdf')


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Branch, StoreSession

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_verify_branch_qr(request):
    """
    Verifies that the user has scanned a valid branch QR and retrieves the active session branch.
    Returns branch info and allows verified cart operations.
    """
    # 1️⃣ Get active store session instead of using assigned_branch
    try:
        session = StoreSession.objects.get(user=request.user, is_active=True)
        if session.is_expired():
            return JsonResponse({"success": False, "error": "Session expired. Scan QR again."})
        branch = session.branch
    except StoreSession.DoesNotExist:
        return JsonResponse({"success": False, "error": "No active session. Scan branch QR first."})

    # 2️⃣ Example: Return branch info
    branch_data = {
        "id": branch.id,
        "name": branch.name,
        "province": branch.province,
        "town": branch.town
    }

    return JsonResponse({"success": True, "branch": branch_data})



  

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_store_session(request):
    branch_id = request.data.get("branch_id")

    if not branch_id:
        return JsonResponse({"error": "Branch ID required"}, status=400)

    branch = Branch.objects.filter(id=branch_id).first()

    if not branch:
        return JsonResponse({"error": "Invalid branch"}, status=404)

    # Deactivate old sessions
    StoreSession.objects.filter(user=request.user, is_active=True).update(is_active=False)

    expires = timezone.now() + timedelta(minutes=30)

    session = StoreSession.objects.create(
        user=request.user,
        branch=branch,
        expires_at=expires
    )

    return JsonResponse({
        "success": True,
        "session_token": str(session.session_token),
        "branch_name": branch.name,
        "expires_at": session.expires_at
    })

import base64

@login_required
def branch_qr_page(request):
    if request.user.role != "branch":
        return redirect("dashboard")

    branch = request.user.assigned_branch

    qr_payload = {
        "branch_id": branch.id,
        "type": "STORE_SESSION"
    }

    qr = qrcode.make(json.dumps(qr_payload))
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, "core/branch_qr.html", {
        "branch": branch,
        "qr_base64": qr_base64,
        "active": "qr"
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_branch_products(request):

    session_token = request.GET.get("session_token")

    if not session_token:
        return JsonResponse({"error": "Session required"}, status=400)

    try:
        session = StoreSession.objects.get(
            session_token=session_token,
            user=request.user,
            is_active=True
        )
    except StoreSession.DoesNotExist:
        return JsonResponse({"error": "Invalid session"}, status=403)

    branch = session.branch

    stocks = BranchStock.objects.filter(branch=branch).select_related('product')

    data = []

    for stock in stocks:
        data.append({
            "name": stock.product.name,
            "barcode": stock.product.barcode,
            "price": stock.current_price,
            "stock": stock.quantity,
        })

    return JsonResponse({
        "branch": branch.name,
        "products": data
    })

from .models import StoreSession


@csrf_exempt
@login_required
def api_verify_presence(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        branch_id = body.get("branch_id")
        detected_ssid = body.get("detected_ssid")
    except Exception:
        return JsonResponse({"error": "Invalid payload"}, status=400)

    if not branch_id or not detected_ssid:
        return JsonResponse({"error": "Missing data"}, status=400)

    branch = get_object_or_404(Branch, id=branch_id)

    if branch.wifi_ssid != detected_ssid:
        return JsonResponse({"verified": False, "reason": "SSID mismatch"}, status=403)

    # 🔥 STEP 1 — Kill old active session
    old_session = StoreSession.objects.filter(
        user=request.user,
        is_active=True
    ).first()

    if old_session:
        old_session.is_active = False
        old_session.save()

        # Delete old cart tied to that session
        Cart.objects.filter(session=old_session).delete()

    # 🔥 STEP 2 — Create new session
    session = StoreSession.objects.create(
        branch=branch,
        user=request.user,
        verified_ssid=detected_ssid,
        expires_at=timezone.now() + timedelta(minutes=60)
    )

    return JsonResponse({
        "verified": True,
        "session_id": session.id,
        "branch_name": branch.name,
        "expires_at": session.expires_at
    })

@login_required
def manage_guards(request):
    # Only Branch Managers can manage guards
    if request.user.role != 'branch':
        messages.error(request, "Access denied. Only Branch Managers can manage guards.")
        return redirect('dashboard')

    branch = request.user.assigned_branch

    if request.method == "POST":
        company_name = request.POST.get("company_name")
        username = request.POST.get("username")
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Validation checks
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
        else:
            try:
                User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    full_name=full_name,
                    role='guard',
                    assigned_branch=branch,
                    company_name=company_name if company_name else branch.company.company_name,
                    is_active=True,
                    is_verified=True
                )

                messages.success(request, f"Guard {full_name} created successfully.")
                return redirect('manage_guards')

            except Exception as e:
                messages.error(request, f"Error: {e}")

    guards = User.objects.filter(
        role='guard',
        assigned_branch=branch
    ).order_by('-date_joined')

    return render(request, "core/manage_guards.html", {
        "guards": guards,
        "branch": branch,
        "active": "guards"
    })

@login_required
def delete_guard(request, guard_id):

    # Only branch managers allowed
    if request.user.role != 'branch':
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    branch = request.user.assigned_branch

    try:
        guard = User.objects.get(
            id=guard_id,
            role='guard',
            assigned_branch=branch
        )

        guard.delete()
        messages.success(request, "Guard removed successfully.")

    except User.DoesNotExist:
        messages.error(request, "Guard not found.")

    return redirect('manage_guards')


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required


@csrf_protect
def guard_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = User.objects.get(email=email)
            username = user.username
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password")
            return redirect("auth_page")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            print("LOGIN:", user.email, user.role)
            
            # Redirect based on role
            if user.role == "guard":
                return redirect("guard_dashboard")
            elif user.role == "teller":
                return redirect("pos_terminal")
            elif user.role in ["company", "branch"]:
                return redirect("dashboard")
            else:
                return redirect("auth_page")
        
        messages.error(request, "Invalid credentials")
        return redirect("auth_page")

    return redirect("auth_page")

@login_required(login_url='auth_page')
def guard_dashboard(request):
    if request.user.role != "guard":
        messages.error(request, "Access denied.")
        return redirect("auth_page")  # redirect non-guards to main dashboard or login

    return render(request, "core/guard_dashboard.html", {
        "active": "guard_dashboard",
    })
from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
   
   
    path('admin/', admin.site.urls),

    

    # ✅ Products API
    path('api/', include('products.urls')),
    path('', include('core.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

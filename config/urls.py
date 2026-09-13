"""系统总路由。"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('goods/', include('apps.goods.urls')),
    path('purchase/', include('apps.purchase.urls')),
    path('sales/', include('apps.sales.urls')),
    path('member/', include('apps.member.urls')),
    path('report/', include('apps.report.urls')),
    path('', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

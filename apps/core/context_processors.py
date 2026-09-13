"""全局模板上下文。"""

from django.conf import settings
from django.db.models import F

from apps.goods.models import Product


def site_info(request):
    """注入站点名称与库存预警数量到所有模板。"""
    low_stock_count = 0
    if getattr(request, 'user', None) and request.user.is_authenticated:
        low_stock_count = Product.objects.filter(
            status=Product.STATUS_ON, stock__lte=F('safety_stock')
        ).count()
    return {
        'SHOP_NAME': getattr(settings, 'SHOP_NAME', '社区超市'),
        'SYSTEM_VERSION': 'v1.0.0',
        'low_stock_count': low_stock_count,
    }

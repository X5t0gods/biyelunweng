"""系统首页（经营看板）。"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.core.utils import local_today
from apps.goods.models import Product
from apps.member.models import Member
from apps.sales.models import Sale, SaleItem


@login_required
def dashboard(request):
    today = local_today()
    week_ago = today - timedelta(days=6)

    # 今日经营概况
    today_sales = Sale.objects.filter(created_at__date=today, status=Sale.STATUS_DONE)
    today_amount = today_sales.aggregate(t=Sum('actual_amount'), c=Sum('cost_amount'))
    today_total = today_amount['t'] or 0
    today_profit = (today_amount['t'] or 0) - (today_amount['c'] or 0)

    # 本月累计
    month_start = today.replace(day=1)
    month_amount = Sale.objects.filter(
        created_at__date__gte=month_start, status=Sale.STATUS_DONE
    ).aggregate(t=Sum('actual_amount'))['t'] or 0

    # 近 7 日销售趋势
    trend_qs = (
        Sale.objects.filter(created_at__date__gte=week_ago, status=Sale.STATUS_DONE)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('actual_amount'), profit=Sum('actual_amount') - Sum('cost_amount'),
                  orders=Count('id'))
        .order_by('day')
    )
    trend_map = {row['day']: row for row in trend_qs}
    trend_labels, trend_totals, trend_profits = [], [], []
    for i in range(7):
        day = week_ago + timedelta(days=i)
        row = trend_map.get(day)
        trend_labels.append(day.strftime('%m-%d'))
        trend_totals.append(float(row['total'] or 0) if row else 0)
        trend_profits.append(float(row['profit'] or 0) if row else 0)

    # 热销商品 TOP 10
    hot_products = (
        SaleItem.objects.filter(sale__status=Sale.STATUS_DONE)
        .values('product__name')
        .annotate(qty=Sum('quantity'), amount=Sum('subtotal'))
        .order_by('-qty')[:10]
    )

    # 分类销售占比
    category_sales = (
        SaleItem.objects.filter(sale__status=Sale.STATUS_DONE)
        .values('product__category__name')
        .annotate(amount=Sum('subtotal'))
        .order_by('-amount')
    )

    # 库存预警：总数单独统计，列表只取前 8 条展示
    low_stock_qs = Product.objects.filter(status=Product.STATUS_ON, stock__lte=F('safety_stock'))
    low_stock = low_stock_qs.order_by('stock')[:8]

    # 最近订单
    recent_sales = Sale.objects.select_related('member', 'cashier').order_by('-created_at')[:8]

    context = {
        'today_total': today_total,
        'today_profit': today_profit,
        'today_orders': today_sales.count(),
        'month_amount': month_amount,
        'member_count': Member.objects.filter(is_active=True).count(),
        'product_count': Product.objects.count(),
        'low_stock_count': low_stock_qs.count(),
        'low_stock': low_stock,
        'trend_labels': trend_labels,
        'trend_totals': trend_totals,
        'trend_profits': trend_profits,
        'hot_products': list(hot_products),
        'category_sales': list(category_sales),
        'recent_sales': recent_sales,
    }
    return render(request, 'core/dashboard.html', context)

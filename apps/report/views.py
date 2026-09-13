"""统计报表视图。"""

import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.utils import local_today
from apps.goods.models import Category, Product
from apps.member.models import Member
from apps.purchase.models import PurchaseOrder
from apps.sales.models import Sale, SaleItem


def _parse_range(request, default_days=30):
    """解析日期区间，默认近 30 天。"""
    today = local_today()
    start = request.GET.get('start') or (today - timedelta(days=default_days - 1)).isoformat()
    end = request.GET.get('end') or today.isoformat()
    return start, end


@login_required
def sales_report(request):
    """销售统计报表。"""
    start, end = _parse_range(request)
    qs = Sale.objects.filter(created_at__date__gte=start, created_at__date__lte=end,
                             status=Sale.STATUS_DONE)

    summary = qs.aggregate(
        amount=Sum('actual_amount'), cost=Sum('cost_amount'), orders=Count('id'),
        discount=Sum('discount_amount'),
    )
    total_amount = summary['amount'] or 0
    total_cost = summary['cost'] or 0
    profit = total_amount - total_cost

    # 每日趋势
    daily = (qs.annotate(day=TruncDate('created_at')).values('day')
             .annotate(amount=Sum('actual_amount'), cost=Sum('cost_amount'), orders=Count('id'))
             .order_by('day'))
    daily_labels = [r['day'].strftime('%m-%d') for r in daily]
    daily_amounts = [float(r['amount'] or 0) for r in daily]
    daily_profits = [float((r['amount'] or 0) - (r['cost'] or 0)) for r in daily]

    # 分类销售
    category_data = (SaleItem.objects.filter(sale__in=qs)
                     .values('product__category__name')
                     .annotate(amount=Sum('subtotal'), qty=Sum('quantity'))
                     .order_by('-amount'))

    # 热销商品 TOP 20
    top_goods = (SaleItem.objects.filter(sale__in=qs)
                 .values('product__name', 'product__barcode')
                 .annotate(qty=Sum('quantity'), amount=Sum('subtotal'))
                 .order_by('-qty')[:20])

    # 支付方式分布
    pay_data = qs.values('pay_method').annotate(amount=Sum('actual_amount'),
                                                orders=Count('id')).order_by('-amount')

    return render(request, 'report/sales_report.html', {
        'start': start, 'end': end,
        'summary': summary,
        'total_amount': total_amount,
        'total_cost': total_cost,
        'profit': profit,
        'avg_order': (total_amount / summary['orders']) if summary['orders'] else 0,
        'daily_labels': daily_labels,
        'daily_amounts': daily_amounts,
        'daily_profits': daily_profits,
        'category_data': list(category_data),
        'top_goods': list(top_goods),
        'pay_data': list(pay_data),
        'pay_choices': dict(Sale.PAY_CHOICES),
    })


@login_required
def sales_export(request):
    """导出销售明细 CSV（Excel 可直接打开）。"""
    start, end = _parse_range(request)
    qs = Sale.objects.filter(created_at__date__gte=start, created_at__date__lte=end,
                             status=Sale.STATUS_DONE).select_related('member', 'cashier')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="sales_{start}_{end}.csv"'
    writer = csv.writer(response)
    writer.writerow(['销售单号', '销售时间', '会员', '商品件数', '应收金额', '优惠金额',
                     '实收金额', '成本金额', '毛利', '支付方式', '收银员'])
    for s in qs:
        writer.writerow([
            s.order_no, s.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            s.member.name if s.member else '散客',
            s.total_quantity, s.total_amount, s.discount_amount, s.actual_amount,
            s.cost_amount, s.profit, s.get_pay_method_display(),
            s.cashier.real_name or s.cashier.username,
        ])
    return response


@login_required
def profit_report(request):
    """利润分析。"""
    start, end = _parse_range(request, default_days=180)
    qs = Sale.objects.filter(created_at__date__gte=start, created_at__date__lte=end,
                             status=Sale.STATUS_DONE)

    monthly = (qs.annotate(month=TruncMonth('created_at')).values('month')
               .annotate(amount=Sum('actual_amount'), cost=Sum('cost_amount'),
                         orders=Count('id')).order_by('month'))

    # 商品毛利排行
    goods_profit = (SaleItem.objects.filter(sale__in=qs)
                    .values('product__name')
                    .annotate(qty=Sum('quantity'), amount=Sum('subtotal'),
                              cost=Sum(F('quantity') * F('cost_price')))
                    .order_by('-amount')[:20])

    purchase_total = PurchaseOrder.objects.filter(
        status=PurchaseOrder.STATUS_CONFIRMED,
        confirmed_at__date__gte=start, confirmed_at__date__lte=end
    ).aggregate(t=Sum('total_amount'))['t'] or 0

    total_amount = qs.aggregate(t=Sum('actual_amount'))['t'] or 0
    total_cost = qs.aggregate(t=Sum('cost_amount'))['t'] or 0

    return render(request, 'report/profit_report.html', {
        'start': start, 'end': end,
        'monthly': list(monthly),
        'goods_profit': list(goods_profit),
        'purchase_total': purchase_total,
        'total_amount': total_amount,
        'total_cost': total_cost,
        'profit': total_amount - total_cost,
    })


@login_required
def goods_report(request):
    """商品销售排行。"""
    start, end = _parse_range(request)
    qs = Sale.objects.filter(created_at__date__gte=start, created_at__date__lte=end,
                             status=Sale.STATUS_DONE)
    rows = (SaleItem.objects.filter(sale__in=qs)
            .values('product__name', 'product__barcode', 'product__category__name')
            .annotate(qty=Sum('quantity'), amount=Sum('subtotal'))
            .order_by('-amount'))
    return render(request, 'report/goods_report.html', {
        'start': start, 'end': end, 'rows': list(rows),
    })


@login_required
def stock_report(request):
    """库存与会员概览报表。"""
    products = Product.objects.select_related('category', 'supplier').all()
    low = products.filter(stock__lte=F('safety_stock'))
    total_value = sum(float(p.stock_value) for p in products)
    categories = Category.objects.all()

    # 分类库存分布
    category_stock = (products.values('category__name')
                      .annotate(total=Sum('stock'), value=Sum(F('stock') * F('purchase_price')))
                      .order_by('-total'))

    members = Member.objects.select_related('level').all()
    return render(request, 'report/stock_report.html', {
        'products': products,
        'low_count': low.count(),
        'total_value': total_value,
        'category_stock': list(category_stock),
        'categories': categories,
        'member_count': members.count(),
        'member_balance': sum(float(m.balance) for m in members),
        'member_points': sum(m.points for m in members),
    })

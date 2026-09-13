"""销售收银与退货视图。"""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.mixins import manager_required
from apps.core.models import StockLog
from apps.core.utils import generate_order_no, local_today, write_log
from apps.goods.models import Product
from apps.member.models import Member
from apps.sales.forms import CheckoutForm, SaleReturnForm
from apps.sales.models import Sale, SaleItem, SaleReturn, SaleReturnItem

CART_KEY = 'pos_cart'


# ----------------------------- 购物车辅助 -----------------------------

def get_cart(request):
    cart = request.session.get(CART_KEY)
    if not cart:
        cart = {'items': {}, 'member_id': None}
        request.session[CART_KEY] = cart
    return cart


def save_cart(request, cart):
    request.session[CART_KEY] = cart
    request.session.modified = True


def cart_products(cart):
    """把 session 购物车转换为带商品对象的明细列表。"""
    rows = []
    for pid, qty in cart['items'].items():
        product = Product.objects.filter(pk=pid).first()
        if product:
            rows.append({
                'product': product,
                'quantity': qty,
                'subtotal': product.sale_price * qty,
            })
    return rows


def cart_totals(rows, member):
    total = sum((r['subtotal'] for r in rows), Decimal('0'))
    discount = Decimal('0')
    if member:
        discount = (total * (Decimal('1') - Decimal(str(member.discount)))).quantize(Decimal('0.01'))
    return total, discount, total - discount


# ----------------------------- 收银台 -----------------------------

@login_required
def pos(request):
    """前台收银（POS）。"""
    cart = get_cart(request)
    member = None
    if cart.get('member_id'):
        member = Member.objects.filter(pk=cart['member_id']).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        if not action and request.POST.get('code'):
            # 点击“常用商品”按钮时只提交条码，默认视为加入购物车
            action = 'add'

        if action == 'add':
            code = request.POST.get('code', '').strip()
            product = Product.objects.filter(
                Q(barcode__iexact=code) | Q(name__icontains=code), status=Product.STATUS_ON
            ).first()
            if not product:
                messages.error(request, f'未找到商品：{code}')
            elif product.stock <= 0:
                messages.error(request, f'【{product.name}】库存不足，无法销售。')
            else:
                pid = str(product.pk)
                current = cart['items'].get(pid, 0)
                if current + 1 > product.stock:
                    messages.error(request, f'【{product.name}】库存仅剩 {product.stock}{product.unit}。')
                else:
                    cart['items'][pid] = current + 1
                    save_cart(request, cart)
            return redirect('sales:pos')

        if action == 'update':
            pid = str(request.POST.get('pid', ''))
            try:
                qty = int(request.POST.get('qty', 1))
            except ValueError:
                qty = 1
            if pid in cart['items']:
                if qty <= 0:
                    cart['items'].pop(pid)
                else:
                    product = Product.objects.filter(pk=pid).first()
                    if product and qty > product.stock:
                        messages.error(request, f'【{product.name}】库存仅剩 {product.stock}{product.unit}。')
                        qty = min(qty, product.stock)
                    cart['items'][pid] = qty
                save_cart(request, cart)
            return redirect('sales:pos')

        if action == 'remove':
            cart['items'].pop(str(request.POST.get('pid', '')), None)
            save_cart(request, cart)
            return redirect('sales:pos')

        if action == 'member':
            keyword = request.POST.get('member_key', '').strip()
            m = Member.objects.filter(Q(card_no__iexact=keyword) | Q(phone=keyword),
                                      is_active=True).first()
            if m:
                cart['member_id'] = m.pk
                save_cart(request, cart)
                messages.success(request, f'已绑定会员：{m.name}（{m.level_name}）')
            else:
                messages.error(request, '未找到该会员，请检查卡号或手机号。')
            return redirect('sales:pos')

        if action == 'clear_member':
            cart['member_id'] = None
            save_cart(request, cart)
            return redirect('sales:pos')

        if action == 'clear':
            cart['items'] = {}
            cart['member_id'] = None
            save_cart(request, cart)
            messages.info(request, '购物车已清空。')
            return redirect('sales:pos')

        if action == 'checkout':
            return _checkout(request, cart)

    rows = cart_products(cart)
    total, discount, actual = cart_totals(rows, member)

    # 常用商品：按近 30 天真实销量排序，而非随机
    since = local_today() - timedelta(days=30)
    hot_ids = (
        SaleItem.objects.filter(sale__status=Sale.STATUS_DONE, sale__created_at__date__gte=since)
        .values('product_id')
        .annotate(qty=Sum('quantity'))
        .order_by('-qty')
        .values_list('product_id', flat=True)[:12]
    )
    hot = [Product.objects.get(pk=pid) for pid in hot_ids if Product.objects.filter(pk=pid).exists()]
    if not hot:
        hot = list(Product.objects.filter(status=Product.STATUS_ON)[:12])
    return render(request, 'sales/pos.html', {
        'rows': rows,
        'member': member,
        'total': total,
        'discount': discount,
        'actual': actual,
        'form': CheckoutForm(),
        'hot_products': hot,
    })


@login_required
@transaction.atomic
def _checkout(request, cart):
    """结算：生成销售单、扣减库存、累计会员积分。"""
    rows = cart_products(cart)
    if not rows:
        messages.error(request, '购物车为空，无法结算。')
        return redirect('sales:pos')

    member = None
    if cart.get('member_id'):
        member = Member.objects.filter(pk=cart['member_id']).first()

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(request, '支付信息有误，请重新选择支付方式。')
        return redirect('sales:pos')

    pay_method = form.cleaned_data['pay_method']
    total, discount, actual = cart_totals(rows, member)
    cost_amount = sum((r['product'].purchase_price * r['quantity'] for r in rows), Decimal('0'))

    if pay_method == Sale.PAY_BALANCE:
        if not member:
            messages.error(request, '使用会员余额支付前请先绑定会员。')
            return redirect('sales:pos')
        if member.balance < actual:
            messages.error(request, f'会员余额不足，当前余额 ¥{member.balance}。')
            return redirect('sales:pos')

    # 再次校验库存
    for row in rows:
        if row['product'].stock < row['quantity']:
            messages.error(request, f'【{row["product"].name}】库存不足，当前 {row["product"].stock}。')
            return redirect('sales:pos')

    sale = Sale.objects.create(
        order_no=generate_order_no('XS', Sale),
        member=member,
        cashier=request.user,
        total_amount=total,
        discount_amount=discount,
        actual_amount=actual,
        cost_amount=cost_amount,
        pay_method=pay_method,
        remark=form.cleaned_data.get('remark', ''),
    )

    for row in rows:
        SaleItem.objects.create(
            sale=sale,
            product=row['product'],
            quantity=row['quantity'],
            price=row['product'].sale_price,
            cost_price=row['product'].purchase_price,
        )
        row['product'].change_stock(
            -row['quantity'],
            change_type=StockLog.TYPE_SALE,
            operator=request.user,
            related_no=sale.order_no,
            remark='前台销售出库',
        )

    # 会员积分与余额
    if member:
        rate = Decimal(str(member.level.point_rate)) if member.level else Decimal('1')
        points = int(actual * rate)
        sale.points_earned = points
        sale.save(update_fields=['points_earned'])
        member.points += points
        member.total_points += points
        member.total_spend += actual
        if pay_method == Sale.PAY_BALANCE:
            member.balance -= actual
        member.save()
        member.refresh_level()

    cart['items'] = {}
    cart['member_id'] = None
    save_cart(request, cart)

    write_log(request, 'sales', '销售结算',
              f'生成销售单 {sale.order_no}，实收 ¥{actual}')
    messages.success(request, f'结算成功！销售单号 {sale.order_no}，应收 ¥{actual}。')
    return redirect('sales:sale_detail', pk=sale.pk)


# ----------------------------- 销售单 -----------------------------

@login_required
def sale_list(request):
    keyword = request.GET.get('q', '').strip()
    pay = request.GET.get('pay', '')
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    qs = Sale.objects.select_related('member', 'cashier').all()
    if keyword:
        qs = qs.filter(Q(order_no__icontains=keyword) | Q(member__name__icontains=keyword)
                       | Q(member__card_no__icontains=keyword))
    if pay:
        qs = qs.filter(pay_method=pay)
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)

    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    summary = qs.aggregate(
        amount=__import__('django.db.models', fromlist=['Sum']).Sum('actual_amount'),
        profit=__import__('django.db.models', fromlist=['Sum']).Sum('actual_amount')
        - __import__('django.db.models', fromlist=['Sum']).Sum('cost_amount'),
    )
    return render(request, 'sales/sale_list.html', {
        'page_obj': page_obj, 'keyword': keyword, 'pay': pay, 'start': start, 'end': end,
        'pay_choices': Sale.PAY_CHOICES,
        'summary': summary,
        'query_params': f'q={keyword}&pay={pay}&start={start}&end={end}',
    })


@login_required
def sale_detail(request, pk):
    obj = get_object_or_404(Sale, pk=pk)
    return render(request, 'sales/sale_detail.html', {'object': obj})


@login_required
@manager_required
@transaction.atomic
def sale_void(request, pk):
    """作废销售单（回退库存）。"""
    obj = get_object_or_404(Sale, pk=pk)
    if obj.status != Sale.STATUS_DONE:
        messages.error(request, '仅已完成的销售单可作废。')
        return redirect('sales:sale_detail', pk=obj.pk)

    for item in obj.items.select_related('product'):
        item.product.change_stock(
            item.quantity, change_type=StockLog.TYPE_RETURN, operator=request.user,
            related_no=obj.order_no, remark='销售单作废回退库存'
        )

    # 回退会员权益：扣回积分、退还余额支付金额、扣减累计消费
    member = obj.member
    if member:
        member.points = max(0, member.points - obj.points_earned)
        member.total_points = max(0, member.total_points - obj.points_earned)
        member.total_spend = max(Decimal('0'), member.total_spend - obj.actual_amount)
        if obj.pay_method == Sale.PAY_BALANCE:
            member.balance += obj.actual_amount
        member.save()
        member.refresh_level()

    obj.status = Sale.STATUS_VOID
    obj.save(update_fields=['status'])
    write_log(request, 'sales', '作废销售单', f'作废销售单 {obj.order_no}，库存已回退')
    messages.success(request, f'销售单 {obj.order_no} 已作废，库存已回退。')
    return redirect('sales:sale_detail', pk=obj.pk)


# ----------------------------- 退货 -----------------------------

@login_required
def return_list(request):
    qs = SaleReturn.objects.select_related('sale', 'operator').all()
    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'sales/return_list.html', {'page_obj': page_obj, 'query_params': ''})


@login_required
@transaction.atomic
def return_create(request):
    """销售退货：按原销售单整单或部分退货。"""
    form = SaleReturnForm(request.POST or None)
    sale = None
    if request.method == 'POST' and form.is_valid():
        order_no = form.cleaned_data['sale_no'].strip()
        sale = Sale.objects.filter(order_no__iexact=order_no).first()
        if not sale:
            messages.error(request, f'未找到销售单：{order_no}')
        elif sale.status != Sale.STATUS_DONE:
            messages.error(request, '该销售单状态不允许退货。')
        else:
            items = []
            total = Decimal('0')
            for item in sale.items.select_related('product'):
                qty = int(request.POST.get(f'qty_{item.pk}', 0) or 0)
                if qty > 0:
                    if qty > item.quantity:
                        messages.error(request, f'【{item.product.name}】退货数量不能超过购买数量。')
                        return redirect('sales:return_create')
                    subtotal = item.price * qty
                    total += subtotal
                    items.append((item, qty, subtotal))
            if not items:
                messages.error(request, '请至少填写一项退货数量。')
            else:
                sale_return = SaleReturn.objects.create(
                    return_no=generate_order_no('TH', SaleReturn, field='return_no'),
                    sale=sale,
                    operator=request.user,
                    amount=total,
                    reason=form.cleaned_data.get('reason', ''),
                )
                for item, qty, subtotal in items:
                    SaleReturnItem.objects.create(
                        sale_return=sale_return, product=item.product,
                        quantity=qty, price=item.price,
                    )
                    item.product.change_stock(
                        qty, change_type=StockLog.TYPE_RETURN, operator=request.user,
                        related_no=sale_return.return_no, remark='销售退货入库'
                    )
                # 按退款比例回退会员权益（积分、储值、累计消费）
                member = sale.member
                if member:
                    ratio = (total / sale.actual_amount) if sale.actual_amount else Decimal('0')
                    back_points = int(Decimal(sale.points_earned) * ratio)
                    member.points = max(0, member.points - back_points)
                    member.total_points = max(0, member.total_points - back_points)
                    member.total_spend = max(Decimal('0'), member.total_spend - total)
                    if sale.pay_method == Sale.PAY_BALANCE:
                        # 会员余额支付的，退款原路退回储值账户
                        member.balance += total
                    member.save()
                    member.refresh_level()

                sale.status = Sale.STATUS_RETURNED
                sale.save(update_fields=['status'])
                write_log(request, 'sales', '销售退货',
                          f'退货单 {sale_return.return_no}，退款 ¥{total}')
                messages.success(request, f'退货处理成功，退款金额 ¥{total}。')
                return redirect('sales:return_detail', pk=sale_return.pk)
    return render(request, 'sales/return_form.html', {'form': form, 'sale': sale})


@login_required
def return_detail(request, pk):
    obj = get_object_or_404(SaleReturn, pk=pk)
    return render(request, 'sales/return_detail.html', {'object': obj})

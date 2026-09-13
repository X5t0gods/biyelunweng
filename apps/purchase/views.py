"""采购进货视图。"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.mixins import stock_required
from apps.core.models import StockLog
from apps.core.utils import generate_order_no, write_log
from apps.purchase.forms import PurchaseItemForm, PurchaseOrderForm
from apps.purchase.models import PurchaseItem, PurchaseOrder


@login_required
def order_list(request):
    """采购单列表。"""
    keyword = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    qs = PurchaseOrder.objects.select_related('supplier', 'operator').all()
    if keyword:
        qs = qs.filter(Q(order_no__icontains=keyword) | Q(supplier__name__icontains=keyword))
    if status:
        qs = qs.filter(status=status)

    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'purchase/order_list.html', {
        'page_obj': page_obj,
        'keyword': keyword,
        'status': status,
        'status_choices': PurchaseOrder.STATUS_CHOICES,
        'query_params': f'q={keyword}&status={status}',
    })


@login_required
@stock_required
def order_create(request):
    """新建采购单（待入库）。"""
    form = PurchaseOrderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        order = form.save(commit=False)
        order.operator = request.user
        order.order_no = generate_order_no('CG', PurchaseOrder)
        order.save()
        write_log(request, 'purchase', '新建采购单', f'采购单 {order.order_no}（{order.supplier.name}）')
        messages.success(request, f'采购单 {order.order_no} 已创建，请添加采购商品。')
        return redirect('purchase:order_detail', pk=order.pk)
    return render(request, 'purchase/order_form.html', {'form': form, 'title': '新建采购单'})


@login_required
def order_detail(request, pk):
    """采购单详情：添加商品明细并入库。"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    item_form = PurchaseItemForm(request.POST or None)
    if request.method == 'POST' and item_form.is_valid():
        if order.status != PurchaseOrder.STATUS_DRAFT:
            messages.error(request, '该采购单已处理，不能再添加商品。')
        else:
            item = item_form.save(commit=False)
            item.order = order
            item.save()
            order.recalc_total()
            write_log(request, 'purchase', '添加采购明细',
                      f'{order.order_no} 添加 {item.product.name} x {item.quantity}')
            messages.success(request, f'已添加 {item.product.name}。')
        return redirect('purchase:order_detail', pk=order.pk)
    return render(request, 'purchase/order_detail.html', {'object': order, 'item_form': item_form})


@login_required
@stock_required
def order_add_item(request, pk):
    """兼容入口：添加采购明细。"""
    return order_detail(request, pk)


@login_required
@stock_required
def order_delete_item(request, pk, item_pk):
    """删除采购明细。"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    item = get_object_or_404(PurchaseItem, pk=item_pk, order=order)
    if order.status != PurchaseOrder.STATUS_DRAFT:
        messages.error(request, '该采购单已入库，不能删除明细。')
    else:
        name = item.product.name
        item.delete()
        order.recalc_total()
        write_log(request, 'purchase', '删除采购明细', f'{order.order_no} 删除 {name}')
        messages.success(request, f'已删除明细 {name}。')
    return redirect('purchase:order_detail', pk=order.pk)


@login_required
@stock_required
@transaction.atomic
def order_confirm(request, pk):
    """采购单确认入库：更新库存并生成库存流水。"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status != PurchaseOrder.STATUS_DRAFT:
        messages.error(request, '该采购单已处理，请勿重复操作。')
        return redirect('purchase:order_detail', pk=order.pk)

    if not order.items.exists():
        messages.error(request, '请先添加采购商品。')
        return redirect('purchase:order_detail', pk=order.pk)

    for item in order.items.select_related('product'):
        item.product.change_stock(
            item.quantity,
            change_type=StockLog.TYPE_PURCHASE,
            operator=request.user,
            related_no=order.order_no,
            remark=f'采购入库（{order.supplier.name}）',
        )
    order.status = PurchaseOrder.STATUS_CONFIRMED
    order.confirmed_at = timezone.now()
    order.recalc_total()
    order.save(update_fields=['status', 'confirmed_at'])
    write_log(request, 'purchase', '采购入库',
              f'采购单 {order.order_no} 入库完成，总金额 ¥{order.total_amount}')
    messages.success(request, f'采购单 {order.order_no} 入库成功，库存已更新。')
    return redirect('purchase:order_detail', pk=order.pk)


@login_required
@stock_required
def order_cancel(request, pk):
    """取消采购单。"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status != PurchaseOrder.STATUS_DRAFT:
        messages.error(request, '仅待入库的采购单可以取消。')
    else:
        order.status = PurchaseOrder.STATUS_CANCELED
        order.save(update_fields=['status'])
        write_log(request, 'purchase', '取消采购单', f'取消采购单 {order.order_no}')
        messages.success(request, '采购单已取消。')
    return redirect('purchase:order_list')


@login_required
@stock_required
def order_delete(request, pk):
    """删除待入库采购单。"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.status != PurchaseOrder.STATUS_DRAFT:
        messages.error(request, '仅待入库的采购单可以删除。')
    else:
        no = order.order_no
        order.delete()
        write_log(request, 'purchase', '删除采购单', f'删除采购单 {no}')
        messages.success(request, f'采购单 {no} 已删除。')
    return redirect('purchase:order_list')

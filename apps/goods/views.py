"""商品、分类、供应商与库存视图。"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.mixins import stock_required
from apps.core.models import StockLog
from apps.core.utils import write_log
from apps.goods.forms import CategoryForm, ProductForm, StockAdjustForm, SupplierForm
from apps.goods.models import Category, Product, Supplier


# ----------------------------- 商品分类 -----------------------------

@login_required
def category_list(request):
    categories = Category.objects.annotate(
        product_count=Count('products__id'),
        stock_qty=Sum('products__stock'),
    ).order_by('sort', 'id')
    return render(request, 'goods/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'goods', '新增分类', f'新增商品分类：{obj.name}')
        messages.success(request, f'分类【{obj.name}】创建成功。')
        return redirect('goods:category_list')
    return render(request, 'goods/category_form.html', {'form': form, 'title': '新增商品分类'})


@login_required
def category_update(request, pk):
    obj = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'goods', '修改分类', f'修改商品分类：{obj.name}')
        messages.success(request, '分类信息已更新。')
        return redirect('goods:category_list')
    return render(request, 'goods/category_form.html', {'form': form, 'title': '编辑商品分类', 'object': obj})


@login_required
def category_delete(request, pk):
    obj = get_object_or_404(Category, pk=pk)
    if obj.products.exists():
        messages.error(request, f'分类【{obj.name}】下仍有商品，无法删除。')
    else:
        name = obj.name
        obj.delete()
        write_log(request, 'goods', '删除分类', f'删除商品分类：{name}')
        messages.success(request, f'已删除分类【{name}】。')
    return redirect('goods:category_list')


# ----------------------------- 供应商 -----------------------------

@login_required
def supplier_list(request):
    keyword = request.GET.get('q', '').strip()
    qs = Supplier.objects.all()
    if keyword:
        qs = qs.filter(Q(name__icontains=keyword) | Q(contact__icontains=keyword)
                       | Q(phone__icontains=keyword))
    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'goods/supplier_list.html', {
        'page_obj': page_obj, 'keyword': keyword, 'query_params': f'q={keyword}',
    })


@login_required
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'goods', '新增供应商', f'新增供应商：{obj.name}')
        messages.success(request, f'供应商【{obj.name}】创建成功。')
        return redirect('goods:supplier_list')
    return render(request, 'goods/supplier_form.html', {'form': form, 'title': '新增供应商'})


@login_required
def supplier_update(request, pk):
    obj = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'goods', '修改供应商', f'修改供应商：{obj.name}')
        messages.success(request, '供应商信息已更新。')
        return redirect('goods:supplier_list')
    return render(request, 'goods/supplier_form.html', {'form': form, 'title': '编辑供应商', 'object': obj})


@login_required
def supplier_delete(request, pk):
    obj = get_object_or_404(Supplier, pk=pk)
    if obj.products.exists() or obj.purchase_orders.exists():
        messages.error(request, f'供应商【{obj.name}】已关联商品或采购单，无法删除。')
    else:
        name = obj.name
        obj.delete()
        write_log(request, 'goods', '删除供应商', f'删除供应商：{name}')
        messages.success(request, f'已删除供应商【{name}】。')
    return redirect('goods:supplier_list')


# ----------------------------- 商品 -----------------------------

@login_required
def product_list(request):
    keyword = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    only_low = request.GET.get('low', '')

    qs = Product.objects.select_related('category', 'supplier').all()
    if keyword:
        qs = qs.filter(Q(name__icontains=keyword) | Q(barcode__icontains=keyword)
                       | Q(spec__icontains=keyword))
    if category_id:
        qs = qs.filter(category_id=category_id)
    if status:
        qs = qs.filter(status=status)
    if only_low:
        qs = qs.filter(stock__lte=F('safety_stock'))

    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'goods/product_list.html', {
        'page_obj': page_obj,
        'keyword': keyword,
        'category_id': category_id,
        'status': status,
        'only_low': only_low,
        'categories': Category.objects.all(),
        'query_params': f'q={keyword}&category={category_id}&status={status}&low={only_low}',
    })


@login_required
def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'goods', '新增商品', f'新增商品：{obj.name}（{obj.barcode}）')
        messages.success(request, f'商品【{obj.name}】创建成功。')
        return redirect('goods:product_list')
    return render(request, 'goods/product_form.html', {'form': form, 'title': '新增商品'})


@login_required
def product_update(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'goods', '修改商品', f'修改商品信息：{obj.name}')
        messages.success(request, '商品信息已更新。')
        return redirect('goods:product_detail', pk=obj.pk)
    return render(request, 'goods/product_form.html', {'form': form, 'title': '编辑商品', 'object': obj})


@login_required
def product_toggle(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    obj.status = Product.STATUS_OFF if obj.status == Product.STATUS_ON else Product.STATUS_ON
    obj.save(update_fields=['status'])
    write_log(request, 'goods', '变更商品状态', f'{obj.name} → {obj.get_status_display()}')
    messages.success(request, f'商品【{obj.name}】已{obj.get_status_display()}。')
    return redirect('goods:product_list')


@login_required
def product_detail(request, pk):
    obj = get_object_or_404(Product, pk=pk)
    logs = obj.stock_logs.select_related('operator').all()[:20]
    return render(request, 'goods/product_detail.html', {'object': obj, 'logs': logs})


# ----------------------------- 库存 -----------------------------

@login_required
def stock_list(request):
    keyword = request.GET.get('q', '').strip()
    qs = Product.objects.select_related('category').all()
    if keyword:
        qs = qs.filter(Q(name__icontains=keyword) | Q(barcode__icontains=keyword))
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    total_value = sum(float(p.stock_value) for p in qs)
    return render(request, 'goods/stock_list.html', {
        'page_obj': page_obj, 'keyword': keyword, 'total_value': total_value,
        'query_params': f'q={keyword}',
    })


@login_required
@stock_required
def stock_adjust(request, pk):
    """库存盘点 / 报损 / 手动调整。"""
    obj = get_object_or_404(Product, pk=pk)
    form = StockAdjustForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quantity = form.cleaned_data['quantity']
        try:
            obj.change_stock(
                quantity,
                change_type=form.cleaned_data['change_type'],
                operator=request.user,
                related_no='',
                remark=form.cleaned_data.get('remark', ''),
            )
            write_log(request, 'stock', '库存调整',
                      f'{obj.name} 调整 {quantity:+d}，调整后库存 {obj.stock}')
            messages.success(request, f'库存调整成功，当前库存 {obj.stock}{obj.unit}。')
            return redirect('goods:stock_list')
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'goods/stock_adjust.html', {'form': form, 'object': obj})


@login_required
def stock_log_list(request):
    qs = StockLog.objects.select_related('product', 'operator').all()
    change_type = request.GET.get('type', '')
    keyword = request.GET.get('q', '')
    if change_type:
        qs = qs.filter(change_type=change_type)
    if keyword:
        qs = qs.filter(product__name__icontains=keyword)
    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'goods/stock_log_list.html', {
        'page_obj': page_obj, 'type_choices': StockLog.TYPE_CHOICES,
        'change_type': change_type, 'keyword': keyword,
        'query_params': f'type={change_type}&q={keyword}',
    })


@login_required
def stock_alert(request):
    qs = Product.objects.select_related('category', 'supplier').filter(
        stock__lte=F('safety_stock')).order_by('stock')
    return render(request, 'goods/stock_alert.html', {'objects': qs})


# ----------------------------- AJAX -----------------------------

@login_required
def product_api(request):
    """按条码或关键字检索商品，供收银台使用。"""
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'success': False, 'message': '请输入条码或商品名称'})
    product = Product.objects.filter(
        Q(barcode__iexact=code) | Q(name__icontains=code), status=Product.STATUS_ON
    ).first()
    if not product:
        return JsonResponse({'success': False, 'message': '未找到该商品'})
    return JsonResponse({
        'success': True,
        'data': {
            'id': product.pk,
            'name': product.name,
            'barcode': product.barcode,
            'spec': product.spec,
            'unit': product.unit,
            'price': str(product.sale_price),
            'stock': product.stock,
        },
    })

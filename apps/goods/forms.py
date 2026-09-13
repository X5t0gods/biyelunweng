"""商品相关表单。"""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.core.models import StockLog
from apps.goods.models import Category, Product, Supplier


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'code', 'description', 'sort']
        labels = {'name': '分类名称', 'code': '分类编码', 'description': '描述', 'sort': '排序值'}


class SupplierForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact', 'phone', 'address', 'bank_account', 'remark', 'is_active']
        labels = {
            'name': '供应商名称', 'contact': '联系人', 'phone': '联系电话', 'address': '地址',
            'bank_account': '收款账号', 'remark': '备注', 'is_active': '合作状态',
        }
        widgets = {'remark': forms.Textarea(attrs={'rows': 2})}


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'barcode', 'category', 'supplier', 'spec', 'unit', 'purchase_price',
                  'sale_price', 'stock', 'safety_stock', 'shelf_life_days', 'status', 'remark']
        labels = {
            'name': '商品名称', 'barcode': '条形码', 'category': '所属分类', 'supplier': '默认供应商',
            'spec': '规格', 'unit': '单位', 'purchase_price': '进价(元)', 'sale_price': '售价(元)',
            'stock': '当前库存', 'safety_stock': '安全库存', 'shelf_life_days': '保质期(天)',
            'status': '状态', 'remark': '备注',
        }
        widgets = {'remark': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        cleaned = super().clean()
        purchase = cleaned.get('purchase_price') or 0
        sale = cleaned.get('sale_price') or 0
        if sale and purchase and sale < purchase:
            raise forms.ValidationError('售价不能低于进价，请检查后重新填写。')
        return cleaned


class StockAdjustForm(BootstrapFormMixin, forms.Form):
    """库存手动调整 / 盘点。"""

    change_type = forms.ChoiceField(label='调整类型', choices=(
        (StockLog.TYPE_CHECK, '库存盘点'),
        (StockLog.TYPE_LOSS, '商品报损'),
        (StockLog.TYPE_MANUAL, '手动调整'),
    ))
    quantity = forms.IntegerField(label='变动数量（负数表示减少）')
    remark = forms.CharField(label='调整说明', required=False, widget=forms.Textarea(attrs={'rows': 2}))

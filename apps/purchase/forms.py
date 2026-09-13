"""采购表单。"""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.goods.models import Product, Supplier
from apps.purchase.models import PurchaseItem, PurchaseOrder


class PurchaseOrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'remark']
        labels = {'supplier': '供应商', 'remark': '备注'}
        widgets = {'remark': forms.Textarea(attrs={'rows': 2})}


class PurchaseItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ['product', 'quantity', 'price']
        labels = {'product': '采购商品', 'quantity': '采购数量', 'price': '采购单价(元)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(status=Product.STATUS_ON)

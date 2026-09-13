"""销售相关表单。"""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.sales.models import Sale


class CheckoutForm(BootstrapFormMixin, forms.Form):
    """收银结算。"""

    pay_method = forms.ChoiceField(label='支付方式', choices=Sale.PAY_CHOICES, initial=Sale.PAY_CASH)
    remark = forms.CharField(label='备注', required=False, widget=forms.Textarea(attrs={'rows': 2}))


class SaleReturnForm(BootstrapFormMixin, forms.Form):
    """销售退货：选择原销售单。"""

    sale_no = forms.CharField(label='原销售单号', max_length=30)
    reason = forms.CharField(label='退货原因', required=False, widget=forms.Textarea(attrs={'rows': 2}))

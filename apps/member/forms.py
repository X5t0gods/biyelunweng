"""会员表单。"""

from django import forms

from apps.core.forms import BootstrapFormMixin
from apps.member.models import Member, MemberLevel


class MemberLevelForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MemberLevel
        fields = ['name', 'discount', 'point_rate', 'min_points', 'remark']
        labels = {
            'name': '等级名称', 'discount': '折扣率', 'point_rate': '积分倍率',
            'min_points': '升级所需积分', 'remark': '备注',
        }


class MemberForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Member
        fields = ['card_no', 'name', 'phone', 'gender', 'birthday', 'level', 'address',
                  'is_active', 'remark']
        labels = {
            'card_no': '会员卡号', 'name': '姓名', 'phone': '手机号', 'gender': '性别',
            'birthday': '生日', 'level': '会员等级', 'address': '住址', 'is_active': '状态', 'remark': '备注',
        }
        widgets = {'birthday': forms.DateInput(attrs={'type': 'date'})}


class RechargeForm(BootstrapFormMixin, forms.Form):
    """会员储值充值。"""

    amount = forms.DecimalField(label='充值金额(元)', max_digits=10, decimal_places=2, min_value=0.01)
    remark = forms.CharField(label='备注', required=False)

"""账号相关表单。"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm

from apps.accounts.models import User
from apps.core.forms import BootstrapFormMixin


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """登录表单。"""

    username = forms.CharField(label='登录账号', max_length=50)
    password = forms.CharField(label='登录密码', widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': '账号或密码不正确，请重新输入。',
        'inactive': '该账号已停用，请联系管理员。',
    }


class UserForm(BootstrapFormMixin, forms.ModelForm):
    """员工账号新增 / 编辑。"""

    password = forms.CharField(
        label='登录密码', widget=forms.PasswordInput(render_value=True), required=False,
        help_text='新增时必填；编辑时留空表示不修改密码。'
    )

    class Meta:
        model = User
        fields = ['username', 'real_name', 'role', 'employee_no', 'phone', 'address',
                  'entry_date', 'is_active']
        labels = {
            'username': '登录账号',
            'real_name': '姓名',
            'role': '角色',
            'employee_no': '工号',
            'phone': '手机号',
            'address': '住址',
            'entry_date': '入职日期',
            'is_active': '在职状态',
        }
        widgets = {'entry_date': forms.DateInput(attrs={'type': 'date'})}

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.instance.pk and not password:
            raise forms.ValidationError('新增员工必须设置登录密码。')
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class ResetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    """管理员重置员工密码。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = '新密码'
        self.fields['new_password2'].label = '确认新密码'

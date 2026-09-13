"""账号与权限视图。"""

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.forms import LoginForm, ResetPasswordForm, UserForm
from apps.accounts.models import User
from apps.core.mixins import manager_required
from apps.core.models import OperationLog
from apps.core.utils import write_log


def login_view(request):
    """系统登录。"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        write_log(request, 'system', '登录系统', f'{user.real_name or user.username} 登录成功')
        messages.success(request, f'欢迎回来，{user.real_name or user.username}！')
        return redirect(request.GET.get('next') or 'core:dashboard')

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """退出登录。"""
    if request.user.is_authenticated:
        write_log(request, 'system', '退出系统', f'{request.user.username} 退出登录')
    logout(request)
    messages.info(request, '您已安全退出系统。')
    return redirect('accounts:login')


@login_required
def profile(request):
    """个人中心 + 修改密码。"""
    user = request.user
    if request.method == 'POST':
        old = request.POST.get('old_password', '')
        new1 = request.POST.get('new_password1', '')
        new2 = request.POST.get('new_password2', '')
        if not user.check_password(old):
            messages.error(request, '原密码不正确。')
        elif new1 != new2:
            messages.error(request, '两次输入的新密码不一致。')
        elif len(new1) < 6:
            messages.error(request, '新密码长度不能少于 6 位。')
        else:
            user.set_password(new1)
            user.save()
            update_session_auth_hash(request, user)
            write_log(request, 'account', '修改密码', '个人中心修改登录密码')
            messages.success(request, '密码修改成功。')
        return redirect('accounts:profile')

    my_logs = OperationLog.objects.filter(user=user)[:10]
    return render(request, 'accounts/profile.html', {'my_logs': my_logs})


@login_required
@manager_required
def user_list(request):
    """员工列表。"""
    keyword = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    qs = User.objects.all().order_by('id')
    if keyword:
        qs = qs.filter(Q(username__icontains=keyword) | Q(real_name__icontains=keyword)
                       | Q(phone__icontains=keyword) | Q(employee_no__icontains=keyword))
    if role:
        qs = qs.filter(role=role)

    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'accounts/user_list.html', {
        'page_obj': page_obj,
        'keyword': keyword,
        'role': role,
        'role_choices': User.ROLE_CHOICES,
        'query_params': f'q={keyword}&role={role}',
    })


@login_required
@manager_required
def user_create(request):
    """新增员工。"""
    form = UserForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        write_log(request, 'account', '新增员工', f'新增员工账号：{user.username}（{user.role_name}）')
        messages.success(request, f'员工【{user.real_name or user.username}】创建成功。')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': '新增员工'})


@login_required
@manager_required
def user_update(request, pk):
    """编辑员工。"""
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        write_log(request, 'account', '修改员工', f'修改员工信息：{user.username}')
        messages.success(request, '员工信息已更新。')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': '编辑员工', 'object': user})


@login_required
@manager_required
def user_toggle(request, pk):
    """启用 / 停用员工。"""
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, '不能停用自己的账号。')
    else:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        write_log(request, 'account', '变更状态',
                  f'{"启用" if user.is_active else "停用"}员工账号：{user.username}')
        messages.success(request, f'已{"启用" if user.is_active else "停用"}账号 {user.username}。')
    return redirect('accounts:user_list')


@login_required
@manager_required
def user_reset_password(request, pk):
    """重置员工密码。"""
    user = get_object_or_404(User, pk=pk)
    form = ResetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        write_log(request, 'account', '重置密码', f'重置员工密码：{user.username}')
        messages.success(request, f'已重置 {user.username} 的登录密码。')
        return redirect('accounts:user_list')
    return render(request, 'accounts/reset_password.html', {'form': form, 'object': user})


@login_required
@manager_required
def log_list(request):
    """操作日志。"""
    keyword = request.GET.get('q', '').strip()
    module = request.GET.get('module', '')
    qs = OperationLog.objects.select_related('user').all()
    if keyword:
        qs = qs.filter(Q(detail__icontains=keyword) | Q(action__icontains=keyword)
                       | Q(user__username__icontains=keyword))
    if module:
        qs = qs.filter(module=module)

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'accounts/log_list.html', {
        'page_obj': page_obj,
        'keyword': keyword,
        'module': module,
        'module_choices': OperationLog.MODULE_CHOICES,
        'query_params': f'q={keyword}&module={module}',
    })

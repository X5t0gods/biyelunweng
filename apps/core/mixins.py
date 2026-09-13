"""视图层通用权限控制。"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect


class ManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """店长 / 管理员权限。"""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.is_manager)

    def handle_no_permission(self):
        messages.error(self.request, '您没有该功能的访问权限，请联系店长或管理员。')
        return redirect('core:dashboard')


class StockRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """库管 / 采购权限。"""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.can_manage_stock)

    def handle_no_permission(self):
        messages.error(self.request, '您没有该功能的访问权限，请联系店长或管理员。')
        return redirect('core:dashboard')


def manager_required(view_func):
    """函数视图版本的店长权限装饰器。"""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_superuser or request.user.is_manager):
            messages.error(request, '您没有该功能的访问权限，请联系店长或管理员。')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper


def stock_required(view_func):
    """函数视图版本的库管权限装饰器。"""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_superuser or request.user.can_manage_stock):
            messages.error(request, '您没有该功能的访问权限，请联系店长或管理员。')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper

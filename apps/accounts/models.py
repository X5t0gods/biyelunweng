"""用户 / 员工账号模型。"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """扩展 Django 内置用户，增加员工角色、手机号等超市业务字段。"""

    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_CASHIER = 'cashier'
    ROLE_STOCK = 'stock'

    ROLE_CHOICES = (
        (ROLE_ADMIN, '系统管理员'),
        (ROLE_MANAGER, '店长'),
        (ROLE_CASHIER, '收银员'),
        (ROLE_STOCK, '库管/采购员'),
    )

    real_name = models.CharField('姓名', max_length=50, blank=True, default='')
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)
    phone = models.CharField('手机号', max_length=20, blank=True, default='')
    employee_no = models.CharField('工号', max_length=20, unique=True, null=True, blank=True)
    address = models.CharField('住址', max_length=200, blank=True, default='')
    entry_date = models.DateField('入职日期', null=True, blank=True)
    is_active = models.BooleanField('在职状态', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '员工账号'
        verbose_name_plural = '员工账号'
        ordering = ['id']

    def __str__(self):
        return self.real_name or self.username

    @property
    def role_name(self):
        return self.get_role_display()

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_manager(self):
        """店长及以上拥有经营数据查看与审核权限。"""
        return self.role in (self.ROLE_ADMIN, self.ROLE_MANAGER) or self.is_superuser

    @property
    def can_manage_stock(self):
        """采购、入库、盘点权限。"""
        return self.role in (self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_STOCK) or self.is_superuser

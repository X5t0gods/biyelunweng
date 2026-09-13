"""采购进货模型。"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.utils import generate_order_no
from apps.goods.models import Product


class PurchaseOrder(models.Model):
    """采购单（入库单）。"""

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '待入库'),
        (STATUS_CONFIRMED, '已入库'),
        (STATUS_CANCELED, '已取消'),
    )

    order_no = models.CharField('采购单号', max_length=30, unique=True)
    supplier = models.ForeignKey(
        'goods.Supplier', on_delete=models.PROTECT, verbose_name='供应商', related_name='purchase_orders'
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='经办人',
        related_name='purchase_orders'
    )
    total_amount = models.DecimalField('采购总额', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    remark = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', default=timezone.now)
    confirmed_at = models.DateTimeField('入库时间', null=True, blank=True)

    class Meta:
        verbose_name = '采购单'
        verbose_name_plural = '采购单'
        ordering = ['-created_at']

    def __str__(self):
        return self.order_no

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    def recalc_total(self):
        total = sum(float(item.subtotal) for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        return self.total_amount


class PurchaseItem(models.Model):
    """采购明细。"""

    order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, verbose_name='采购单', related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, verbose_name='商品', related_name='purchase_items'
    )
    quantity = models.PositiveIntegerField('采购数量', default=1)
    price = models.DecimalField('采购单价', max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = '采购明细'
        verbose_name_plural = '采购明细'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)

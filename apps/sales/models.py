"""销售（POS 收银）与退货模型。"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Sale(models.Model):
    """销售订单。"""

    PAY_CASH = 'cash'
    PAY_WECHAT = 'wechat'
    PAY_ALIPAY = 'alipay'
    PAY_CARD = 'card'
    PAY_BALANCE = 'balance'
    PAY_CHOICES = (
        (PAY_CASH, '现金'),
        (PAY_WECHAT, '微信'),
        (PAY_ALIPAY, '支付宝'),
        (PAY_CARD, '银行卡'),
        (PAY_BALANCE, '会员余额'),
    )

    STATUS_DONE = 'done'
    STATUS_RETURNED = 'returned'
    STATUS_VOID = 'void'
    STATUS_CHOICES = (
        (STATUS_DONE, '已完成'),
        (STATUS_RETURNED, '已退货'),
        (STATUS_VOID, '已作废'),
    )

    order_no = models.CharField('销售单号', max_length=30, unique=True)
    member = models.ForeignKey(
        'member.Member', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='会员', related_name='sales'
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='收银员', related_name='sales'
    )
    total_amount = models.DecimalField('应收金额', max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField('优惠金额', max_digits=12, decimal_places=2, default=0)
    actual_amount = models.DecimalField('实收金额', max_digits=12, decimal_places=2, default=0)
    cost_amount = models.DecimalField('成本金额', max_digits=12, decimal_places=2, default=0)
    pay_method = models.CharField('支付方式', max_length=20, choices=PAY_CHOICES, default=PAY_CASH)
    points_earned = models.IntegerField('本次积分', default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_DONE)
    remark = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('销售时间', default=timezone.now)

    class Meta:
        verbose_name = '销售单'
        verbose_name_plural = '销售单'
        ordering = ['-created_at']

    def __str__(self):
        return self.order_no

    @property
    def profit(self):
        """毛利 = 实收 - 成本。"""
        return self.actual_amount - self.cost_amount

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())


class SaleItem(models.Model):
    """销售明细。"""

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, verbose_name='销售单', related_name='items')
    product = models.ForeignKey(
        'goods.Product', on_delete=models.PROTECT, verbose_name='商品', related_name='sale_items'
    )
    product_name = models.CharField('商品名称', max_length=100, blank=True, default='')
    quantity = models.PositiveIntegerField('数量', default=1)
    price = models.DecimalField('销售单价', max_digits=10, decimal_places=2, default=0)
    cost_price = models.DecimalField('成本单价', max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = '销售明细'
        verbose_name_plural = '销售明细'
        ordering = ['id']

    def __str__(self):
        return f'{self.product_name or self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        if not self.product_name:
            self.product_name = self.product.name
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)


class SaleReturn(models.Model):
    """销售退货单。"""

    return_no = models.CharField('退货单号', max_length=30, unique=True)
    sale = models.ForeignKey(
        Sale, on_delete=models.PROTECT, verbose_name='原销售单', related_name='returns'
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='操作人',
        related_name='sale_returns'
    )
    amount = models.DecimalField('退款金额', max_digits=12, decimal_places=2, default=0)
    reason = models.CharField('退货原因', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('退货时间', default=timezone.now)

    class Meta:
        verbose_name = '销售退货单'
        verbose_name_plural = '销售退货单'
        ordering = ['-created_at']

    def __str__(self):
        return self.return_no


class SaleReturnItem(models.Model):
    """退货明细。"""

    sale_return = models.ForeignKey(
        SaleReturn, on_delete=models.CASCADE, verbose_name='退货单', related_name='items'
    )
    product = models.ForeignKey(
        'goods.Product', on_delete=models.PROTECT, verbose_name='商品', related_name='return_items'
    )
    quantity = models.PositiveIntegerField('退货数量', default=1)
    price = models.DecimalField('退款单价', max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计', max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = '退货明细'
        verbose_name_plural = '退货明细'
        ordering = ['id']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)

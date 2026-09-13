"""系统公共模型：操作日志、库存流水。"""

from django.conf import settings
from django.db import models


class OperationLog(models.Model):
    """操作日志：记录关键业务动作，便于审计与追溯。"""

    MODULE_CHOICES = (
        ('account', '账号管理'),
        ('goods', '商品管理'),
        ('purchase', '采购管理'),
        ('sales', '销售管理'),
        ('member', '会员管理'),
        ('stock', '库存管理'),
        ('report', '统计报表'),
        ('system', '系统'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='操作人', related_name='operation_logs'
    )
    module = models.CharField('所属模块', max_length=20, choices=MODULE_CHOICES, default='system')
    action = models.CharField('操作类型', max_length=50, default='')
    detail = models.TextField('操作详情', blank=True, default='')
    ip = models.GenericIPAddressField('IP 地址', null=True, blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_module_display()}] {self.action}'


class StockLog(models.Model):
    """库存流水：任何引起库存变化的操作都要留痕。"""

    TYPE_PURCHASE = 'purchase'
    TYPE_SALE = 'sale'
    TYPE_RETURN = 'return'
    TYPE_CHECK = 'check'
    TYPE_LOSS = 'loss'
    TYPE_MANUAL = 'manual'

    TYPE_CHOICES = (
        (TYPE_PURCHASE, '采购入库'),
        (TYPE_SALE, '销售出库'),
        (TYPE_RETURN, '退货入库'),
        (TYPE_CHECK, '库存盘点'),
        (TYPE_LOSS, '报损'),
        (TYPE_MANUAL, '手动调整'),
    )

    product = models.ForeignKey(
        'goods.Product', on_delete=models.CASCADE, verbose_name='商品', related_name='stock_logs'
    )
    change_type = models.CharField('变动类型', max_length=20, choices=TYPE_CHOICES, default=TYPE_MANUAL)
    quantity = models.IntegerField('变动数量', help_text='正数表示入库，负数表示出库')
    stock_before = models.IntegerField('变动前库存', default=0)
    stock_after = models.IntegerField('变动后库存', default=0)
    related_no = models.CharField('关联单号', max_length=50, blank=True, default='')
    remark = models.CharField('备注', max_length=200, blank=True, default='')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='操作人'
    )
    created_at = models.DateTimeField('变动时间', auto_now_add=True)

    class Meta:
        verbose_name = '库存流水'
        verbose_name_plural = '库存流水'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} {self.quantity:+d}'

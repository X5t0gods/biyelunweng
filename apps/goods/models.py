"""商品、分类、供应商模型。"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import StockLog


class Supplier(models.Model):
    """供应商 / 供货商。"""

    name = models.CharField('供应商名称', max_length=100, unique=True)
    contact = models.CharField('联系人', max_length=50, blank=True, default='')
    phone = models.CharField('联系电话', max_length=30, blank=True, default='')
    address = models.CharField('地址', max_length=200, blank=True, default='')
    bank_account = models.CharField('收款账号', max_length=60, blank=True, default='')
    remark = models.TextField('备注', blank=True, default='')
    is_active = models.BooleanField('合作中', default=True)
    created_at = models.DateTimeField('创建时间', default=timezone.now)

    class Meta:
        verbose_name = '供应商'
        verbose_name_plural = '供应商'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Category(models.Model):
    """商品分类。"""

    name = models.CharField('分类名称', max_length=50, unique=True)
    code = models.CharField('分类编码', max_length=20, unique=True, null=True, blank=True)
    description = models.CharField('描述', max_length=200, blank=True, default='')
    sort = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', default=timezone.now)

    class Meta:
        verbose_name = '商品分类'
        verbose_name_plural = '商品分类'
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class Product(models.Model):
    """商品（SKU）。"""

    STATUS_ON = 'on'
    STATUS_OFF = 'off'
    STATUS_CHOICES = (
        (STATUS_ON, '在售'),
        (STATUS_OFF, '已下架'),
    )

    name = models.CharField('商品名称', max_length=100)
    barcode = models.CharField('条形码', max_length=50, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, verbose_name='所属分类', related_name='products'
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='默认供应商', related_name='products'
    )
    spec = models.CharField('规格', max_length=50, blank=True, default='')
    unit = models.CharField('单位', max_length=10, default='件')
    purchase_price = models.DecimalField('进价(元)', max_digits=10, decimal_places=2, default=0)
    sale_price = models.DecimalField('售价(元)', max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField('当前库存', default=0)
    safety_stock = models.IntegerField('安全库存', default=10)
    shelf_life_days = models.IntegerField('保质期(天)', null=True, blank=True)
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default=STATUS_ON)
    remark = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', default=timezone.now)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name}({self.barcode})'

    @property
    def profit(self):
        """单件毛利。"""
        return self.sale_price - self.purchase_price

    @property
    def profit_rate(self):
        """毛利率(%)。"""
        if self.sale_price:
            return round(float(self.profit) / float(self.sale_price) * 100, 2)
        return 0

    @property
    def is_low_stock(self):
        """是否库存预警。"""
        return self.stock <= self.safety_stock

    @property
    def stock_value(self):
        """库存金额（按进价）。"""
        return self.purchase_price * self.stock

    @property
    def suggest_purchase(self):
        """建议补货量：补足到安全库存的 3 倍，已充足则为 0。"""
        target = self.safety_stock * 3
        return max(0, target - self.stock)

    def change_stock(self, quantity, change_type=StockLog.TYPE_MANUAL, operator=None,
                     related_no='', remark=''):
        """统一改库存入口，同时写库存流水。"""
        before = self.stock
        self.stock = before + quantity
        if self.stock < 0:
            raise ValueError(f'商品【{self.name}】库存不足，当前库存 {before}')
        self.save(update_fields=['stock', 'updated_at'])
        StockLog.objects.create(
            product=self,
            change_type=change_type,
            quantity=quantity,
            stock_before=before,
            stock_after=self.stock,
            related_no=related_no,
            remark=remark,
            operator=operator,
        )
        return self.stock

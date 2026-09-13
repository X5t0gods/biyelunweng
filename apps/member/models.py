"""会员模型。"""

from django.db import models
from django.utils import timezone


class MemberLevel(models.Model):
    """会员等级：不同等级享有不同折扣与积分倍率。"""

    name = models.CharField('等级名称', max_length=30, unique=True)
    discount = models.DecimalField(
        '折扣率', max_digits=4, decimal_places=2, default=1.00,
        help_text='0.95 表示 95 折，1.00 表示无折扣'
    )
    point_rate = models.DecimalField(
        '积分倍率', max_digits=4, decimal_places=2, default=1.00,
        help_text='每消费 1 元获得 1 积分，倍率为 2 则获得 2 积分'
    )
    min_points = models.IntegerField('升级所需积分', default=0)
    remark = models.CharField('备注', max_length=100, blank=True, default='')

    class Meta:
        verbose_name = '会员等级'
        verbose_name_plural = '会员等级'
        ordering = ['min_points']

    def __str__(self):
        return self.name


class Member(models.Model):
    """超市会员。"""

    GENDER_CHOICES = (('M', '男'), ('F', '女'), ('N', '未知'))

    card_no = models.CharField('会员卡号', max_length=30, unique=True)
    name = models.CharField('姓名', max_length=50)
    phone = models.CharField('手机号', max_length=20, unique=True)
    gender = models.CharField('性别', max_length=2, choices=GENDER_CHOICES, default='N')
    birthday = models.DateField('生日', null=True, blank=True)
    level = models.ForeignKey(
        MemberLevel, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='会员等级', related_name='members'
    )
    points = models.IntegerField('积分余额', default=0)
    total_points = models.IntegerField('累计积分', default=0)
    balance = models.DecimalField('储值余额(元)', max_digits=10, decimal_places=2, default=0)
    total_spend = models.DecimalField('累计消费(元)', max_digits=12, decimal_places=2, default=0)
    address = models.CharField('住址', max_length=200, blank=True, default='')
    is_active = models.BooleanField('状态', default=True)
    join_date = models.DateTimeField('入会时间', default=timezone.now)
    remark = models.CharField('备注', max_length=200, blank=True, default='')

    class Meta:
        verbose_name = '会员'
        verbose_name_plural = '会员'
        ordering = ['-join_date']

    def __str__(self):
        return f'{self.name}({self.card_no})'

    @property
    def level_name(self):
        return self.level.name if self.level else '普通顾客'

    @property
    def discount(self):
        return float(self.level.discount) if self.level else 1.0

    @property
    def point_rate(self):
        return float(self.level.point_rate) if self.level else 1.0

    def refresh_level(self):
        """按累计积分自动匹配会员等级（取满足门槛的最高等级）。"""
        level = MemberLevel.objects.filter(min_points__lte=self.total_points).order_by('-min_points').first()
        if level and level != self.level:
            self.level = level
            self.save(update_fields=['level'])
        return self.level

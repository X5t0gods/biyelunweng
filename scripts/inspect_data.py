"""数据体检：检查 MySQL 连接、数据量与演示数据的真实度。

运行：python scripts/inspect_data.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.db.models import Count, Sum  # noqa: E402

from apps.core.models import StockLog  # noqa: E402
from apps.goods.models import Product  # noqa: E402
from apps.member.models import Member  # noqa: E402
from apps.sales.models import Sale, SaleReturn  # noqa: E402


def line(title):
    print(f'\n{"=" * 46}\n{title}\n{"=" * 46}')


def main():
    line('数据库')
    print('后端     :', connection.vendor)
    print('库名     :', connection.settings_dict['NAME'])
    print('地址     :', f"{connection.settings_dict['HOST']}:{connection.settings_dict['PORT']}")
    print('字符集   :', connection.settings_dict['OPTIONS'].get('charset'))

    line('数据量')
    print('商品       :', Product.objects.count())
    print('会员       :', Member.objects.count())
    print('销售单     :', Sale.objects.count())
    print('退货单     :', SaleReturn.objects.count())
    print('库存流水   :', StockLog.objects.count())
    print('累计销售额 : ¥', Sale.objects.aggregate(t=Sum('actual_amount'))['t'] or 0)

    line('真实度抽查 — 商品与供应商匹配')
    for p in Product.objects.select_related('supplier', 'category')[:5]:
        print(f'  {p.name:<16} {p.barcode}  {p.category.name:<6} <- {p.supplier.name}')

    line('真实度抽查 — 会员')
    for m in Member.objects.select_related('level')[:3]:
        print(f'  {m.name:<6} {m.phone}  {m.level_name:<6} {m.address}')

    line('会员等级分布')
    for row in Member.objects.values('level__name').annotate(c=Count('id')).order_by('-c'):
        print(f"  {row['level__name']:<8} {row['c']} 人")

    line('支付方式分布')
    for row in Sale.objects.values('pay_method').annotate(c=Count('id')).order_by('-c'):
        print(f"  {row['pay_method']:<10} {row['c']} 单")

    line('营业时段分布（社区超市典型双高峰）')
    rows = (Sale.objects.extra({'h': 'HOUR(created_at)'})
            .values('h').annotate(c=Count('id')).order_by('h'))
    for row in rows:
        bar = '#' * max(1, row['c'] // 2)
        print(f"  {row['h']:>2} 时  {bar} {row['c']}")

    line('库存预警')
    low = [p for p in Product.objects.all() if p.is_low_stock]
    print(f'  预警商品 {len(low)} 个')
    for p in low[:5]:
        print(f'  {p.name:<16} 库存 {p.stock}{p.unit}，建议补货 {p.suggest_purchase}{p.unit}')


if __name__ == '__main__':
    main()

"""冒烟测试：用 Django 测试客户端访问所有主要页面，检查是否正常返回 200。

运行：python scripts/smoke_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from apps.goods.models import Product  # noqa: E402
from apps.purchase.models import PurchaseOrder  # noqa: E402
from apps.sales.models import Sale  # noqa: E402
from apps.member.models import Member  # noqa: E402

URLS = [
    '/',
    '/accounts/profile/',
    '/accounts/users/',
    '/accounts/users/create/',
    '/accounts/logs/',
    '/goods/categories/',
    '/goods/suppliers/',
    '/goods/products/',
    '/goods/products/create/',
    '/goods/stock/',
    '/goods/stock/logs/',
    '/goods/stock/alert/',
    '/purchase/',
    '/purchase/create/',
    '/sales/pos/',
    '/sales/',
    '/sales/returns/',
    '/sales/returns/create/',
    '/member/levels/',
    '/member/',
    '/member/create/',
    '/report/sales/',
    '/report/profit/',
    '/report/goods/',
    '/report/stock/',
    '/report/sales/export/',
]


def main():
    client = Client()
    if not client.login(username='admin', password='******'):
        print('登录失败，请先执行 python manage.py init_data')
        return 1

    product = Product.objects.first()
    order = PurchaseOrder.objects.first()
    sale = Sale.objects.first()
    member = Member.objects.first()
    if product:
        URLS.append(f'/goods/products/{product.pk}/')
        URLS.append(f'/goods/products/{product.pk}/edit/')
        URLS.append(f'/goods/stock/{product.pk}/adjust/')
        URLS.append(f'/goods/api/product/?code={product.barcode}')
    if order:
        URLS.append(f'/purchase/{order.pk}/')
    if sale:
        URLS.append(f'/sales/{sale.pk}/')
    if member:
        URLS.append(f'/member/{member.pk}/')
        URLS.append(f'/member/{member.pk}/edit/')
        URLS.append(f'/member/{member.pk}/recharge/')

    failed = []
    for url in URLS:
        resp = client.get(url)
        status = resp.status_code
        flag = 'OK ' if status in (200, 302) else 'ERR'
        if status not in (200, 302):
            failed.append((url, status))
        print(f'[{flag}] {status} {url}')

    if failed:
        print('\n以下页面异常：')
        for url, status in failed:
            print(f'  {status} {url}')
        return 1
    print('\n全部页面访问正常。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""菜单高亮测试：验证侧边栏的高亮项与当前所在页面一致。

背景：早期用 `request.resolver_match.namespace == 'goods'` 判断高亮，
导致访问「库存查询」「供应商」时高亮的却是「商品管理」（同属 goods 命名空间）。
本脚本逐个访问页面，解析渲染结果里带 active 的菜单项，与预期比对。

运行：python scripts/nav_test.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from apps.goods.models import Product  # noqa: E402
from apps.member.models import Member  # noqa: E402
from apps.purchase.models import PurchaseOrder  # noqa: E402
from apps.sales.models import Sale  # noqa: E402

# 匹配带 active 的菜单链接（菜单里 <a> 的 href 与 class 可能被模板换行分隔）
ACTIVE_RE = re.compile(r'<a\s+href="[^"]*"\s+class="side-link\s+active"[^>]*>(.*?)</a>', re.S)
TAG_RE = re.compile(r'<[^>]+>')

# (url name, 动态参数, 期望高亮项)
CASES = [
    ('core:dashboard', None, '系统首页'),
    ('sales:pos', None, '前台收银'),
    ('sales:sale_list', None, '销售订单'),
    ('sales:return_list', None, '销售退货'),
    ('goods:product_list', None, '商品管理'),
    ('goods:category_list', None, '商品管理'),
    ('goods:stock_list', None, '库存查询'),
    ('goods:stock_log_list', None, '库存查询'),
    ('goods:stock_alert', None, '库存查询'),
    ('purchase:order_list', None, '采购进货'),
    ('goods:supplier_list', None, '供应商'),
    ('member:member_list', None, '会员管理'),
    ('member:level_list', None, '会员管理'),
    ('report:sales_report', None, '统计报表'),
    ('report:profit_report', None, '统计报表'),
    ('report:goods_report', None, '统计报表'),
    ('report:stock_report', None, '统计报表'),
    ('accounts:user_list', None, '员工账号'),
    ('accounts:user_create', None, '员工账号'),
    ('accounts:log_list', None, '操作日志'),
]

passed = failed = 0


def active_labels(html):
    """提取页面中所有处于高亮状态的菜单项文字（桌面侧栏 + 移动抽屉会重复，去重）。"""
    labels = []
    for raw in ACTIVE_RE.findall(html):
        text = TAG_RE.sub('', raw).strip()
        if text and text not in labels:
            labels.append(text)
    return labels


def check(name, url, expected, client):
    global passed, failed
    resp = client.get(url)
    if resp.status_code != 200:
        failed += 1
        print(f'  [失败] {name} -> HTTP {resp.status_code}')
        return
    labels = active_labels(resp.content.decode('utf-8'))
    if labels == [expected]:
        passed += 1
        print(f'  [通过] {name:<28} 高亮「{expected}」')
    else:
        failed += 1
        shown = '、'.join(labels) if labels else '（无高亮）'
        print(f'  [失败] {name:<28} 期望「{expected}」实际「{shown}」')


def main():
    global passed, failed

    c = Client()
    assert c.login(username='admin', password='******'), '登录失败，请先执行 init_data'

    print('【固定页面高亮】')
    for name, _args, expected in CASES:
        check(name, reverse(name), expected, c)

    print('\n【详情页高亮】')
    dynamic = []
    if Product.objects.exists():
        dynamic.append(('goods:product_detail', {'pk': Product.objects.first().pk}, '商品管理'))
    if PurchaseOrder.objects.exists():
        dynamic.append(('purchase:order_detail', {'pk': PurchaseOrder.objects.first().pk}, '采购进货'))
    if Sale.objects.exists():
        dynamic.append(('sales:sale_detail', {'pk': Sale.objects.first().pk}, '销售订单'))
    if Member.objects.exists():
        dynamic.append(('member:member_detail', {'pk': Member.objects.first().pk}, '会员管理'))
    for name, args, expected in dynamic:
        check(name, reverse(name, kwargs=args), expected, c)

    print('\n【回归：其他角色登录也能正常渲染菜单】')
    for account, role in [('cashier', '收银员'), ('stocker', '库管'), ('manager', '店长')]:
        cc = Client()
        if not cc.login(username=account, password='******'):
            failed += 1
            print(f'  [失败] {account} 登录失败')
            continue
        for url in ['/', '/sales/pos/', '/goods/stock/', '/goods/suppliers/']:
            resp = cc.get(url)
            if resp.status_code != 200:
                failed += 1
                print(f'  [失败] {role} 访问 {url} -> HTTP {resp.status_code}')
            else:
                passed += 1
        print(f'  [通过] {role}（{account}）菜单渲染正常')

    print(f'\n===== 结果：通过 {passed} 项，失败 {failed} 项 =====')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

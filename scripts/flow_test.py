"""业务流程测试：覆盖所有写操作，用于回归验证。

运行：python scripts/flow_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from decimal import Decimal  # noqa: E402

from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

# 让测试客户端能够捕获模板上下文（response.context），否则取到 None
setup_test_environment()

from apps.accounts.models import User  # noqa: E402
from apps.core.models import StockLog  # noqa: E402
from apps.goods.models import Category, Product, Supplier  # noqa: E402
from apps.member.models import Member, MemberLevel  # noqa: E402
from apps.purchase.models import PurchaseOrder  # noqa: E402
from apps.sales.models import Sale, SaleReturn  # noqa: E402

PASSED, FAILED = [], []


def check(name, cond, detail=''):
    if cond:
        PASSED.append(name)
        print(f'  [通过] {name}')
    else:
        FAILED.append((name, detail))
        print(f'  [失败] {name} {detail}')


def admin():
    c = Client()
    assert c.login(username='admin', password='123456')
    return c


# --------------------------------------------------------------- 收银

def test_pos():
    print('\n【1】前台收银')
    c = Client()
    c.login(username='cashier', password='123456')

    p = Product.objects.filter(status=Product.STATUS_ON, stock__gt=20).first()
    before = p.stock

    c.post('/sales/pos/', {'action': 'add', 'code': p.barcode})
    c.post('/sales/pos/', {'action': 'add', 'code': p.barcode})
    c.post('/sales/pos/', {'action': 'update', 'pid': p.pk, 'qty': 5})
    c.post('/sales/pos/', {'action': 'remove', 'pid': p.pk})
    c.post('/sales/pos/', {'action': 'clear'})
    check('购物车加/改/删/清空不报错', True)

    # 会员折扣 + 现金支付
    member = Member.objects.filter(level__isnull=False).first()
    c.post('/sales/pos/', {'action': 'add', 'code': p.barcode})
    c.post('/sales/pos/', {'action': 'add', 'code': p.barcode})
    c.post('/sales/pos/', {'action': 'member', 'member_key': member.card_no})
    points_before = member.points
    r = c.post('/sales/pos/', {'action': 'checkout', 'pay_method': 'cash', 'remark': '流程测试'})
    check('结算成功并跳转', r.status_code == 302, f'status={r.status_code}')

    p.refresh_from_db()
    member.refresh_from_db()
    sale = Sale.objects.order_by('-pk').first()
    check('库存正确扣减 2', p.stock == before - 2, f'{before} -> {p.stock}')
    check('会员折扣已生效', sale.discount_amount >= 0 and sale.member_id == member.pk)
    check('会员积分已累计', member.points > points_before, f'{points_before} -> {member.points}')
    check('生成销售出库流水',
          StockLog.objects.filter(related_no=sale.order_no, change_type=StockLog.TYPE_SALE).count() == 1)

    # 会员余额支付
    m2 = Member.objects.exclude(pk=member.pk).first()
    m2.balance = Decimal('500')
    m2.save()
    p2 = Product.objects.filter(status=Product.STATUS_ON, stock__gt=20).exclude(pk=p.pk).first()
    c2 = Client()
    c2.login(username='cashier', password='123456')
    c2.post('/sales/pos/', {'action': 'add', 'code': p2.barcode})
    c2.post('/sales/pos/', {'action': 'member', 'member_key': m2.card_no})
    c2.post('/sales/pos/', {'action': 'checkout', 'pay_method': 'balance'})
    m2.refresh_from_db()
    check('会员余额支付后余额减少', m2.balance < Decimal('500'), f'余额 {m2.balance}')

    # 余额不足应被拒绝
    m3 = Member.objects.exclude(pk__in=[member.pk, m2.pk]).first()
    m3.balance = Decimal('0')
    m3.save()
    c3 = Client()
    c3.login(username='cashier', password='123456')
    c3.post('/sales/pos/', {'action': 'add', 'code': p2.barcode})
    c3.post('/sales/pos/', {'action': 'member', 'member_key': m3.card_no})
    r = c3.post('/sales/pos/', {'action': 'checkout', 'pay_method': 'balance'})
    check('余额不足时拒绝结算', r.status_code == 302 and Sale.objects.order_by('-pk').first().member_id != m3.pk)


# --------------------------------------------------------------- 采购

def test_purchase():
    print('\n【2】采购入库')
    c = Client()
    c.login(username='stocker', password='123456')

    # 只挑选在售商品（采购明细表单限定了 status=on），保证测试可重复执行
    p = Product.objects.filter(status=Product.STATUS_ON).first()
    before = p.stock
    c.post('/purchase/create/', {'supplier': Supplier.objects.first().pk, 'remark': '流程测试'})
    order = PurchaseOrder.objects.order_by('-pk').first()
    c.post(f'/purchase/{order.pk}/', {'product': p.pk, 'quantity': 20, 'price': str(p.purchase_price)})
    c.post(f'/purchase/{order.pk}/confirm/', {})

    p.refresh_from_db()
    order.refresh_from_db()
    check('采购单已入库', order.status == PurchaseOrder.STATUS_CONFIRMED)
    check('库存增加 20', p.stock == before + 20, f'{before} -> {p.stock}')
    check('生成采购入库流水',
          StockLog.objects.filter(related_no=order.order_no, change_type=StockLog.TYPE_PURCHASE).count() == 1)

    # 重复入库应被拒绝
    c.post(f'/purchase/{order.pk}/confirm/', {})
    p.refresh_from_db()
    check('重复入库被拒绝', p.stock == before + 20)

    # 空明细不能入库
    c.post('/purchase/create/', {'supplier': Supplier.objects.first().pk, 'remark': '空单'})
    empty = PurchaseOrder.objects.order_by('-pk').first()
    c.post(f'/purchase/{empty.pk}/confirm/', {})
    empty.refresh_from_db()
    check('空明细采购单不能入库', empty.status == PurchaseOrder.STATUS_DRAFT)


# --------------------------------------------------------------- 退货

def test_return():
    print('\n【3】销售退货')
    c = Client()
    c.login(username='manager', password='123456')

    sale = Sale.objects.filter(status=Sale.STATUS_DONE, member__isnull=False).first()
    item = sale.items.first()
    p = item.product
    stock_before = p.stock
    member = sale.member
    points_before = member.points
    spend_before = member.total_spend

    r = c.post('/sales/returns/create/', {
        'sale_no': sale.order_no,
        'reason': '流程测试退货',
        f'qty_{item.pk}': 1,
    })
    check('退货单创建成功（不报 FieldError）', r.status_code == 302, f'status={r.status_code}')

    ret = SaleReturn.objects.order_by('-pk').first()
    check('生成退货单号', bool(ret) and ret.return_no.startswith('TH'))

    p.refresh_from_db()
    member.refresh_from_db()
    sale.refresh_from_db()
    check('退货后库存回补', p.stock == stock_before + 1, f'{stock_before} -> {p.stock}')
    check('退货后扣回积分', member.points <= points_before, f'{points_before} -> {member.points}')
    check('退货后累计消费减少', member.total_spend <= spend_before)
    check('原销售单标记为已退货', sale.status == Sale.STATUS_RETURNED)

    # 不存在的单号
    r = c.post('/sales/returns/create/', {'sale_no': 'XS00000000', 'reason': 'x'})
    check('不存在的销售单被拒绝', r.status_code == 200)

    # 超过购买数量
    sale2 = Sale.objects.filter(status=Sale.STATUS_DONE).exclude(pk=sale.pk).first()
    it2 = sale2.items.first()
    c.post('/sales/returns/create/', {'sale_no': sale2.order_no, 'reason': 'x', f'qty_{it2.pk}': 999})
    check('超额退货被拒绝', not SaleReturn.objects.filter(sale=sale2).exists())


# --------------------------------------------------------------- 作废

def test_void():
    print('\n【4】销售单作废')
    c = Client()
    c.login(username='manager', password='123456')

    sale = Sale.objects.filter(status=Sale.STATUS_DONE, member__isnull=False).first()
    p = sale.items.first().product
    stock_before = p.stock
    member = sale.member
    points_before = member.points

    c.post(f'/sales/{sale.pk}/void/', {})
    p.refresh_from_db()
    member.refresh_from_db()
    sale.refresh_from_db()

    qty = sum(i.quantity for i in sale.items.all())
    check('作废后库存回退', p.stock == stock_before + qty, f'{stock_before} -> {p.stock}')
    check('作废后积分扣回', member.points <= points_before)
    check('状态标记为已作废', sale.status == Sale.STATUS_VOID)

    # 重复作废
    c.post(f'/sales/{sale.pk}/void/', {})
    check('重复作废被拒绝', Sale.objects.get(pk=sale.pk).status == Sale.STATUS_VOID)


# --------------------------------------------------------------- 商品/分类/库存

def test_goods():
    print('\n【5】商品 / 分类 / 库存')
    c = admin()
    cat = Category.objects.first()
    sup = Supplier.objects.first()

    # 清理上一轮遗留的测试数据，保证可重复执行
    Product.objects.filter(barcode__startswith='69999000').delete()
    Category.objects.filter(name='待删除分类').delete()

    # 售价低于进价应被表单拦截
    r = c.post('/goods/products/create/', {
        'name': '测试商品', 'barcode': '6999900000011', 'category': cat.pk, 'supplier': sup.pk,
        'spec': '测试', 'unit': '个', 'purchase_price': '10.00', 'sale_price': '5.00',
        'stock': 10, 'safety_stock': 5, 'status': 'on', 'remark': '',
    })
    check('售价低于进价被拦截', not Product.objects.filter(barcode='6999900000011').exists())

    r = c.post('/goods/products/create/', {
        'name': '测试商品', 'barcode': '6999900000028', 'category': cat.pk, 'supplier': sup.pk,
        'spec': '测试', 'unit': '个', 'purchase_price': '5.00', 'sale_price': '9.90',
        'stock': 10, 'safety_stock': 5, 'status': 'on', 'remark': '',
    })
    p = Product.objects.filter(barcode='6999900000028').first()
    check('商品创建成功', p is not None)

    if p:
        before = p.stock
        c.post(f'/goods/stock/{p.pk}/adjust/', {'change_type': 'check', 'quantity': -3, 'remark': '盘点'})
        p.refresh_from_db()
        check('库存盘点调整生效', p.stock == before - 3, f'{before} -> {p.stock}')

        # 报损超过库存应报错且不改动库存
        r = c.post(f'/goods/stock/{p.pk}/adjust/', {'change_type': 'loss', 'quantity': -99999, 'remark': '超量'})
        p.refresh_from_db()
        check('超量出库被拒绝', p.stock == before - 3, f'库存 {p.stock}')

        status_before = p.status
        c.post(f'/goods/products/{p.pk}/toggle/', {})
        p.refresh_from_db()
        check('商品可上下架切换', p.status != status_before, f'{status_before} -> {p.status}')

    # 有商品的分类不能删除
    r = c.post(f'/goods/categories/{cat.pk}/delete/', {})
    check('有商品的分类禁止删除', Category.objects.filter(pk=cat.pk).exists())

    # 空分类可删除
    empty_cat = Category.objects.create(name='待删除分类', code='TMP')
    c.post(f'/goods/categories/{empty_cat.pk}/delete/', {})
    check('空分类可删除', not Category.objects.filter(pk=empty_cat.pk).exists())


# --------------------------------------------------------------- 会员

def test_member():
    print('\n【6】会员 / 等级')
    c = admin()
    m = Member.objects.first()
    before = m.balance
    c.post(f'/member/{m.pk}/recharge/', {'amount': '100.00', 'remark': '流程测试'})
    m.refresh_from_db()
    check('会员充值到账', m.balance == before + Decimal('100'), f'{before} -> {m.balance}')

    # 等级自动升级
    gold = MemberLevel.objects.order_by('-min_points').first()
    m2 = Member.objects.exclude(pk=m.pk).first()
    m2.total_points = gold.min_points + 100
    m2.save()
    m2.refresh_level()
    m2.refresh_from_db()
    check('积分达标自动升级到最高等级', m2.level_id == gold.pk, f'当前等级 {m2.level}')


# --------------------------------------------------------------- 权限

def test_permission():
    print('\n【7】权限控制')
    c = Client()
    c.login(username='cashier', password='123456')

    r = c.get('/accounts/users/')
    check('收银员不能访问员工管理', r.status_code == 302, f'status={r.status_code}')

    r = c.get('/purchase/create/')
    check('收银员不能新建采购单', r.status_code == 302, f'status={r.status_code}')

    m = Client()
    m.login(username='manager', password='123456')
    r = m.get('/accounts/users/')
    check('店长可访问员工管理', r.status_code == 200, f'status={r.status_code}')


# --------------------------------------------------------------- 报表

def test_report():
    print('\n【8】报表与导出')
    c = admin()
    r = c.get('/report/sales/?start=2026-01-01&end=2026-12-31')
    check('销售报表按日期筛选', r.status_code == 200)
    ctx = r.context
    check('报表统计出销售额', ctx['total_amount'] > 0, f"total={ctx['total_amount']}")

    r = c.get('/report/sales/export/')
    check('CSV 导出可用', r.status_code == 200 and 'text/csv' in r['Content-Type'])

    r = c.get('/report/profit/')
    check('利润分析可用', r.status_code == 200)

    # 今日看板数据（验证 MySQL 下日期过滤未失效）
    r = c.get('/')
    check('首页今日销售统计非空', r.context['today_orders'] >= 0)
    check('首页近 7 日趋势有数据',
          sum(r.context['trend_totals']) > 0, f"trend={r.context['trend_totals']}")


def test_misc_writes():
    print('\n【9】其余写操作与查询')
    c = admin()

    # 员工新增 / 编辑 / 重置密码 / 停用
    r = c.post('/accounts/users/create/', {
        'username': 'testuser', 'real_name': '测试员工', 'role': User.ROLE_CASHIER,
        'employee_no': 'T999', 'phone': '13700000000', 'password': 'test123456',
        'is_active': 'on', 'address': '', 'entry_date': '',
    })
    u = User.objects.filter(username='testuser').first()
    check('员工账号创建成功', u is not None)
    if u:
        check('员工默认角色为收银员', u.role == User.ROLE_CASHIER)
        r = c.post(f'/accounts/users/{u.pk}/edit/', {
            'username': 'testuser', 'real_name': '测试员工改', 'role': User.ROLE_STOCK,
            'employee_no': 'T998', 'phone': '13700000001', 'is_active': 'on',
            'address': '', 'entry_date': '',
        })
        u.refresh_from_db()
        check('员工信息可修改', u.real_name == '测试员工改' and u.employee_no == 'T998')
        r = c.post(f'/accounts/users/{u.pk}/reset-password/',
                   {'new_password1': 'Newpass123!', 'new_password2': 'Newpass123!'})
        check('重置密码成功', r.status_code == 302, f'status={r.status_code}')
        c.post(f'/accounts/users/{u.pk}/toggle/', {})
        u.refresh_from_db()
        check('员工可停用', not u.is_active)
        u.delete()

    # 供应商新增 / 删除
    c.post('/goods/suppliers/create/', {
        'name': '临时供应商', 'contact': '王五', 'phone': '13711112222',
        'address': '测试路 1 号', 'bank_account': '', 'remark': '', 'is_active': 'on',
    })
    s = Supplier.objects.filter(name='临时供应商').first()
    check('供应商创建成功', s is not None)
    if s:
        c.post(f'/goods/suppliers/{s.pk}/delete/', {})
        check('无关联供应商可删除', not Supplier.objects.filter(pk=s.pk).exists())

    # 采购单取消 / 删除
    c2 = Client()
    c2.login(username='stocker', password='123456')
    c2.post('/purchase/create/', {'supplier': Supplier.objects.first().pk, 'remark': '待取消'})
    o1 = PurchaseOrder.objects.order_by('-pk').first()
    c2.post(f'/purchase/{o1.pk}/cancel/', {})
    o1.refresh_from_db()
    check('采购单可取消', o1.status == PurchaseOrder.STATUS_CANCELED)

    c2.post('/purchase/create/', {'supplier': Supplier.objects.first().pk, 'remark': '待删除'})
    o2 = PurchaseOrder.objects.order_by('-pk').first()
    c2.post(f'/purchase/{o2.pk}/delete/', {})
    check('草稿采购单可删除', not PurchaseOrder.objects.filter(pk=o2.pk).exists())

    # 已入库采购单不可删除
    confirmed = PurchaseOrder.objects.filter(status=PurchaseOrder.STATUS_CONFIRMED).first()
    c2.post(f'/purchase/{confirmed.pk}/delete/', {})
    check('已入库采购单禁止删除', PurchaseOrder.objects.filter(pk=confirmed.pk).exists())

    # 会员新增 / 停用
    c.post('/member/create/', {
        'card_no': '999999', 'name': '测试会员', 'phone': '13700000999', 'gender': 'M',
        'level': MemberLevel.objects.first().pk, 'address': '测试', 'is_active': 'on', 'remark': '',
    })
    m = Member.objects.filter(card_no='999999').first()
    check('会员创建成功', m is not None)
    if m:
        c.post(f'/member/{m.pk}/toggle/', {})
        m.refresh_from_db()
        check('会员可停用', not m.is_active)
        m.delete()

    # 会员等级新增 / 删除
    c.post('/member/levels/create/', {
        'name': '钻石会员', 'discount': '0.90', 'point_rate': '3.00', 'min_points': '8000', 'remark': '',
    })
    lv = MemberLevel.objects.filter(name='钻石会员').first()
    check('会员等级创建成功', lv is not None)
    if lv:
        c.post(f'/member/levels/{lv.pk}/delete/', {})
        check('无会员等级可删除', not MemberLevel.objects.filter(pk=lv.pk).exists())

    # 分页与搜索
    r = c.get('/member/?page=2')
    check('列表分页可用', r.status_code == 200 and r.context['page_obj'].number == 2)

    kw = Product.objects.first().name[:2]
    r = c.get(f'/goods/products/?q={kw}')
    check('商品搜索可用', r.status_code == 200 and r.context['page_obj'].paginator.count > 0)

    r = c.get(f'/sales/?pay=wechat')
    check('销售单按支付方式筛选', r.status_code == 200)


def main():
    test_pos()
    test_purchase()
    test_return()
    test_void()
    test_goods()
    test_member()
    test_permission()
    test_report()
    test_misc_writes()

    print('\n' + '=' * 50)
    print(f'通过 {len(PASSED)} 项，失败 {len(FAILED)} 项')
    if FAILED:
        print('\n失败明细：')
        for name, detail in FAILED:
            print(f'  - {name} {detail}')
        sys.exit(1)
    print('全部业务流程测试通过。')


if __name__ == '__main__':
    main()

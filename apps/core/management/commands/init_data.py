"""初始化演示数据：python manage.py init_data

会清空业务数据并重建一套贴近真实经营的演示账套：
员工、分类、供应商、商品（EAN-13 条码）、会员、采购单、近 30 天按客流时段分布的销售单。
"""

import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import OperationLog, StockLog
from apps.core.utils import generate_order_no, local_today
from apps.goods.models import Category, Product, Supplier
from apps.member.models import Member, MemberLevel
from apps.purchase.models import PurchaseItem, PurchaseOrder
from apps.sales.models import Sale, SaleItem, SaleReturn, SaleReturnItem

random.seed(20260911)

# ---------------------------------------------------------------- 基础档案

# 商品：（名称, 分类, 进价, 售价, 规格, 单位, 安全库存）
# 售价采用社区超市常见的 .8/.9 心理定价
PRODUCT_DATA = [
    # 饮料烟酒
    ('农夫山泉饮用天然水', '饮料烟酒', 1.10, 1.80, '550ml', '瓶', 48),
    ('可口可乐汽水', '饮料烟酒', 2.20, 3.50, '330ml', '罐', 36),
    ('康师傅冰红茶', '饮料烟酒', 2.10, 3.00, '500ml', '瓶', 36),
    ('雪花啤酒勇闯天涯', '饮料烟酒', 3.30, 4.80, '500ml', '瓶', 24),
    ('红牛维生素功能饮料', '饮料烟酒', 4.80, 6.50, '250ml', '罐', 24),
    ('南京炫赫门香烟', '饮料烟酒', 15.50, 18.00, '20支', '包', 20),
    # 休闲零食
    ('乐事薯片黄瓜味', '休闲零食', 4.30, 6.50, '70g', '袋', 24),
    ('奥利奥夹心饼干', '休闲零食', 5.20, 7.90, '116g', '袋', 24),
    ('好丽友派巧克力', '休闲零食', 8.60, 12.90, '12枚', '盒', 18),
    ('洽洽山核桃瓜子', '休闲零食', 6.20, 9.90, '260g', '袋', 20),
    ('德芙丝滑牛奶巧克力', '休闲零食', 9.80, 14.90, '43g', '块', 20),
    ('卫龙辣条亲嘴烧', '休闲零食', 2.50, 4.00, '108g', '袋', 30),
    # 粮油调味
    ('金龙鱼调和油', '粮油调味', 52.00, 69.90, '5L', '桶', 10),
    ('五常稻花香大米', '粮油调味', 46.00, 59.90, '10kg', '袋', 12),
    ('海天金标生抽', '粮油调味', 8.60, 11.90, '500ml', '瓶', 18),
    ('中盐加碘食用盐', '粮油调味', 1.60, 2.50, '400g', '袋', 30),
    ('太古白砂糖', '粮油调味', 5.40, 7.80, '1kg', '袋', 18),
    ('紫林山西老陈醋', '粮油调味', 4.60, 6.90, '500ml', '瓶', 18),
    # 日用百货
    ('金号本色卷纸', '日用百货', 12.50, 17.90, '10卷', '提', 20),
    ('雕牌高效洗洁精', '日用百货', 7.20, 10.90, '1.5kg', '瓶', 16),
    ('云南白药留兰香牙膏', '日用百货', 15.80, 22.90, '120g', '支', 18),
    ('蓝月亮深层洁净洗衣液', '日用百货', 26.00, 35.90, '3kg', '瓶', 10),
    ('心相印三层抽纸', '日用百货', 9.20, 13.90, '3包', '提', 20),
    ('南孚聚能环5号电池', '日用百货', 8.50, 12.00, '4粒', '卡', 16),
    # 生鲜果蔬
    ('新鲜西红柿', '生鲜果蔬', 3.60, 5.98, '500g', '份', 15),
    ('山东红富士苹果', '生鲜果蔬', 5.20, 8.80, '1kg', '份', 15),
    ('本地小白菜', '生鲜果蔬', 1.80, 3.50, '500g', '份', 12),
    ('散养土鸡蛋', '生鲜果蔬', 12.50, 17.90, '15枚', '盒', 12),
    ('云南香蕉', '生鲜果蔬', 3.20, 5.50, '1kg', '份', 12),
    # 乳品冷饮
    ('伊利纯牛奶', '乳品冷饮', 2.90, 4.50, '250ml', '盒', 36),
    ('安慕希希腊风味酸奶', '乳品冷饮', 5.10, 7.50, '205g', '盒', 30),
    ('光明优倍鲜牛奶', '乳品冷饮', 9.80, 13.90, '950ml', '瓶', 16),
    ('八喜香草冰淇淋杯', '乳品冷饮', 8.20, 12.00, '90g', '杯', 18),
]

# 供应商与主营品类（保证商品与供应商业务匹配，而不是随机分配）
SUPPLIER_DATA = [
    ('本地华联食品批发部', '张建国', '13801234567', '城关镇农贸路 18 号', ['饮料烟酒', '休闲零食']),
    ('信达粮油副食配送中心', '李慧敏', '13902345678', '开发区物流园 B 区 3 号', ['粮油调味']),
    ('鲜达生鲜供应链有限公司', '王大海', '13703456789', '农产品批发市场 7 号棚', ['生鲜果蔬', '乳品冷饮']),
    ('恒安日化用品有限公司', '赵秀兰', '13604567890', '工业大道 66 号', ['日用百货']),
]

# 会员姓名素材（姓氏 + 名，覆盖不同年龄层，避免全是同一代人）
SURNAMES = ['王', '李', '张', '刘', '陈', '杨', '赵', '周', '吴', '徐',
            '孙', '马', '朱', '胡', '郭', '何', '高', '林', '罗', '郑',
            '梁', '谢', '宋', '唐', '许', '韩', '冯', '邓', '曹', '彭']
GIVEN_NAMES = ['秀英', '桂英', '淑珍', '玉梅', '凤兰', '桂兰', '志强', '建军', '晓明', '海燕',
               '丽娟', '文静', '国庆', '春花', '雅雯', '子涵', '雨桐', '浩然', '思远', '嘉怡',
               '伟', '芳', '娜', '敏', '静', '磊', '洋', '勇', '艳', '杰']

# 小区名称，用于生成住址
COMMUNITIES = ['惠民小区', '阳光花园', '锦绣家园', '幸福里', '时代新城',
               '龙湖春天', '金桂苑', '和顺家园', '东方名苑', '书香雅苑']

# 手机号号段
PHONE_PREFIX = ['138', '139', '150', '151', '158', '159', '186', '187', '188', '199']

# 营业时段客流权重（社区超市典型双高峰：早市买菜、晚市下班）
HOUR_WEIGHTS = {
    7: 2, 8: 6, 9: 5, 10: 4, 11: 4, 12: 3, 13: 2, 14: 2,
    15: 2, 16: 3, 17: 6, 18: 8, 19: 7, 20: 5, 21: 3,
}
PAY_WEIGHTS = [('wechat', 45), ('alipay', 25), ('cash', 17), ('card', 8), ('balance', 5)]


def ean13(manufacturer: int, item: int) -> str:
    """生成合法的 EAN-13 条码（69 为中国前缀，最后一位为校验位）。"""
    body = f'69{manufacturer:05d}{item:05d}'
    digits = [int(c) for c in body]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return body + str((10 - total % 10) % 10)


def weighted_hour():
    hours = list(HOUR_WEIGHTS.keys())
    return random.choices(hours, weights=[HOUR_WEIGHTS[h] for h in hours])[0]


def weighted_pay():
    methods = [m for m, _ in PAY_WEIGHTS]
    weights = [w for _, w in PAY_WEIGHTS]
    return random.choices(methods, weights=weights)[0]


class Command(BaseCommand):
    help = '初始化社区超市销售管理系统的演示数据'

    def add_arguments(self, parser):
        parser.add_argument('--no-sales', action='store_true', help='不生成历史销售数据')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('开始初始化演示数据...'))

        # 全部写入放在同一事务中，避免逐条提交导致写入过慢
        with transaction.atomic():
            self.clear_data()
            users = self.create_users()
            categories = self.create_categories()
            suppliers = self.create_suppliers()
            products = self.create_products(categories, suppliers)
            levels, members = self.create_members()
            self.create_purchases(products, suppliers, users['stocker'])
            if not options.get('no_sales'):
                # 两名收银员轮班，销售单由不同人开出
                cashiers = [users['cashier'], User.objects.get(username='cashier2')]
                self.create_sales(products, members, cashiers)

        self.stdout.write(self.style.SUCCESS('演示数据初始化完成！'))
        self.stdout.write('登录账号：admin / manager / cashier / stocker，密码统一为 ******')

    # ---------------- 工具 ----------------

    def clear_data(self):
        # 退货单通过 PROTECT 外键关联销售单，必须先删除，否则清空会失败
        SaleReturnItem.objects.all().delete()
        SaleReturn.objects.all().delete()
        SaleItem.objects.all().delete()
        Sale.objects.all().delete()
        PurchaseItem.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        StockLog.objects.all().delete()
        OperationLog.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Supplier.objects.all().delete()
        Member.objects.all().delete()
        MemberLevel.objects.all().delete()
        User.objects.all().delete()

    def create_users(self):
        data = [
            ('admin', '陈立国', User.ROLE_ADMIN, 'A001', '13800000001', True),
            ('manager', '周慧敏', User.ROLE_MANAGER, 'M001', '13800000002', False),
            ('cashier', '李小雨', User.ROLE_CASHIER, 'C001', '13800000003', False),
            ('cashier2', '赵婷婷', User.ROLE_CASHIER, 'C002', '13800000004', False),
            ('stocker', '孙德海', User.ROLE_STOCK, 'S001', '13800000005', False),
        ]
        mapping = {}
        for username, name, role, no, phone, superuser in data:
            if superuser:
                user = User.objects.create_superuser(username=username, password='******')
            else:
                user = User.objects.create_user(username=username, password='******')
            user.real_name = name
            user.role = role
            user.employee_no = no
            user.phone = phone
            user.entry_date = local_today() - datetime.timedelta(days=random.randint(120, 1200))
            user.save()
            mapping[username] = user
        self.stdout.write(f'  员工账号 {len(data)} 个')
        return {'admin': mapping['admin'], 'manager': mapping['manager'],
                'cashier': mapping['cashier'], 'stocker': mapping['stocker']}

    def create_categories(self):
        names = ['饮料烟酒', '休闲零食', '粮油调味', '日用百货', '生鲜果蔬', '乳品冷饮']
        mapping = {}
        for i, name in enumerate(names, start=1):
            mapping[name] = Category.objects.create(
                name=name, code=f'C{i:02d}', sort=i, description=f'{name}类商品'
            )
        self.stdout.write(f'  商品分类 {len(names)} 个')
        return mapping

    def create_suppliers(self):
        mapping = {}
        for name, contact, phone, address, _cats in SUPPLIER_DATA:
            mapping[name] = Supplier.objects.create(
                name=name, contact=contact, phone=phone, address=address
            )
        self.stdout.write(f'  供应商 {len(SUPPLIER_DATA)} 个')
        return mapping

    def create_products(self, categories, suppliers):
        """按品类匹配供应商，生成带合法 EAN-13 条码的商品档案。"""
        cat_to_supplier = {}
        for name, _c, _p, _a, cats in SUPPLIER_DATA:
            for cat in cats:
                cat_to_supplier[cat] = suppliers[name]

        # 每个品类一个厂商码，条码前缀可区分品类
        cat_codes = {name: 10000 + idx * 777 for idx, name in enumerate(categories.keys())}

        products = []
        counter = {}
        for name, cat, purchase, sale, spec, unit, safe in PRODUCT_DATA:
            counter[cat] = counter.get(cat, 0) + 1
            product = Product.objects.create(
                name=name,
                barcode=ean13(cat_codes[cat], counter[cat]),
                category=categories[cat],
                supplier=cat_to_supplier.get(cat),
                spec=spec,
                unit=unit,
                purchase_price=Decimal(str(purchase)),
                sale_price=Decimal(str(sale)),
                # 库存围绕安全库存上下浮动；刻意留几款偏低的商品用于演示库存预警
                stock=random.randint(max(1, safe - 5), safe + 90),
                safety_stock=safe,
                shelf_life_days={'生鲜果蔬': 7, '乳品冷饮': 21}.get(cat, random.choice([180, 365, 540, 720])),
            )
            products.append(product)
        self.stdout.write(f'  商品档案 {len(products)} 条（EAN-13 条码）')
        return products

    def create_members(self):
        levels = {}
        for name, discount, rate, min_points in [
            ('普通会员', Decimal('1.00'), Decimal('1.00'), 0),
            ('银卡会员', Decimal('0.98'), Decimal('1.50'), 800),
            ('金卡会员', Decimal('0.95'), Decimal('2.00'), 3000),
        ]:
            levels[name] = MemberLevel.objects.create(
                name=name, discount=discount, point_rate=rate, min_points=min_points
            )
        level_list = list(levels.values())

        members = []
        used_names, used_phones = set(), set()
        for i in range(40):
            while True:
                name = random.choice(SURNAMES) + random.choice(GIVEN_NAMES)
                if name not in used_names:
                    used_names.add(name)
                    break
            while True:
                phone = random.choice(PHONE_PREFIX) + ''.join(str(random.randint(0, 9)) for _ in range(8))
                if phone not in used_phones:
                    used_phones.add(phone)
                    break

            join_date = timezone.now() - datetime.timedelta(days=random.randint(30, 1000))
            total_points = random.randint(0, 4200)
            # 等级与累计积分保持一致
            level = max((lv for lv in level_list if lv.min_points <= total_points),
                        key=lambda lv: lv.min_points, default=level_list[0])
            member = Member.objects.create(
                card_no=f'8802{i + 1:05d}',
                name=name,
                phone=phone,
                gender=random.choice(['F', 'M', 'F', 'M', 'N']),
                birthday=datetime.date(random.randint(1958, 2005), random.randint(1, 12), random.randint(1, 28)),
                level=level,
                points=random.randint(0, max(1, total_points // 3)),
                total_points=total_points,
                balance=Decimal(str(random.choice([0, 0, 50, 100, 200, 300, 500]))),
                join_date=join_date,
                address=f'{random.choice(COMMUNITIES)} {random.randint(1, 18)}号楼'
                        f'{random.randint(1, 4)}单元{random.randint(101, 1805)}室',
            )
            members.append(member)
        self.stdout.write(f'  会员等级 3 个，会员 {len(members)} 人')
        return levels, members

    def create_purchases(self, products, suppliers, operator):
        """按品类生成采购单，保证供应商与所采商品业务匹配。"""
        by_category = {}
        for p in products:
            by_category.setdefault(p.category.name, []).append(p)

        for idx, (name, _c, _p, _a, cats) in enumerate(SUPPLIER_DATA):
            supplier = suppliers[name]
            pool = [p for cat in cats for p in by_category.get(cat, [])]
            if not pool:
                continue
            created = timezone.now() - datetime.timedelta(days=40 - idx * 2)
            order = PurchaseOrder.objects.create(
                order_no=generate_order_no('CG', PurchaseOrder),
                supplier=supplier,
                operator=operator,
                status=PurchaseOrder.STATUS_CONFIRMED,
                remark='常规补货',
                created_at=created,
                confirmed_at=created,
            )
            for product in random.sample(pool, min(len(pool), 6)):
                quantity = random.randint(30, 120)
                PurchaseItem.objects.create(
                    order=order, product=product, quantity=quantity, price=product.purchase_price
                )
                # 走统一库存入口，保证库存流水与账面库存一致
                product.change_stock(
                    quantity,
                    change_type=StockLog.TYPE_PURCHASE,
                    operator=operator,
                    related_no=order.order_no,
                    remark=f'采购入库（{supplier.name}）',
                )
            order.recalc_total()
            StockLog.objects.filter(related_no=order.order_no).update(created_at=created)
        self.stdout.write(f'  历史采购单 {len(SUPPLIER_DATA)} 张（已入库，含库存流水）')

    def create_sales(self, products, members, cashiers):
        """按营业时段客流权重生成近 30 天销售单。"""
        today = local_today()
        count = 0
        for day_offset in range(29, -1, -1):
            day = today - datetime.timedelta(days=day_offset)
            # 周末客流上浮
            base = 9 if day.weekday() >= 5 else 6
            orders_today = random.randint(base, base + 5)

            for _ in range(orders_today):
                created = datetime.datetime.combine(
                    day,
                    datetime.time(weighted_hour(), random.randint(0, 59), random.randint(0, 59)),
                )
                # 会员消费占比约 55%；收银员按早/晚班交替
                member = random.choice(members) if random.random() < 0.55 else None
                cashier = cashiers[0] if created.hour < 15 else cashiers[1]

                # 客单商品数：以 1~3 种为主，偶尔多件
                kinds = random.choices([1, 2, 3, 4, 5, 6], weights=[26, 28, 20, 13, 8, 5])[0]
                picked = random.sample(products, min(kinds, len(products)))
                rows = []
                for p in picked:
                    if p.stock <= 0:
                        continue
                    qty = random.choices([1, 2, 3, 4], weights=[62, 24, 9, 5])[0]
                    rows.append((p, min(qty, p.stock)))
                if not rows:
                    continue

                total = sum((p.sale_price * q for p, q in rows), Decimal('0'))
                cost = sum((p.purchase_price * q for p, q in rows), Decimal('0'))
                discount = Decimal('0')
                if member:
                    discount = (total * (Decimal('1') - Decimal(str(member.discount)))).quantize(Decimal('0.01'))
                actual = (total - discount).quantize(Decimal('0.01'))

                pay_method = weighted_pay()
                if pay_method == 'balance' and (not member or member.balance < actual):
                    pay_method = 'wechat' if member else 'cash'
                if not member and pay_method == 'balance':
                    pay_method = 'cash'

                sale = Sale.objects.create(
                    order_no=generate_order_no('XS', Sale),
                    member=member,
                    cashier=cashier,
                    total_amount=total,
                    discount_amount=discount,
                    actual_amount=actual,
                    cost_amount=cost,
                    pay_method=pay_method,
                    created_at=created,
                )
                for p, q in rows:
                    SaleItem.objects.create(
                        sale=sale, product=p, quantity=q,
                        price=p.sale_price, cost_price=p.purchase_price,
                    )
                    p.change_stock(
                        -q,
                        change_type=StockLog.TYPE_SALE,
                        operator=cashier,
                        related_no=sale.order_no,
                        remark='前台销售出库',
                    )

                if member:
                    rate = Decimal(str(member.point_rate))
                    sale.points_earned = int(actual * rate)
                    sale.save(update_fields=['points_earned'])
                    member.points += sale.points_earned
                    member.total_points += sale.points_earned
                    member.total_spend += actual
                    if pay_method == 'balance':
                        member.balance -= actual
                    member.save()
                StockLog.objects.filter(related_no=sale.order_no).update(created_at=created)
                count += 1
        self.stdout.write(f'  历史销售单 {count} 张（近 30 天，按时段分布）')

        # 生成 2 笔退货，用于演示退货与库存回补
        self.create_returns(cashiers[0])

    def create_returns(self, operator):
        """挑选两张会员订单做部分退货。"""
        candidates = Sale.objects.filter(member__isnull=False, status=Sale.STATUS_DONE).order_by('-created_at')[:8]
        made = 0
        for sale in candidates:
            if made >= 2:
                break
            item = sale.items.first()
            if not item or item.quantity < 1:
                continue
            qty = 1
            amount = (item.price * qty).quantize(Decimal('0.01'))
            ret = SaleReturn.objects.create(
                return_no=generate_order_no('TH', SaleReturn, field='return_no'),
                sale=sale,
                operator=operator,
                amount=amount,
                reason=random.choice(['商品临期', '顾客买错', '包装破损']),
            )
            SaleReturnItem.objects.create(
                sale_return=ret, product=item.product, quantity=qty, price=item.price
            )
            item.product.change_stock(
                qty,
                change_type=StockLog.TYPE_RETURN,
                operator=operator,
                related_no=ret.return_no,
                remark='销售退货入库',
            )
            member = sale.member
            if member:
                member.balance += amount
                member.total_spend = max(Decimal('0'), member.total_spend - amount)
                member.save()
            sale.status = Sale.STATUS_RETURNED
            sale.save(update_fields=['status'])
            StockLog.objects.filter(related_no=ret.return_no).update(created_at=sale.created_at)
            made += 1
        if made:
            self.stdout.write(f'  历史退货单 {made} 张')

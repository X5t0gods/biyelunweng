# 基于 Django 的中小型社区超市销售管理系统

面向中小型社区超市的**进销存 + 前台收银 + 会员营销 + 经营报表**一体化 Web 系统，可作为课程设计 / 毕业设计项目直接使用。

技术栈：Python 3 + Django 5.x + MySQL 8.0 + Bootstrap 5 + ECharts 5（可一键切回 SQLite）。

---

## 一、快速开始

### 1. 准备 MySQL

系统默认连接 `127.0.0.1:3306` 的 MySQL 8.0，数据库名 `supermarket`，账号 `root / 123456`。
这些参数均可用环境变量覆盖，无需改代码：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DB_ENGINE` | `mysql` | 设为 `sqlite` 可切回 SQLite |
| `DB_NAME` | `supermarket` | 数据库名 |
| `DB_USER` | `root` | 用户名 |
| `DB_PASSWORD` | `123456` | 密码 |
| `DB_HOST` | `127.0.0.1` | 主机 |
| `DB_PORT` | `3306` | 端口 |

建库语句：

```sql
CREATE DATABASE supermarket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 本项目开发时使用的本地 MySQL 实例配置文件在 `C:\mysql_dev\my.ini`，
> 可通过 `C:\mysql_dev\start_mysql.bat` / `stop_mysql.bat` 启动与停止。

### 2. 安装依赖并启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 建立数据库表
python manage.py makemigrations
python manage.py migrate

# 3. 初始化演示数据（员工 / 分类 / 供应商 / 商品 / 会员 / 采购单 / 近 30 天历史销售单）
python manage.py init_data

# 4. 启动服务
python manage.py runserver 8000
```

浏览器访问 <http://127.0.0.1:8000/> 即可。

> **MySQL 驱动说明**：Django 的 MySQL 后端依赖 `MySQLdb`。Windows 下编译 `mysqlclient` 较为麻烦，
> 项目改用纯 Python 的 `PyMySQL`，并在 `config/__init__.py` 中执行 `pymysql.install_as_MySQLdb()`
> 完成适配。若已安装 `mysqlclient`，直接删掉该文件内容即可，业务代码无需任何改动。

> **时区说明**：`settings.py` 中 `USE_TZ = False`、`TIME_ZONE = 'Asia/Shanghai'`。
> 因为 Windows 版 MySQL 默认不导入时区表（`mysql.time_zone_*` 为空），`CONVERT_TZ()` 会返回 NULL，
> 导致 Django 的日期过滤与 `TruncDate` 聚合全部失效。关闭 `USE_TZ` 后所有时间均按本地时间处理，
> 对单一门店系统是最简单可靠的做法。

### 演示账号（密码统一 `123456`）

| 账号 | 姓名 | 角色 | 权限说明 |
|---|---|---|---|
| admin | 系统管理员 | 超级管理员 | 全部功能 |
| manager | 陈店长 | 店长 | 经营数据、员工/日志管理、订单作废 |
| cashier | 小李 | 收银员 | 前台收银、订单与退货 |
| stocker | 老周 | 库管/采购员 | 采购入库、库存盘点、商品维护 |

### 自动化自检

```bash
python scripts/smoke_test.py    # 全站页面可访问性检查（35+ 个页面）
python scripts/flow_test.py     # 60 项业务流程回归（收银/采购/退货/作废/权限/报表…）
python scripts/nav_test.py      # 36 项侧边栏菜单高亮检查
python scripts/inspect_data.py  # 数据体检：连接信息、数据量、真实度抽查、客流时段分布
python scripts/live_check.py    # 对正在运行的服务发真实 HTTP 请求，验证页面与菜单高亮
```

> **改完代码后页面却没变化？**
> `smoke_test` / `flow_test` / `nav_test` 用的是 Django 测试客户端，**直接调用 WSGI、不经过端口**，
> 所以即使服务进程还跑着旧代码，这些脚本也会全绿——容易误判成"已修复"。
> Django 进程加载过的 Python 模块（例如新增 `app_tags.py` 里的自定义标签）不会因改文件而更新，
> 必须**重启服务**；此外浏览器也可能缓存旧页面，用 `Ctrl + F5` 强制刷新。
> 排查顺序：重启服务 → `python scripts/live_check.py` → 浏览器强刷。

---

## 二、功能模块

| 模块 | 主要功能 |
|---|---|
| 系统首页 | 今日销售额/毛利/订单数、本月累计、近 7 日销售趋势、分类销售占比、库存预警、最近订单 |
| 前台收银（POS） | 条码/名称检索加购、购物车改量移除、会员绑定自动折扣、多种支付方式（现金/微信/支付宝/银行卡/会员余额）、一键结算扣减库存并累计积分 |
| 商品管理 | 商品分类、商品档案（条码/规格/进价/售价/安全库存/保质期）、上下架、商品详情与库存变动追溯 |
| 采购进货 | 采购单新建 → 明细添加 → 确认入库（库存自动增加并生成流水）、取消/删除 |
| 库存管理 | 库存查询与总金额、库存盘点/报损/手动调整、库存流水追溯、库存预警清单 |
| 销售管理 | 销售订单查询（按单号/会员/支付方式/日期）、订单详情、订单作废（回退库存）、销售退货（部分或整单退货，库存回补） |
| 会员管理 | 会员等级（折扣率、积分倍率、升级门槛）、会员档案、储值充值、消费记录 |
| 统计报表 | 销售统计（趋势/分类占比/支付方式/热销 TOP20，支持 CSV 导出）、利润分析（月度收入-成本-毛利、商品毛利排行）、商品销售排行、库存与会员概览 |
| 系统管理 | 员工账号与角色权限、操作日志审计、个人中心与密码修改 |

---

## 三、目录结构

```
community_supermarket/
├── config/                 # 项目配置（settings / urls / wsgi）
├── apps/
│   ├── core/               # 首页看板、操作日志、库存流水、通用工具与权限
│   ├── accounts/           # 员工账号与角色权限
│   ├── goods/              # 商品、分类、供应商、库存
│   ├── purchase/           # 采购进货
│   ├── sales/              # 收银与销售、退货
│   ├── member/             # 会员与等级
│   └── report/             # 统计报表
├── templates/              # 全站页面模板
├── static/                 # CSS / JS
├── scripts/                # 冒烟测试与流程测试脚本
├── docs/                   # 开题报告等文档
├── manage.py
└── requirements.txt
```

---

## 四、核心数据模型

| 模型 | 说明 | 关键字段 |
|---|---|---|
| `accounts.User` | 员工账号（继承 AbstractUser） | 角色、工号、手机号、在职状态 |
| `goods.Supplier` | 供应商 | 名称、联系人、电话、地址 |
| `goods.Category` | 商品分类 | 名称、编码、排序 |
| `goods.Product` | 商品 | 条码、分类、进价、售价、库存、安全库存 |
| `core.StockLog` | 库存流水 | 变动类型、变动数量、变动前后库存、关联单号 |
| `core.OperationLog` | 操作日志 | 操作人、模块、动作、详情、IP |
| `purchase.PurchaseOrder` / `PurchaseItem` | 采购单与明细 | 单号、供应商、总额、状态 |
| `sales.Sale` / `SaleItem` | 销售单与明细 | 单号、会员、应收/优惠/实收/成本、支付方式、积分 |
| `sales.SaleReturn` / `SaleReturnItem` | 销售退货 | 退货单号、原单、退款金额、原因 |
| `member.MemberLevel` / `Member` | 会员等级与会员 | 折扣率、积分倍率、积分、储值余额 |

---

## 五、切换到 SQLite（离线演示用）

系统默认使用 MySQL。若需要在没有 MySQL 的机器上演示，设置环境变量即可切回 SQLite，
业务代码零改动：

```bash
# Windows
set DB_ENGINE=sqlite
python manage.py migrate
python manage.py init_data

# Linux / macOS
export DB_ENGINE=sqlite
```

反向切回 MySQL 同理，去掉该环境变量并设置好连接参数即可。

## 六、演示数据说明

`init_data` 生成的账套刻意贴近真实经营：

- **商品条码**为带校验位的合法 EAN-13 码，`69` 为中国前缀，按品类分配不同厂商码；
- **供应商与品类匹配**：生鲜果蔬、乳品冷饮由生鲜供应链供货，日用百货由日化公司供货，不会出现"日化公司供应蔬菜"的情况；
- **销售时间按客流时段分布**：呈现社区超市典型的早市（8–9 点）与晚市（18–19 点）双高峰，午后低谷；
- **支付方式**按真实占比分布：微信约 47%、支付宝约 26%、现金约 21%、银行卡与会员余额合计约 6%；
- **周末客流上浮**，会员消费占比约 55%，两名收银员按早晚班交替开单；
- 采购单走统一库存入口，销售单也会生成对应的出库流水，**账实相符、全程可追溯**。

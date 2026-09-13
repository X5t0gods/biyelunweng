"""在线检查：对**正在运行的服务**（默认 http://127.0.0.1:8000）发起真实 HTTP 请求，
验证页面状态码与侧边栏菜单高亮项。

与 smoke_test.py / nav_test.py 的区别：
- smoke_test / nav_test 用的是 Django 测试客户端，直接调用 WSGI，**不经端口**，
  因此进程加载的旧代码不会暴露出来（边改边看时容易误判为"已修复"）；
- 本脚本走真实 HTTP，能验证浏览器实际拿到的 HTML。

使用：
    python manage.py runserver 8000
    python scripts/live_check.py                 # 默认检查 127.0.0.1:8000
    python scripts/live_check.py http://192.168.1.9:8000
"""

import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000').rstrip('/')
ACCOUNT = ('admin', '123456')

# 期望「该页面高亮哪个菜单项」
EXPECTED = [
    ('/', '系统首页'),
    ('/sales/pos/', '前台收银'),
    ('/sales/', '销售订单'),
    ('/sales/returns/', '销售退货'),
    ('/goods/products/', '商品管理'),
    ('/goods/categories/', '商品管理'),
    ('/goods/stock/', '库存查询'),
    ('/goods/stock/logs/', '库存查询'),
    ('/goods/stock/alert/', '库存查询'),
    ('/purchase/', '采购进货'),
    ('/goods/suppliers/', '供应商'),
    ('/member/', '会员管理'),
    ('/report/sales/', '统计报表'),
    ('/accounts/users/', '员工账号'),
    ('/accounts/logs/', '操作日志'),
]

ACTIVE_RE = re.compile(r'<a\s+href="[^"]*"\s+class="side-link\s+active"[^>]*>(.*?)</a>', re.S)
TAG_RE = re.compile(r'<[^>]+>')

passed = failed = 0


def build_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def login(opener):
    page = opener.open(f'{BASE}/accounts/login/').read().decode('utf-8')
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    if not match:
        return False, '登录页未取到 csrftoken'
    payload = urllib.parse.urlencode({
        'username': ACCOUNT[0],
        'password': ACCOUNT[1],
        'csrfmiddlewaretoken': match.group(1),
    }).encode()
    opener.open(urllib.request.Request(
        f'{BASE}/accounts/login/', data=payload,
        headers={'Referer': f'{BASE}/accounts/login/'},
    ))
    return True, 'ok'


def active_labels(html):
    labels = []
    for raw in ACTIVE_RE.findall(html):
        text = TAG_RE.sub('', raw).strip()
        if text and text not in labels:
            labels.append(text)
    return labels


def main():
    global passed, failed
    opener = build_opener()
    ok, hint = login(opener)
    print(f'服务地址：{BASE}')
    if not ok:
        print(f'登录失败：{hint}')
        print('提示：请先启动服务并执行 python manage.py init_data 生成演示账号。')
        return 1
    print(f'登录成功：{ACCOUNT[0]}\n')

    for path, expected in EXPECTED:
        try:
            resp = opener.open(f'{BASE}{path}')
            html = resp.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            failed += 1
            print(f'  [失败] {path:<22} HTTP {exc.code}')
            continue
        except OSError as exc:
            failed += 1
            print(f'  [失败] {path:<22} 连接失败：{exc}')
            continue

        labels = active_labels(html)
        if labels == [expected]:
            passed += 1
            print(f'  [通过] {path:<22} 高亮「{expected}」')
        else:
            failed += 1
            shown = '、'.join(labels) if labels else '（无高亮）'
            print(f'  [失败] {path:<22} 期望「{expected}」实际「{shown}」   '
                  f'← 若与改前一致，多半是服务进程未重启 / 浏览器缓存')

    print(f'\n===== 结果：通过 {passed} 项，失败 {failed} 项 =====')
    if failed:
        print('仍未生效时依次排查：\n'
              '  1. 重启 Django 服务（新增模板标签或改 Python 代码必须重启）；\n'
              '  2. 浏览器强制刷新 Ctrl + F5，或用无痕窗口打开；\n'
              '  3. 用本脚本再跑一次，若脚本已正确而浏览器不对，则纯属浏览器缓存。')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

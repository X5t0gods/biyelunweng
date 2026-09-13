"""自定义模板标签与过滤器。"""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_active(context, *names, css='active'):
    """侧边栏菜单高亮判定，按「命名空间:路由名」精确匹配当前页面。

    用法：
        <a class="side-link {% nav_active 'goods:supplier_list' 'goods:supplier_create' %}">
        <a class="side-link {% nav_active 'report:*' %}">   <!-- 整个 report 应用 -->

    注意：不要直接用 request.resolver_match.namespace 判断高亮——同一命名空间下
    往往有多个相互独立的菜单项（如 goods 下的商品/库存/供应商），会一起亮起来。
    """
    request = context.get('request')
    match = getattr(request, 'resolver_match', None)
    if match is None or not match.url_name:
        return ''

    current = f'{match.namespace}:{match.url_name}' if match.namespace else match.url_name
    for name in names:
        if name.endswith(':*'):
            if match.namespace and match.namespace == name[:-2]:
                return css
        elif name == current:
            return css
    return ''


@register.filter
def sub(value, arg):
    """模板中的减法：{{ a|sub:b }}。"""
    try:
        return float(value or 0) - float(arg or 0)
    except (TypeError, ValueError):
        return 0


@register.filter
def dict_key(mapping, key):
    """按 key 取字典值，用于把 choice value 转成显示名称。"""
    if not mapping:
        return key
    try:
        return mapping.get(key, key)
    except AttributeError:
        return key

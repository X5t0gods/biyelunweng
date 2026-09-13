"""通用工具函数。"""

from django.utils import timezone


def local_today():
    """获取当前本地日期。

    Django 的 timezone.localdate() 在 USE_TZ=False 时会抛
    "localtime() cannot be applied to a naive datetime"，这里统一用兼容写法。
    """
    return timezone.now().date()


def generate_order_no(prefix, model_cls, field='order_no'):
    """生成业务单号：前缀 + 年月日 + 4 位流水号（按当天已有单据数量递增）。

    field 用于兼容单号字段名不是 order_no 的模型（如 SaleReturn 使用 return_no）。
    """
    today = local_today().strftime('%Y%m%d')
    count = model_cls.objects.filter(**{f'{field}__startswith': f'{prefix}{today}'}).count()
    return f'{prefix}{today}{count + 1:04d}'


def get_client_ip(request):
    """获取客户端真实 IP。"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def write_log(request, module, action, detail=''):
    """记录操作日志。"""
    from apps.core.models import OperationLog
    user = request.user if request.user.is_authenticated else None
    OperationLog.objects.create(
        user=user,
        module=module,
        action=action,
        detail=detail,
        ip=get_client_ip(request),
    )

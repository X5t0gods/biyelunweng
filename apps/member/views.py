"""会员管理视图。"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.mixins import manager_required
from apps.core.utils import write_log
from apps.member.forms import MemberForm, MemberLevelForm, RechargeForm
from apps.member.models import Member, MemberLevel


# ----------------------------- 会员等级 -----------------------------

@login_required
def level_list(request):
    levels = MemberLevel.objects.all()
    return render(request, 'member/level_list.html', {'levels': levels})


@login_required
@manager_required
def level_create(request):
    form = MemberLevelForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'member', '新增会员等级', f'新增等级：{obj.name}')
        messages.success(request, f'会员等级【{obj.name}】创建成功。')
        return redirect('member:level_list')
    return render(request, 'member/level_form.html', {'form': form, 'title': '新增会员等级'})


@login_required
@manager_required
def level_update(request, pk):
    obj = get_object_or_404(MemberLevel, pk=pk)
    form = MemberLevelForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, '会员等级已更新。')
        return redirect('member:level_list')
    return render(request, 'member/level_form.html', {'form': form, 'title': '编辑会员等级', 'object': obj})


@login_required
@manager_required
def level_delete(request, pk):
    obj = get_object_or_404(MemberLevel, pk=pk)
    if obj.members.exists():
        messages.error(request, f'等级【{obj.name}】下仍有会员，无法删除。')
    else:
        obj.delete()
        messages.success(request, '会员等级已删除。')
    return redirect('member:level_list')


# ----------------------------- 会员 -----------------------------

@login_required
def member_list(request):
    keyword = request.GET.get('q', '').strip()
    level_id = request.GET.get('level', '')
    qs = Member.objects.select_related('level').all()
    if keyword:
        qs = qs.filter(Q(card_no__icontains=keyword) | Q(name__icontains=keyword)
                       | Q(phone__icontains=keyword))
    if level_id:
        qs = qs.filter(level_id=level_id)

    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'member/member_list.html', {
        'page_obj': page_obj, 'keyword': keyword, 'level_id': level_id,
        'levels': MemberLevel.objects.all(),
        'query_params': f'q={keyword}&level={level_id}',
    })


@login_required
def member_create(request):
    form = MemberForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'member', '新增会员', f'新增会员：{obj.name}（{obj.card_no}）')
        messages.success(request, f'会员【{obj.name}】创建成功。')
        return redirect('member:member_list')
    return render(request, 'member/member_form.html', {'form': form, 'title': '新增会员'})


@login_required
def member_update(request, pk):
    obj = get_object_or_404(Member, pk=pk)
    form = MemberForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        write_log(request, 'member', '修改会员', f'修改会员信息：{obj.name}')
        messages.success(request, '会员信息已更新。')
        return redirect('member:member_detail', pk=obj.pk)
    return render(request, 'member/member_form.html', {'form': form, 'title': '编辑会员', 'object': obj})


@login_required
def member_detail(request, pk):
    obj = get_object_or_404(Member, pk=pk)
    sales = obj.sales.select_related('cashier').all()[:15]
    return render(request, 'member/member_detail.html', {'object': obj, 'sales': sales})


@login_required
def member_recharge(request, pk):
    """会员储值充值。"""
    obj = get_object_or_404(Member, pk=pk)
    form = RechargeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        amount = form.cleaned_data['amount']
        obj.balance += amount
        obj.save(update_fields=['balance'])
        write_log(request, 'member', '会员充值', f'{obj.name} 充值 ¥{amount}')
        messages.success(request, f'充值成功，{obj.name} 当前余额 ¥{obj.balance}。')
        return redirect('member:member_detail', pk=obj.pk)
    return render(request, 'member/recharge_form.html', {'form': form, 'object': obj})


@login_required
def member_toggle(request, pk):
    obj = get_object_or_404(Member, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=['is_active'])
    messages.success(request, f'已{"启用" if obj.is_active else "停用"}会员 {obj.name}。')
    return redirect('member:member_list')


@login_required
def member_api(request):
    """收银台会员检索。"""
    keyword = request.GET.get('q', '').strip()
    if not keyword:
        return JsonResponse({'success': False, 'message': '请输入会员卡号或手机号'})
    member = Member.objects.filter(
        Q(card_no__iexact=keyword) | Q(phone=keyword), is_active=True
    ).first()
    if not member:
        return JsonResponse({'success': False, 'message': '未找到该会员'})
    return JsonResponse({
        'success': True,
        'data': {
            'id': member.pk, 'name': member.name, 'card_no': member.card_no,
            'level': member.level_name, 'discount': member.discount,
            'points': member.points, 'balance': str(member.balance),
        },
    })

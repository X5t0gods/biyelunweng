"""通用表单基类：统一注入 Bootstrap 样式。"""

from django import forms


class BootstrapFormMixin:
    """为所有字段自动添加 Bootstrap 表单控件样式。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            css = 'form-control'
            if isinstance(widget, (forms.CheckboxInput,)):
                css = 'form-check-input'
            elif isinstance(widget, (forms.Select, forms.SelectMultiple, forms.NullBooleanSelect)):
                css = 'form-select'
            elif isinstance(widget, forms.Textarea):
                css = 'form-control'
                widget.attrs.setdefault('rows', 3)
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = (existing + ' ' + css).strip()
            if field.required and not isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('placeholder', f'请输入{field.label}')

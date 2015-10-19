from django import forms
from django import template
register = template.Library()


@register.filter
def is_dateinput(field):
    return isinstance(field.field.widget, forms.DateInput)

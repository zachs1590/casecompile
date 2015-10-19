from django import template
register = template.Library()


@register.filter
def as_range(value):
    return range(value)

@register.filter
def multiply(value, factor):
    return value * float(factor)
    
@register.filter
def startswith(value, prefix):
    return str(value).startswith(prefix)

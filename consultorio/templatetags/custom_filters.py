from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Obtiene un elemento del diccionario usando una clave"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, [])
    return []


@register.filter
def add(value, arg):
    """Suma dos números"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value

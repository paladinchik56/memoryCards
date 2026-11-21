"""Template helpers for translated strings (see web/i18n.py)."""
import re

from django import template

register = template.Library()


@register.filter
def tt(strings, key):
    """{{ t|tt:key }} — look a string up by a key held in a variable."""
    return strings.get(key, key)


@register.filter
def fill(text, value):
    """{{ t.lib_cards_n|fill:5 }} — put `value` into the {placeholder} of a string."""
    return re.sub(r'\{\w+\}', str(value), str(text), count=1)

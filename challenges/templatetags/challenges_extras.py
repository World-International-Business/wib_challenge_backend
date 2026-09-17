import markdown
import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
@stringfilter
def render_markdown(value):
    value = re.sub(r'\[\]\(https?://(?:127\.0\.0\.1|localhost)[^)]*\)', '', value)
    value = re.sub(r'\[\]\([^)]*\)', '', value)
    md = markdown.Markdown(extensions=["fenced_code"])
    return mark_safe(md.convert(value))

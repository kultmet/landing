import re

from django import template
from django.utils.html import escape
from django.utils.html import format_html

register = template.Library()

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
PAREN_LINK_RE = re.compile(r"(?P<label>[^()\n]+?)\s*\((?P<url>https?://[^\s)]+)\)")


def _anchor(label: str, url: str) -> str:
    return (
        f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
        f'style="color:var(--crimson);text-decoration:underline;text-underline-offset:0.18em;">'
        f"{escape(label)}</a>"
    )


@register.filter(name="render_linked_text")
def render_linked_text(value):
    if value is None:
        return ""

    text = escape(str(value))
    text = MARKDOWN_LINK_RE.sub(
        lambda match: _anchor(match.group(1), match.group(2)),
        text,
    )
    text = PAREN_LINK_RE.sub(
        lambda match: _anchor(match.group("label").strip(), match.group("url")),
        text,
    )
    text = text.replace("\n", "<br>")
    return format_html("{}", text)

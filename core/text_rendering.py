import re

from django.utils.html import escape
from django.utils.html import format_html

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _anchor(label: str, url: str) -> str:
    return (
        f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
        f'style="color:var(--crimson);text-decoration:underline;text-underline-offset:0.18em;">'
        f"{escape(label)}</a>"
    )


def render_markdown_text(value) -> str:
    if value is None:
        return ""

    text = escape(str(value))
    text = MARKDOWN_LINK_RE.sub(
        lambda match: _anchor(match.group(1), match.group(2)),
        text,
    )
    text = BOLD_RE.sub(lambda match: f"<strong>{escape(match.group(1))}</strong>", text)
    text = text.replace("\n", "<br>")
    return format_html(text)

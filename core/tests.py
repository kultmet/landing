from django.test import SimpleTestCase

from .text_rendering import render_markdown_text


class RenderMarkdownTextTests(SimpleTestCase):
    def test_renders_bold_links_and_line_breaks(self):
        rendered = render_markdown_text("Hello **world**\n[site](https://example.com)")

        assert "<strong>world</strong>" in rendered
        assert '<a href="https://example.com"' in rendered
        assert "<br>" in rendered

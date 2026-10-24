"""Safe rendering helpers for the user-editable public verification layout."""

from html import escape
from html.parser import HTMLParser
import re


ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "caption", "div", "em", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "i", "li", "ol", "p", "span", "strong", "table",
    "tbody", "td", "th", "thead", "tr", "u", "ul",
}
VOID_TAGS = {"br", "hr"}
ALLOWED_STYLE_PROPERTIES = {
    "background-color", "border", "border-collapse", "border-color", "border-radius",
    "border-style", "border-width", "color", "font-size", "font-style", "font-weight",
    "margin", "margin-bottom", "margin-left", "margin-right", "margin-top", "padding",
    "padding-bottom", "padding-left", "padding-right", "padding-top", "text-align",
    "text-decoration", "vertical-align", "width",
}


def _safe_style(value):
    declarations = []
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        name, content = declaration.split(":", 1)
        name = name.strip().lower()
        content = content.strip()
        if (
            name in ALLOWED_STYLE_PROPERTIES
            and content
            and not re.search(r"url\s*\(|expression\s*\(|[<>\\{}]", content, re.I)
        ):
            declarations.append(f"{name}:{content}")
    return ";".join(declarations)


class _LayoutSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []
        self.blocked_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "svg", "math"}:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in ALLOWED_TAGS:
            return
        safe_attrs = []
        for name, value in attrs:
            name = (name or "").lower()
            value = value or ""
            if name == "style":
                value = _safe_style(value)
                if value:
                    safe_attrs.append(f' style="{escape(value, quote=True)}"')
            elif name == "class" and re.fullmatch(r"[\w\s-]{1,160}", value):
                safe_attrs.append(f' class="{escape(value, quote=True)}"')
            elif tag in {"td", "th"} and name in {"colspan", "rowspan"} and value.isdigit():
                safe_attrs.append(f' {name}="{value}"')
            elif tag == "a" and name == "href" and (
                value.strip().lower().startswith(("https://", "http://", "mailto:"))
                or value.strip() == "{{VIEW_REPORT_URL}}"
            ):
                safe_attrs.append(f' href="{escape(value, quote=True)}"')
            elif tag == "a" and name == "target" and value == "_blank":
                safe_attrs.append(' target="_blank" rel="noopener noreferrer"')
        self.parts.append(f"<{tag}{''.join(safe_attrs)}>")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "svg", "math"} and self.blocked_depth:
            self.blocked_depth -= 1
            return
        if self.blocked_depth or tag not in self.open_tags:
            return
        while self.open_tags:
            opened = self.open_tags.pop()
            self.parts.append(f"</{opened}>")
            if opened == tag:
                break

    def handle_data(self, data):
        if not self.blocked_depth:
            self.parts.append(escape(data))

    def handle_entityref(self, name):
        if not self.blocked_depth:
            self.parts.append(f"&amp;{escape(name)};")

    def handle_charref(self, name):
        if not self.blocked_depth:
            self.parts.append(f"&amp;#{escape(name)};")

    def finish(self):
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def render_verification_layout(layout_html, report, report_url, *, show_report=True, logo_url=""):
    """Sanitize the layout and replace only supported, escaped report tokens."""
    if not show_report:
        layout_html = re.sub(
            r'<a\b(?=[^>]*\bhref\s*=\s*(["\'])\{\{VIEW_REPORT_URL\}\}\1)[^>]*>.*?</a\s*>',
            "",
            layout_html or "",
            flags=re.IGNORECASE | re.DOTALL,
        )
    sanitizer = _LayoutSanitizer()
    sanitizer.feed(layout_html or "")
    sanitizer.close()
    rendered = sanitizer.finish()
    booking = report.booking
    values = {
        "ORDER_CODE": booking.tracking_code,
        "REPORT_NUMBER": report.certificate_no,
        "BATCH_NO": booking.batch_no or "-",
        "CUSTOMER_NAME": booking.customer.name if booking.customer_id else "-",
        "SAMPLE_NAME": booking.sample_name.display_name if booking.sample_name_id else "-",
    }
    for token, value in values.items():
        rendered = rendered.replace("{{" + token + "}}", escape(str(value or "")))
    # Accept common Django-style field paths as aliases so existing layouts
    # that used those spellings display the booking values as expected.
    aliases = {
        "{{booking.batch_no}}": values["BATCH_NO"],
        "{{ booking.batch_no }}": values["BATCH_NO"],
        "{{report.booking.batch_no}}": values["BATCH_NO"],
        "{{ report.booking.batch_no }}": values["BATCH_NO"],
        "{{booking.certificate_no}}": values["REPORT_NUMBER"],
        "{{ booking.certificate_no }}": values["REPORT_NUMBER"],
        "{{report.certificate_no}}": values["REPORT_NUMBER"],
        "{{ report.certificate_no }}": values["REPORT_NUMBER"],
        "{{booking.customer.name}}": values["CUSTOMER_NAME"],
        "{{ booking.customer.name }}": values["CUSTOMER_NAME"],
        "{{booking.sample_name}}": values["SAMPLE_NAME"],
        "{{ booking.sample_name }}": values["SAMPLE_NAME"],
    }
    for token, value in aliases.items():
        rendered = rendered.replace(token, escape(str(value or "")))
    rendered = rendered.replace("{{VIEW_REPORT_URL}}", escape(report_url, quote=True))
    if logo_url:
        logo_html = (
            f'<img class="verification-company-logo" src="{escape(logo_url, quote=True)}" '
            'alt="Company logo">'
        )
        if "{{COMPANY_LOGO}}" in rendered:
            rendered = rendered.replace("{{COMPANY_LOGO}}", logo_html)
        else:
            rendered = logo_html + rendered
    else:
        rendered = rendered.replace("{{COMPANY_LOGO}}", "")
    return rendered

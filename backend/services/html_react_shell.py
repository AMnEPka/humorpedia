"""Combine a trusted built React template with a safe, independently readable fallback."""
from html import escape
from html.parser import HTMLParser
from services.public_html import render_html_page

class _Template(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        for number, char in enumerate(source):
            if char == "\n":
                self.lines.append(number + 1)
        self.edits = []
        self.in_head = False
        self.head_end = None
        self.root = None
        self.root_depth = 0
        self.root_end = None
        self.title_start = None
        self.html = None

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        start = self.source_offset()
        end = start + len(self.get_starttag_text())
        values = dict(attrs)
        if tag == "html":
            if self.html is not None:
                raise ValueError("Duplicate HTML element")
            self.html = (start, end, attrs)
        if tag == "head":
            self.in_head = True
        if self.in_head:
            if tag == "title":
                self.title_start = start
            elif (tag == "meta" and (values.get("name", "").lower() in {"description", "robots"} or values.get("property", "").lower().startswith("og:"))) or (tag == "link" and values.get("rel", "").lower() == "canonical"):
                self.edits.append((start, end, ""))
        if values.get("id") == "root":
            if tag != "div" or self.root is not None:
                raise ValueError("Expected a single empty div#root")
            self.root = (start, end, attrs)
            self.root_depth = 1
        elif self.root_depth:
            self.root_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.root_depth:
            self.root_depth -= 1

    def handle_endtag(self, tag):
        start = self.source_offset()
        end = self.source.find(">", start) + 1
        if self.in_head and tag == "title" and self.title_start is not None:
            self.edits.append((self.title_start, end, ""))
            self.title_start = None
        if tag == "head":
            self.head_end = start
            self.in_head = False
        if self.root_depth:
            self.root_depth -= 1
            if not self.root_depth:
                self.root_end = start

def _tag(tag, attrs):
    return "<" + tag + "".join(" " + key + ("" if value is None else '="' + escape(value, quote=True) + '"') for key, value in attrs) + ">"

def render_react_shell(page, template_html):
    parser = _Template(template_html)
    parser.feed(template_html)
    parser.close()
    if parser.root is None or parser.root_end is None or parser.head_end is None or parser.html is None:
        raise ValueError("Expected HTML/head and one empty root")
    start, end, attrs = parser.root
    if template_html[end:parser.root_end].strip() or parser.title_start is not None:
        raise ValueError("Expected empty root and complete head")
    rendered = render_html_page(page)
    metadata = rendered.split("<head>", 1)[1].split("</head>", 1)[0].replace('<meta charset="utf-8">', "", 1)
    body = rendered.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    fallback = '<div id="html-pilot-fallback" data-path="' + escape(page.canonical_path, quote=True) + '">' + body + "</div>"
    root_attrs = [(key, value) for key, value in attrs if key not in {"hidden", "aria-hidden"}] + [("hidden", None), ("aria-hidden", "true")]
    html_start, html_end, html_attrs = parser.html
    edits = parser.edits + [
        (parser.head_end, parser.head_end, metadata),
        (start, end, fallback + _tag("div", root_attrs)),
        (html_start, html_end, _tag("html", [(key, value) for key, value in html_attrs if key != "lang"] + [("lang", page.metadata.lang)])),
    ]
    for start, end, replacement in sorted(edits, reverse=True):
        template_html = template_html[:start] + replacement + template_html[end:]
    return template_html

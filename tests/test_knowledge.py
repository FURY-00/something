import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from jarvis.config import load_config
from jarvis.context import ToolContext
from jarvis.tools.knowledge import article_text, lookup_encyclopedia, parse_catalog

CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="https://specs.opds.io/opds-1.2">
  <entry>
    <id>urn:uuid:1111-2222</id>
    <title>Wikipedia</title>
    <name>wikipedia_en_all_nopic</name>
    <link type="text/html" href="/content/wikipedia_en_all_nopic_2025-01" />
  </entry>
</feed>"""

SEARCH = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Search</title>
  <item><title>Albert Einstein</title>
    <link>/content/wikipedia_en_all_nopic_2025-01/A/Albert_Einstein</link></item>
  <item><title>Einstein family</title>
    <link>/content/wikipedia_en_all_nopic_2025-01/A/Einstein_family</link></item>
</channel></rss>"""

ARTICLE = """<html><body><table><tr><td><p>Infobox text that should be skipped entirely</p></td></tr></table>
<p>Albert Einstein was a German-born theoretical physicist<sup>[1]</sup> who developed the
theory of relativity.</p><p>short</p>
<p>He received the 1921 Nobel Prize in Physics for his services to theoretical physics.</p>
<script>var x = "<p>no</p>";</script></body></html>"""


def test_article_text_keeps_only_prose():
    text = article_text(ARTICLE)
    assert text == (
        "Albert Einstein was a German-born theoretical physicist who developed the theory of "
        "relativity.\nHe received the 1921 Nobel Prize in Physics for his services to "
        "theoretical physics."
    )


def test_parse_catalog():
    assert parse_catalog(CATALOG) == [{
        "id": "1111-2222", "name": "wikipedia_en_all_nopic", "title": "Wikipedia",
        "content": "wikipedia_en_all_nopic_2025-01",
    }]


def test_lookup_against_fake_kiwix_server():
    queries = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/catalog/v2/entries":
                body = CATALOG
            elif url.path == "/search":
                queries.append(parse_qs(url.query))
                body = SEARCH
            elif url.path.endswith("/A/Albert_Einstein"):
                body = ARTICLE
            else:
                self.send_error(404)
                return
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        cfg = load_config()
        cfg.knowledge.kiwix_url = f"http://127.0.0.1:{server.server_address[1]}"
        result = lookup_encyclopedia(ToolContext(cfg), "einstein")
    finally:
        server.shutdown()
        server.server_close()
    assert result.startswith("Article: Albert Einstein\nAlbert Einstein was a German-born")
    assert "Other matching articles: Einstein family" in result
    assert queries[0]["books.id"] == ["1111-2222"]
    assert queries[0]["pattern"] == ["einstein"]

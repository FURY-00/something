"""Offline encyclopedia lookups through a local Kiwix server.

Kiwix (https://kiwix.org) serves a complete copy of Wikipedia from a single
file on your disk, with no internet needed. This gives Jarvis millions of
up-to-date-when-downloaded articles to check facts against, on top of what
the language model memorised in training. Setup steps are in the README.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

from . import tool

ATOM = "{http://www.w3.org/2005/Atom}"


class _ArticleText(HTMLParser):
    """Collects paragraph text from an article, skipping tables and citations."""

    SKIP = {"script", "style", "table", "sup", "figure", "nav", "math"}

    def __init__(self) -> None:
        super().__init__()
        self.paragraphs: list[str] = []
        self._skip_depth = 0
        self._in_p = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "p":
            self._in_p, self._buf = True, []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "p" and self._in_p:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(text) > 30:
                self.paragraphs.append(text)
            self._in_p = False

    def handle_data(self, data):
        if self._in_p and not self._skip_depth:
            self._buf.append(data)


def article_text(html: str, limit: int = 3000) -> str:
    parser = _ArticleText()
    parser.feed(html)
    text = "\n".join(parser.paragraphs)
    return text[:limit] + ("..." if len(text) > limit else "")


def parse_catalog(xml_text: str) -> list[dict]:
    """Books listed by kiwix-serve's OPDS catalog."""
    books = []
    root = ET.fromstring(xml_text)
    for entry in root.iter(f"{ATOM}entry"):
        book = {
            "id": (entry.findtext(f"{ATOM}id") or "").replace("urn:uuid:", ""),
            "name": entry.findtext(f"{ATOM}name") or "",
            "title": entry.findtext(f"{ATOM}title") or "",
            "content": "",
        }
        for link in entry.findall(f"{ATOM}link"):
            if link.get("type") == "text/html":
                book["content"] = link.get("href", "").rstrip("/").split("/")[-1]
        books.append(book)
    return books


def parse_search(xml_text: str) -> list[dict]:
    """Results from kiwix-serve's ``/search?...&format=xml`` RSS output."""
    root = ET.fromstring(xml_text)
    return [
        {"title": item.findtext("title") or "", "link": item.findtext("link") or ""}
        for item in root.iter("item")
    ]


class Kiwix:
    def __init__(self, url: str, book: str = "") -> None:
        self.url = url.rstrip("/") + "/"
        self.book = book
        self._books: list[dict] | None = None

    def books(self) -> list[dict]:
        if self._books is None:
            resp = requests.get(urljoin(self.url, "catalog/v2/entries?count=-1"), timeout=10)
            resp.raise_for_status()
            self._books = parse_catalog(resp.text)
        return self._books

    def _pick_book(self) -> dict:
        books = self.books()
        if not books:
            raise RuntimeError("the Kiwix server has no books loaded")
        if self.book:
            for b in books:
                if self.book in (b["name"], b["content"], b["id"]):
                    return b
        # Prefer Wikipedia if several are loaded.
        return next((b for b in books if "wikipedia" in b["name"]), books[0])

    def search(self, query: str, count: int = 3) -> list[dict]:
        book = self._pick_book()
        attempts = [
            {"books.id": book["id"]},  # kiwix-serve 3.3+
            {"content": book["content"] or book["name"]},  # older versions
        ]
        for scope in attempts:
            params = {**scope, "pattern": query, "format": "xml", "pageLength": count}
            resp = requests.get(urljoin(self.url, "search"), params=params, timeout=15)
            if resp.ok and "<rss" in resp.text[:1000]:
                try:
                    return parse_search(resp.text)[:count]
                except ET.ParseError:
                    continue
        return []

    def article(self, link: str) -> str:
        resp = requests.get(urljoin(self.url, link.lstrip("/")), timeout=15)
        resp.raise_for_status()
        return article_text(resp.text)


def _kiwix(ctx) -> Kiwix:
    if "kiwix" not in ctx.state:
        k = ctx.config.knowledge
        ctx.state["kiwix"] = Kiwix(k.kiwix_url, k.kiwix_book)
    return ctx.state["kiwix"]


@tool(
    "Look something up in the offline encyclopedia (a local copy of Wikipedia). "
    "Use it for facts about people, places, history, science, events, definitions, "
    "or whenever you aren't sure of a fact.",
    {"query": {"type": "string", "description": "Topic to look up, e.g. 'Albert Einstein'"}},
    available=lambda ctx: bool(ctx.config.knowledge.kiwix_url),
)
def lookup_encyclopedia(ctx, query: str) -> str:
    kiwix = _kiwix(ctx)
    results = kiwix.search(query)
    if not results:
        return f"No encyclopedia articles found for '{query}'."
    best = results[0]
    text = kiwix.article(best["link"])
    others = ", ".join(r["title"] for r in results[1:])
    extra = f"\n(Other matching articles: {others})" if others else ""
    return f"Article: {best['title']}\n{text}{extra}"

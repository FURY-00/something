"""Websites and web searches.

Jarvis's brain is offline, but it can still drive your browser. These tools
need an internet connection only because the websites themselves do.
"""

from __future__ import annotations

import webbrowser
from urllib.parse import quote_plus

from . import tool

SITES = {
    "youtube": "https://www.youtube.com",
    "instagram": "https://www.instagram.com",
    "instagram reels": "https://www.instagram.com/reels/",
    "reels": "https://www.instagram.com/reels/",
    "youtube shorts": "https://www.youtube.com/shorts",
    "shorts": "https://www.youtube.com/shorts",
    "facebook": "https://www.facebook.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "whatsapp": "https://web.whatsapp.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "maps": "https://www.google.com/maps",
    "google maps": "https://www.google.com/maps",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "wikipedia": "https://en.wikipedia.org",
    "spotify": "https://open.spotify.com",
}

SEARCH_URLS = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
    "amazon": "https://www.amazon.com/s?k={}",
    "maps": "https://www.google.com/maps/search/{}",
    "images": "https://www.google.com/search?tbm=isch&q={}",
    "github": "https://github.com/search?q={}",
}


def normalize_url(site: str) -> str:
    key = site.strip().lower()
    if key in SITES:
        return SITES[key]
    if "://" in key:
        return site.strip()
    if "." not in key:
        key = key.replace(" ", "") + ".com"
    return "https://" + key


@tool(
    "Open a website in the web browser. Accepts a URL, a domain, or a well-known "
    "site name like 'youtube', 'instagram', 'gmail', 'whatsapp'.",
    {"site": {"type": "string", "description": "URL, domain or site name"}},
)
def open_website(ctx, site: str) -> str:
    url = normalize_url(site)
    webbrowser.open(url)
    return f"Opened {url} in the browser."


@tool(
    "Search the internet in the web browser (Google, YouTube, Wikipedia, Amazon, "
    "Maps, images or GitHub). Opens the results page for the user to look at.",
    {
        "query": {"type": "string", "description": "What to search for"},
        "engine": {"type": "string", "enum": sorted(SEARCH_URLS), "description": "Where to search"},
    },
)
def search_web(ctx, query: str, engine: str = "google") -> str:
    url = SEARCH_URLS[engine].format(quote_plus(query))
    webbrowser.open(url)
    return f"Showing {engine} results for '{query}' in the browser."

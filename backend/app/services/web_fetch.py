"""
Cedric AI - Web Page Fetching
=================================

Distinct from search_web (services/gemini_client.py's search_web,
which uses Gemini's built-in Google Search grounding for open-ended
queries): this fetches and extracts readable text from ONE SPECIFIC
URL the student provides - "go through this website X" needs the
actual page content, not a search result about it.

SECURITY: fetch_url_text resolves the hostname and rejects private/
loopback/link-local addresses before fetching, to prevent the backend
being used to reach internal services (SSRF) via a student-supplied
URL - e.g. http://localhost:8000/... or a cloud metadata address.

JS-RENDERED PAGES: a plain httpx GET only ever sees the initial HTML
a server sends - it never runs JavaScript. Many modern sites (React/
Vue/Next.js apps, site builders like Wix/Squarespace) inject all their
actual visible content client-side after the page loads, so a raw
fetch of those sites returns a near-empty shell (e.g. just a <title>).
To handle that, if the raw fetch returns suspiciously little text, we
retry through r.jina.ai, a free reader/rendering proxy that runs the
page's JS server-side and returns the fully rendered text. The SSRF
check still runs against the ORIGINAL url before we ever fetch anything.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MAX_FETCH_CHARS = 8000  # caps how much page text enters a single prompt
MIN_TEXT_CHARS = 200    # below this, assume the page is JS-rendered and needs the fallback


class UnsafeUrlError(Exception):
    pass


class FetchError(Exception):
    pass


def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    except (socket.gaierror, ValueError):
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def _fetch_raw_html(url: str) -> str:
    try:
        response = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CedricAI/1.0)"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc
    return response.text


def _fetch_rendered_text(url: str) -> str:
    """
    Fallback for JS-rendered pages: r.jina.ai fetches the URL in a
    headless browser (so JS runs) and returns clean readable text
    directly - no HTML parsing needed on our side for this path.
    """
    reader_url = f"https://r.jina.ai/{url}"
    try:
        response = httpx.get(reader_url, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FetchError(f"Could not render {url}: {exc}") from exc
    return " ".join(response.text.split())


def fetch_url_text(url: str) -> str:
    if not _is_safe_url(url):
        raise UnsafeUrlError(f"'{url}' is not a fetchable public URL.")

    html = _fetch_raw_html(url)
    text = _extract_text(html)

    if len(text) < MIN_TEXT_CHARS:
        # Raw HTML was near-empty - likely a JS-rendered page. Retry
        # through the rendering proxy before giving up.
        rendered = _fetch_rendered_text(url)
        if len(rendered) > len(text):
            text = rendered

    if not text:
        raise FetchError(f"No readable text content found at {url}.")

    return text[:MAX_FETCH_CHARS]
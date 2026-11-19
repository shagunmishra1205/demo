"""Fetches a public web page for the link reader.

The server visits whatever address a user types, so this must never reach private
networks (SSRF). Rules: https only, port 443, no embedded passwords, every address the
host resolves to must be public, redirects are followed by hand and each hop is checked
again, and the download is capped in size and time.

Known limit: the address is checked before connecting, so a hostile DNS server that
changes its answer between the check and the connection could slip through. Run the
deployed backend without access to internal networks to close that gap fully.
"""
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 10.0
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AwaazFormBot/0.1)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(Exception):
    """A problem the user can be told about. `code` is stable; the frontend maps it to text."""

    STATUS = {
        "blocked": 400,
        "fetch_failed": 502,
        "too_large": 413,
        "not_html": 415,
        "needs_signin": 422,
        "no_questions": 422,
    }

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = self.STATUS.get(code, 400)


def _resolve(host: str, port: int) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]


def assert_public_url(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme != "https":
        raise FetchError("blocked", "Only secure https:// links are allowed.")
    if not parts.hostname:
        raise FetchError("blocked", "That link has no website address.")
    if parts.username or parts.password:
        raise FetchError("blocked", "Links with a username or password are not allowed.")
    try:
        port = parts.port or 443
    except ValueError:
        raise FetchError("blocked", "That link has an invalid port.")
    if port != 443:
        raise FetchError("blocked", "Only standard https links are allowed.")

    try:
        addresses = _resolve(parts.hostname, port)
    except socket.gaierror:
        raise FetchError("fetch_failed", "Could not find that website.")
    if not addresses:
        raise FetchError("fetch_failed", "Could not find that website.")

    for raw in addresses:
        ip = ipaddress.ip_address(raw.split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped  # ::ffff:127.0.0.1 is still 127.0.0.1
        if not ip.is_global:
            raise FetchError("blocked", "That address is not a public website.")


def fetch_html(url: str, transport: httpx.BaseTransport | None = None) -> tuple[str, str]:
    """Returns (final_url, html). Raises FetchError."""
    current = url
    try:
        with httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(TIMEOUT_SECONDS),
            follow_redirects=False,
            headers=HEADERS,
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                assert_public_url(current)
                with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("fetch_failed", "The website sent a broken redirect.")
                        current = urljoin(current, location)
                        continue
                    if resp.status_code >= 400:
                        raise FetchError("fetch_failed", f"The website answered with error {resp.status_code}.")
                    if "html" not in resp.headers.get("content-type", "").lower():
                        raise FetchError("not_html", "That link is not a web page.")
                    data = bytearray()
                    for chunk in resp.iter_bytes():
                        data += chunk
                        if len(data) > MAX_BYTES:
                            raise FetchError("too_large", "That page is too large to read.")
                    return current, bytes(data).decode(resp.charset_encoding or "utf-8", errors="replace")
    except httpx.HTTPError:
        raise FetchError("fetch_failed", "Could not open that website. Check the link and try again.")
    raise FetchError("fetch_failed", "That link redirects too many times.")

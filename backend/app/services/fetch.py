"""Fetching user-supplied URLs safely.

Users paste arbitrary links, so every request (and every redirect hop) is checked to
resolve only to public internet addresses. This blocks the obvious SSRF routes to
localhost, private networks and cloud metadata endpoints. It does not defend against
DNS rebinding between the check and the connection; acceptable for this POC.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.services.errors import FetchError

MAX_REDIRECTS = 5
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Many retailers serve bot-detection pages to non-browser user agents.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/139.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True)
class FetchedResource:
    url: str  # final URL after redirects
    content_type: str
    body: bytes


async def ensure_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) links are supported.")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise FetchError(f"Couldn't find the site {parts.hostname}.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise FetchError("That link points to a private or local address.")


async def fetch(
    url: str, *, max_bytes: int, accept: str = "*/*", client: httpx.AsyncClient | None = None
) -> FetchedResource:
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT, headers=BROWSER_HEADERS)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            await ensure_public_url(url)
            async with client.stream(
                "GET", url, headers={"Accept": accept}, follow_redirects=False
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                if response.status_code in (401, 403, 429):
                    raise FetchError(
                        "That site blocked automated access. Try uploading a photo or "
                        "screenshot of the item instead."
                    )
                if response.status_code >= 400:
                    raise FetchError(f"That link returned an error ({response.status_code}).")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchError("That page or image is too large to process.")
                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                return FetchedResource(
                    url=str(response.url), content_type=content_type, body=bytes(body)
                )
        raise FetchError("That link redirected too many times.")
    except httpx.HTTPError as exc:
        raise FetchError("Couldn't load that link. Check it and try again.") from exc
    finally:
        if owns_client:
            await client.aclose()

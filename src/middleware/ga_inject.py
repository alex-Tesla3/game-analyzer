"""Google Analytics (GA4 / gtag.js) injection into HTML pages.

Injects the standard gtag snippet right after the ``<head>`` tag of every
``text/html`` response, so all pages of the app are tracked without editing
each template. The measurement ID is configurable via ``GOOGLE_ANALYTICS_ID``
(defaults to ``G-70XNK1WHPX``).
"""

from __future__ import annotations

import os
import re
from typing import Any

from starlette.responses import Response

_DEFAULT_GA_ID = "G-70XNK1WHPX"

_GTAG_SNIPPET = """<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());

  gtag('config', '{ga_id}');
</script>"""

_HEAD_TAG_RE = re.compile(r"<head[^>]*>", re.IGNORECASE)
_ALREADY_INJECTED_RE = re.compile(r"googletagmanager\.com/gtag/js\?id=", re.IGNORECASE)


def ga_measurement_id() -> str:
    """Return the configured GA measurement ID (or the default)."""
    return os.getenv("GOOGLE_ANALYTICS_ID", "").strip() or _DEFAULT_GA_ID


def build_gtag_snippet(ga_id: str) -> str:
    return _GTAG_SNIPPET.format(ga_id=ga_id)


async def _read_response_body(response: Any) -> bytes:
    """Read the full body of a Starlette response (plain or streamed)."""
    body = getattr(response, "body", None)
    if isinstance(body, bytes):
        return body
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is None:
        return b""
    chunks = [chunk async for chunk in body_iterator]
    return b"".join(chunks)


def _rebuild_html(response: Any, text: str) -> Response:
    """Return a new HTML response with the given body (drops stale content-length)."""
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    return Response(
        content=text,
        status_code=response.status_code,
        headers=headers,
        media_type="text/html",
    )


async def inject_google_analytics(request: Any, call_next: Any):
    """ASGI middleware: inject the GA gtag snippet into HTML responses."""
    response = await call_next(request)

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return response

    body = await _read_response_body(response)
    if not body:
        return response

    text = body.decode("utf-8", errors="ignore")
    if _ALREADY_INJECTED_RE.search(text):
        return _rebuild_html(response, text)

    snippet = build_gtag_snippet(ga_measurement_id())
    head_match = _HEAD_TAG_RE.search(text)
    if head_match:
        text = text[: head_match.end()] + "\n" + snippet + "\n" + text[head_match.end():]
    elif "</head>" in text:
        text = text.replace("</head>", snippet + "\n</head>", 1)

    # Always rebuild with the body we already read; never return a consumed stream.
    return _rebuild_html(response, text)

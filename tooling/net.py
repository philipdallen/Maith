"""net.py — the single scheme-validated HTTP fetch helper.

Bandit's B310 warns that `urllib.request.urlopen` accepts `file:` and custom
schemes, not just http(s). Every call site in this repo passes a hard-coded API
URL, so the real risk is low, but the pattern is worth closing: routing every
outbound request through one wrapper keeps the scheme policy in one place and
makes a stray `file://` URL impossible to smuggle in.

Only `https://` is allowed. No call site needs plain http.
"""
from __future__ import annotations

import urllib.request
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"https"})


def safe_urlopen(url, *, timeout: float = 30):
    """`urllib.request.urlopen`, restricted to https:// URLs.

    Accepts a URL string or a `urllib.request.Request`. Raises `ValueError` for
    any other scheme, so a `file://` or custom-scheme URL is refused before the
    request is opened rather than resolved by urllib.
    """
    req = url if isinstance(url, urllib.request.Request) else urllib.request.Request(url)
    scheme = urlparse(req.full_url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"refusing non-https URL scheme: {scheme or '(none)'}")
    # Scheme is validated above; bandit cannot see through the wrapper.
    return urllib.request.urlopen(req, timeout=timeout)  # nosec B310

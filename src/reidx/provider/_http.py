"""Shared HTTP helper for provider clients — stdlib urllib, no extra deps."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 120

_SSL_CONTEXT: ssl.SSLContext | None = None


def _build_ssl_context() -> ssl.SSLContext:
    insecure = os.environ.get("REIDX_INSECURE", "").strip().lower() in ("1", "true", "yes", "on")
    if insecure:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    ctx = ssl.create_default_context()
    try:
        ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
    except ssl.SSLError:
        pass
    return ctx


def _ssl_ctx() -> ssl.SSLContext:
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        _SSL_CONTEXT = _build_ssl_context()
    return _SSL_CONTEXT


def post_json(url: str, payload: dict, headers: dict[str, str], timeout: int = TIMEOUT_SECONDS) -> dict:
    """POST a JSON payload, return the parsed JSON response.

    Raises RuntimeError on HTTP or network errors — providers surface those
    to the agent loop, which turns them into tool-result errors rather than
    crashing the turn.
    """
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"content-type": "application/json", **headers}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection error: {exc}") from exc
    return json.loads(raw)


def get_json(url: str, headers: dict[str, str], timeout: int = TIMEOUT_SECONDS) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection error: {exc}") from exc
    return json.loads(raw)

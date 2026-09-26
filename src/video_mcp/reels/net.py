"""HTTP calls to the outside APIs (pictures, voice, video polls) with retries: the cheap gateways
often answer 5xx/429 for a minute, and one such answer should not fail the whole reel."""

from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger(__name__)

RETRY_DELAYS = (5, 15, 30, 60)


def retryable(resp: httpx.Response) -> bool:
    return resp.status_code == 429 or resp.status_code >= 500


def request(method: str, url: str, **kwargs) -> httpx.Response:
    """Like httpx.request, but asks again after network errors and 5xx/429. Returns the last
    response (the caller checks its status); raises the last network error."""
    for delay in (*RETRY_DELAYS, None):
        try:
            resp = httpx.request(method, url, **kwargs)
            if not retryable(resp) or delay is None:
                return resp
            log.warning("%s %s -> %s, retrying in %ss", method, url.split("?")[0], resp.status_code, delay)
        except httpx.TransportError as exc:
            if delay is None:
                raise
            log.warning("%s %s -> %s, retrying in %ss", method, url.split("?")[0], exc, delay)
        time.sleep(delay)
    raise AssertionError("unreachable")


def get(url: str, **kwargs) -> httpx.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> httpx.Response:
    return request("POST", url, **kwargs)

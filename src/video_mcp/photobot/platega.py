"""Platega payments (docs.platega.io): a payment link for the customer, then its status by id.
Statuses: PENDING, CONFIRMED (paid), CANCELED, CHARGEBACKED (refunded)."""

from __future__ import annotations

from ..reels import net
from .config import bot_settings


def _headers() -> dict[str, str]:
    s = bot_settings
    if not (s.platega_merchant and s.platega_secret):
        raise ValueError("Set PLATEGA_MERCHANT_ID and PLATEGA_SECRET")
    return {"X-MerchantId": s.platega_merchant, "X-Secret": s.platega_secret}


def _url(path: str) -> str:
    return f"{bot_settings.platega_base_url.rstrip('/')}/{path.lstrip('/')}"


def create(amount: int, description: str, user_id: int, username: str, payload: str, return_url: str) -> dict:
    """Returns {"transactionId", "url", "status"}; the customer picks SBP or a card on the payment page."""
    resp = net.post(_url("v2/transaction/process"), headers=_headers(), timeout=60, json={
        "paymentDetails": {"amount": amount, "currency": "RUB"},
        "description": description,
        "return": return_url,
        "failedUrl": return_url,
        "payload": payload,
        "metadata": {"userId": str(user_id), **({"userName": f"@{username}"} if username else {})},
    })
    if resp.status_code >= 400:
        raise RuntimeError(f"Platega error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if not data.get("transactionId") or not data.get("url"):
        raise RuntimeError(f"Platega returned no payment link: {str(data)[:300]}")
    return data


def status(transaction_id: str) -> str:
    resp = net.get(_url(f"transaction/{transaction_id}"), headers=_headers(), timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Platega status error {resp.status_code}: {resp.text[:300]}")
    return str(resp.json().get("status", "")).upper()

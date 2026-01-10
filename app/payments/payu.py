"""PayU client.

This is a minimal integration:
- Creates order via OAuth token and /api/v2_1/orders
- Verifies webhook signature when configured

You must configure PayU environment variables in app/config.py:
- PAYU_ENV (sandbox|production)
- PAYU_POS_ID
- PAYU_CLIENT_ID
- PAYU_CLIENT_SECRET
- PAYU_SECOND_KEY (required for webhook verification)
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass

import requests
from flask import current_app
from werkzeug.exceptions import BadRequest


@dataclass
class PayUConfig:
    env: str
    pos_id: str
    client_id: str
    client_secret: str
    second_key: str
    notify_url: str | None


class PayUClient:
    def __init__(self, cfg: PayUConfig):
        self.cfg = cfg

    @classmethod
    def from_flask_config(cls) -> "PayUClient":
        cfg = current_app.config
        env = (cfg.get("PAYU_ENV") or "sandbox").lower()

        pos_id = cfg.get("PAYU_POS_ID")
        client_id = cfg.get("PAYU_CLIENT_ID")
        client_secret = cfg.get("PAYU_CLIENT_SECRET")
        second_key = cfg.get("PAYU_SECOND_KEY")
        notify_url = cfg.get("PAYU_NOTIFY_URL")

        missing = [k for k, v in {
            "PAYU_POS_ID": pos_id,
            "PAYU_CLIENT_ID": client_id,
            "PAYU_CLIENT_SECRET": client_secret,
            "PAYU_SECOND_KEY": second_key,
        }.items() if not v]

        if missing:
            raise BadRequest(f"Brak konfiguracji PayU: {', '.join(missing)}")

        return cls(PayUConfig(env=env, pos_id=str(pos_id), client_id=str(client_id), client_secret=str(client_secret), second_key=str(second_key), notify_url=notify_url))

    def _base_url(self) -> str:
        # PayU REST API base
        if self.cfg.env == "production":
            return "https://secure.payu.com"
        return "https://secure.snd.payu.com"

    def _token_url(self) -> str:
        if self.cfg.env == "production":
            return "https://secure.payu.com/pl/standard/user/oauth/authorize"
        return "https://secure.snd.payu.com/pl/standard/user/oauth/authorize"

    def get_access_token(self) -> str:
        resp = requests.post(
            self._token_url(),
            data={
                "grant_type": "client_credentials",
                "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret,
            },
            timeout=15,
        )

        if resp.status_code >= 400:
            raise BadRequest(f"PayU OAuth error: {resp.status_code}")

        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise BadRequest("PayU OAuth: brak access_token")
        return token

    def create_order_for_invoice(self, invoice, *, amount, buyer_email: str | None = None) -> dict:
        token = self.get_access_token()

        ext_order_id = secrets.token_hex(16)

        buyer_email = buyer_email or getattr(invoice, "buyer_email", None) or ""

        # PayU expects amount in minor units (grosze)
        amount_gross = int(round(float(amount) * 100))

        payload = {
            "notifyUrl": self.cfg.notify_url,
            "customerIp": "127.0.0.1",
            "merchantPosId": self.cfg.pos_id,
            "description": f"Faktura {invoice.invoice_number}",
            "currencyCode": "PLN",
            "totalAmount": str(amount_gross),
            "extOrderId": ext_order_id,
            "buyer": {
                "email": buyer_email,
            },
            "products": [
                {
                    "name": f"Faktura {invoice.invoice_number}",
                    "unitPrice": str(amount_gross),
                    "quantity": "1",
                }
            ],
        }

        # Remove notifyUrl if not configured (PayU will still accept, but webhook won't work)
        if not payload.get("notifyUrl"):
            payload.pop("notifyUrl", None)

        url = f"{self._base_url()}/api/v2_1/orders"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )

        # PayU often returns 302 with Location redirect to payment page.
        if resp.status_code not in (200, 201, 302):
            raise BadRequest(f"PayU create order error: {resp.status_code}: {resp.text[:200]}")

        # When 302, PayU may still include JSON body.
        try:
            data = resp.json()
        except Exception:
            data = {}

        # Attempt to capture redirect URI
        redirect_uri = data.get("redirectUri") or resp.headers.get("Location")

        order_obj = data.get("order") or {}

        return {
            "extOrderId": ext_order_id,
            "orderId": data.get("orderId") or order_obj.get("orderId"),
            "status": data.get("status") or order_obj.get("status"),
            "redirectUri": redirect_uri,
        }

    def verify_notification(self, *, raw_body: bytes | None, signature_header: str | None) -> None:
        # PayU sends header like: 'sender=checkout;signature=...;algorithm=MD5;content=DOCUMENT'
        if not signature_header:
            raise BadRequest("Brak nagłówka OpenPayU-Signature")

        if not raw_body:
            raise BadRequest("Brak body do weryfikacji podpisu")

        parts = {}
        for chunk in signature_header.split(";"):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                parts[k.strip()] = v.strip()

        signature = parts.get("signature")
        algorithm = (parts.get("algorithm") or "").upper()

        if not signature:
            raise BadRequest("OpenPayU-Signature: brak signature")

        # Minimal verification: MD5(body + second_key)
        # (Exact rules can vary by PayU product; adjust if needed.)
        if algorithm and algorithm != "MD5":
            raise BadRequest(f"OpenPayU-Signature: nieobsługiwany algorithm={algorithm}")

        expected = hashlib.md5(raw_body + self.cfg.second_key.encode("utf-8")).hexdigest()

        if expected != signature:
            raise BadRequest("PayU signature mismatch")

"""Settings services.

Provides DB-backed configuration with fallback to Flask config.
"""

from __future__ import annotations

import os

from flask import current_app, g

from app.extensions import db
from app.settings.models import Setting


COMPANY_FIELD_TO_KEY = {
    "name": "COMPANY_NAME",
    "address": "COMPANY_ADDRESS",
    "nip": "COMPANY_NIP",
    "phone": "COMPANY_PHONE",
    "email": "COMPANY_EMAIL",
    "bank": "COMPANY_BANK",
    "account": "COMPANY_ACCOUNT",
}

INVOICE_FIELD_TO_KEY = {
    "prefix": "INVOICE_PREFIX",
    "deposit_prefix": "INVOICE_DEPOSIT_PREFIX",
    "correction_prefix": "INVOICE_CORRECTION_PREFIX",
    "year_format": "INVOICE_YEAR_FORMAT",
    "vat_rate": "INVOICE_VAT_RATE",
    "vat_exempt": "INVOICE_VAT_EXEMPT",
}

BRANDING_FIELD_TO_KEY = {
    "name": "CRM_NAME",
    "logo_path": "CRM_LOGO_PATH",
    "gallery_logo_path": "GALLERY_LOGO_PATH",
}

WATERMARK_FIELD_TO_KEY = {
    "text": "WATERMARK_TEXT",
}

CANVA_FIELD_TO_KEY = {
    "access_token": "CANVA_ACCESS_TOKEN",
    "client_id": "CANVA_CLIENT_ID",
    "client_secret": "CANVA_CLIENT_SECRET",
}


def get_watermark_text() -> str:
    """Return watermark text (DB override), with sensible fallbacks."""
    raw = str(get_setting(WATERMARK_FIELD_TO_KEY["text"], "") or "").strip()
    if raw:
        return raw

    # Prefer CRM name if set.
    crm = str(get_setting(BRANDING_FIELD_TO_KEY["name"], "") or "").strip()
    if crm:
        return crm

    company = str(get_setting("COMPANY_NAME", "") or "").strip()
    if company:
        return company

    return get_default_brand_name()


def get_default_brand_name() -> str:
    return "EcoShot CRM"


def get_branding() -> dict:
    """Return branding snapshot suitable for public UI."""
    name = str(get_setting(BRANDING_FIELD_TO_KEY["name"], get_default_brand_name()) or "").strip()
    if not name:
        name = get_default_brand_name()

    logo_path = get_setting(BRANDING_FIELD_TO_KEY["logo_path"], None)
    has_logo = bool(logo_path)

    gallery_logo_path = get_setting(BRANDING_FIELD_TO_KEY["gallery_logo_path"], None)
    has_gallery_logo = bool(gallery_logo_path)

    logo_url = None
    if has_logo:
        # Cache-busting based on db stored value (path changes when file is replaced).
        logo_url = f"/api/settings/branding/logo?v={os.path.basename(str(logo_path))}"

    gallery_logo_url = None
    if has_gallery_logo:
        gallery_logo_url = f"/api/settings/branding/gallery-logo?v={os.path.basename(str(gallery_logo_path))}"

    return {
        "name": name,
        "has_logo": has_logo,
        "logo_url": logo_url,
        "has_gallery_logo": has_gallery_logo,
        "gallery_logo_url": gallery_logo_url,
    }


def _get_upload_base_dir() -> str:
    base = current_app.config.get("UPLOAD_FOLDER") or "uploads"
    return os.path.abspath(base)


def get_brand_logo_abs_path() -> str | None:
    rel = get_setting(BRANDING_FIELD_TO_KEY["logo_path"], None)
    if not rel:
        return None

    base = _get_upload_base_dir()
    abs_path = os.path.abspath(str(rel))

    # Support storing either absolute or relative path.
    if not os.path.isabs(str(rel)):
        abs_path = os.path.abspath(os.path.join(base, str(rel)))

    # Prevent path traversal.
    if not abs_path.startswith(base + os.sep) and abs_path != base:
        return None

    return abs_path


def get_gallery_logo_abs_path() -> str | None:
    rel = get_setting(BRANDING_FIELD_TO_KEY["gallery_logo_path"], None)
    if not rel:
        return None

    base = _get_upload_base_dir()
    abs_path = os.path.abspath(str(rel))

    # Support storing either absolute or relative path.
    if not os.path.isabs(str(rel)):
        abs_path = os.path.abspath(os.path.join(base, str(rel)))

    # Prevent path traversal.
    if not abs_path.startswith(base + os.sep) and abs_path != base:
        return None

    return abs_path


def _parse_bool_setting(value) -> bool:
    if value is None:
        return False
    raw = str(value).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _load_db_settings_map() -> dict[str, str | None]:
    cached = getattr(g, "_settings_db_cache", None)
    if cached is not None:
        return cached

    try:
        rows = Setting.query.all()
        cached = {row.key: row.value for row in rows}
    except Exception:
        cached = {}

    g._settings_db_cache = cached
    return cached


def get_setting(key: str, default=None):
    """Return a single setting using DB override (if present), else config fallback."""
    value = _load_db_settings_map().get(key)
    if value is not None:
        return value
    return current_app.config.get(key, default)


def set_setting(key: str, value: str | None) -> Setting:
    """Upsert a single setting key/value in DB."""
    row = Setting.query.filter_by(key=key).first()
    if row is None:
        row = Setting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    return row


def get_settings_snapshot() -> dict:
    """Return settings snapshot (safe, admin-friendly)."""
    cfg = current_app.config

    def _is_set(v):
        return bool(v)

    company = {k: get_setting(key) for k, key in COMPANY_FIELD_TO_KEY.items()}
    invoice = {
        k: get_setting(key)
        for k, key in INVOICE_FIELD_TO_KEY.items()
        if k not in {"vat_exempt"}
    }
    # Provide typed/normalized invoice settings for UI.
    invoice["vat_rate"] = str(invoice.get("vat_rate") or get_setting("INVOICE_VAT_RATE", "23"))
    invoice["vat_exempt"] = _parse_bool_setting(get_setting("INVOICE_VAT_EXEMPT", "0"))

    return {
        "company": company,
        "invoice": invoice,
        "branding": get_branding(),
        "watermark": {
            "text": get_watermark_text(),
        },
        "uploads": {
            "upload_folder": cfg.get("UPLOAD_FOLDER"),
            "max_content_length": cfg.get("MAX_CONTENT_LENGTH"),
            "allowed_extensions": sorted(list(cfg.get("ALLOWED_EXTENSIONS") or [])),
        },
        "integrations": {
            "google_maps": {
                "api_key_set": _is_set(cfg.get("GOOGLE_MAPS_API_KEY")),
                "browser_api_key_set": _is_set(cfg.get("GOOGLE_MAPS_BROWSER_API_KEY")),
            },
            "payu": {
                "env": cfg.get("PAYU_ENV"),
                "pos_id_set": _is_set(cfg.get("PAYU_POS_ID")),
                "client_id_set": _is_set(cfg.get("PAYU_CLIENT_ID")),
                "client_secret_set": _is_set(cfg.get("PAYU_CLIENT_SECRET")),
                "second_key_set": _is_set(cfg.get("PAYU_SECOND_KEY")),
                "notify_url": cfg.get("PAYU_NOTIFY_URL"),
            },
            "canva": {
                "access_token_set": _is_set(get_setting(CANVA_FIELD_TO_KEY["access_token"], None)),
                "client_id_set": _is_set(get_setting(CANVA_FIELD_TO_KEY["client_id"], None)),
                "client_secret_set": _is_set(get_setting(CANVA_FIELD_TO_KEY["client_secret"], None)),
            },
        },
    }


def update_settings_from_payload(payload: dict) -> None:
    """Apply validated payload updates into DB."""
    company = payload.get("company") or {}
    invoice = payload.get("invoice") or {}
    branding = payload.get("branding") or {}
    watermark = payload.get("watermark") or {}
    integrations = payload.get("integrations") or {}
    canva = integrations.get("canva") or {}

    for field, key in COMPANY_FIELD_TO_KEY.items():
        if field in company:
            set_setting(key, company.get(field))

    for field, key in INVOICE_FIELD_TO_KEY.items():
        if field not in invoice:
            continue

        if field == "vat_exempt":
            set_setting(key, "1" if bool(invoice.get(field)) else "0")
            continue

        if field == "vat_rate":
            raw = invoice.get(field)
            if raw is None or raw == "":
                set_setting(key, None)
            else:
                set_setting(key, str(raw).strip())
            continue

        set_setting(key, invoice.get(field))

    # Branding name (logo is handled via upload endpoint)
    if "name" in branding:
        raw = branding.get("name")
        if raw is None or str(raw).strip() == "":
            set_setting(BRANDING_FIELD_TO_KEY["name"], None)
        else:
            set_setting(BRANDING_FIELD_TO_KEY["name"], str(raw).strip())

    if "text" in watermark:
        raw = watermark.get("text")
        if raw is None or str(raw).strip() == "":
            set_setting(WATERMARK_FIELD_TO_KEY["text"], None)
        else:
            set_setting(WATERMARK_FIELD_TO_KEY["text"], str(raw).strip())

    # Canva integration (stored in DB)
    for field, key in CANVA_FIELD_TO_KEY.items():
        if field not in canva:
            continue
        raw = canva.get(field)
        if raw is None or str(raw).strip() == "":
            set_setting(key, None)
        else:
            set_setting(key, str(raw).strip())

    db.session.commit()

    # Clear request cache so subsequent reads in the same request see new values.
    try:
        g._settings_db_cache = None
    except Exception:
        pass

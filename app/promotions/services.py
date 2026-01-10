"""Promotions business logic."""

from datetime import datetime

from sqlalchemy import func

from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.promotions.models import Promotion
from app.vouchers.models import Voucher


def _now():
    return datetime.utcnow()


_MM_TO_PX = 96.0 / 25.4


def _maybe_mm_to_px(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value) * _MM_TO_PX
    except Exception:
        return None


def _read_px_from_payload(data: dict, px_key: str, mm_key: str):
    if px_key in data:
        raw = data.get(px_key)
        return None if raw is None or str(raw).strip() == "" else raw
    if mm_key in data:
        return _maybe_mm_to_px(data.get(mm_key))
    return None


def has_active_promotion_for_type(promo_type: str) -> bool:
    if not promo_type:
        return False

    now = _now()
    return (
        db.session.query(Voucher.id)
        .join(Promotion, Promotion.id == Voucher.promotion_id)
        .filter(Promotion.promo_type == promo_type)
        .filter(Voucher.used_at.is_(None))
        .filter(Voucher.expires_at >= now)
        .first()
        is not None
    )


def get_promotion_by_id(promotion_id: int) -> Promotion:
    promo = db.session.get(Promotion, promotion_id)
    if not promo:
        raise NotFound(f"Promocja #{promotion_id} nie istnieje")
    return promo


def list_promotions(filters=None):
    query = Promotion.query

    if filters:
        if filters.get("promo_type"):
            query = query.filter_by(promo_type=filters["promo_type"])
        if filters.get("active_only") is True:
            now = _now()
            active_promo_ids = (
                db.session.query(Voucher.promotion_id)
                .filter(Voucher.used_at.is_(None))
                .filter(Voucher.expires_at >= now)
                .group_by(Voucher.promotion_id)
                .having(func.count(Voucher.id) > 0)
                .subquery()
            )
            query = query.filter(Promotion.id.in_(active_promo_ids))

    return query.order_by(Promotion.created_at.desc()).all()


def create_promotion(data: dict) -> Promotion:
    promo_type = (data.get("promo_type") or "").strip()
    if not promo_type:
        raise BadRequest("Typ promocji jest wymagany")

    try:
        duration_days = int(data.get("duration_days"))
    except Exception:
        raise BadRequest("Nieprawidłowa długość promocji")

    if duration_days <= 0:
        raise BadRequest("Długość promocji musi być dodatnia")

    promo = Promotion(
        promo_type=promo_type,
        value=data.get("value"),
        duration_days=duration_days,
        canva_project_url=(data.get("canva_project_url") or None),
        voucher_text_x_px=_read_px_from_payload(data, "voucher_text_x_px", "voucher_text_x_mm"),
        voucher_text_y_px=_read_px_from_payload(data, "voucher_text_y_px", "voucher_text_y_mm"),
        voucher_qr_x_px=_read_px_from_payload(data, "voucher_qr_x_px", "voucher_qr_x_mm"),
        voucher_qr_y_px=_read_px_from_payload(data, "voucher_qr_y_px", "voucher_qr_y_mm"),
        voucher_text_font_family=(data.get("voucher_text_font_family") or None),
        voucher_text_font_size_pt=data.get("voucher_text_font_size_pt"),
    )

    # Do NOT auto-activate. Activation starts when vouchers are generated.
    promo.activated_at = None
    promo.active_until = None

    db.session.add(promo)
    db.session.commit()
    return promo


def update_promotion(promotion_id: int, data: dict) -> Promotion:
    promo = get_promotion_by_id(promotion_id)

    # Rule: editing is blocked if any active promotion exists for this type.
    if has_active_promotion_for_type(promo.promo_type):
        raise BadRequest("Nie można edytować promocji: istnieje aktywna promocja tego typu")

    if "promo_type" in data and data["promo_type"] is not None:
        new_type = str(data["promo_type"]).strip()
        if not new_type:
            raise BadRequest("Typ promocji jest wymagany")
        # If type changes, enforce the same rule for the target type.
        if new_type != promo.promo_type and has_active_promotion_for_type(new_type):
            raise Conflict("Istnieje już aktywna promocja docelowego typu")
        promo.promo_type = new_type

    if "value" in data:
        promo.value = data.get("value")

    if "duration_days" in data and data.get("duration_days") is not None:
        try:
            promo.duration_days = int(data.get("duration_days"))
        except Exception:
            raise BadRequest("Nieprawidłowa długość promocji")
        if promo.duration_days <= 0:
            raise BadRequest("Długość promocji musi być dodatnia")

    if "canva_project_url" in data:
        raw = data.get("canva_project_url")
        promo.canva_project_url = None if raw is None or str(raw).strip() == "" else str(raw).strip()

    # Prefer px fields; accept legacy mm inputs and convert.
    if "voucher_text_x_px" in data or "voucher_text_x_mm" in data:
        promo.voucher_text_x_px = _read_px_from_payload(data, "voucher_text_x_px", "voucher_text_x_mm")
    if "voucher_text_y_px" in data or "voucher_text_y_mm" in data:
        promo.voucher_text_y_px = _read_px_from_payload(data, "voucher_text_y_px", "voucher_text_y_mm")
    if "voucher_qr_x_px" in data or "voucher_qr_x_mm" in data:
        promo.voucher_qr_x_px = _read_px_from_payload(data, "voucher_qr_x_px", "voucher_qr_x_mm")
    if "voucher_qr_y_px" in data or "voucher_qr_y_mm" in data:
        promo.voucher_qr_y_px = _read_px_from_payload(data, "voucher_qr_y_px", "voucher_qr_y_mm")

    if "voucher_text_font_family" in data:
        raw = data.get("voucher_text_font_family")
        promo.voucher_text_font_family = None if raw is None or str(raw).strip() == "" else str(raw).strip()
    if "voucher_text_font_size_pt" in data:
        promo.voucher_text_font_size_pt = data.get("voucher_text_font_size_pt")

    db.session.commit()
    return promo


def activate_promotion(promotion_id: int) -> Promotion:
    """Activate a promotion (intended to be called by voucher generation logic)."""
    promo = get_promotion_by_id(promotion_id)

    # Prevent multiple active promotions of the same type.
    if has_active_promotion_for_type(promo.promo_type):
        raise Conflict("Istnieje już aktywna promocja tego typu")

    promo.activate(_now())
    db.session.commit()
    return promo


def delete_promotion(promotion_id: int) -> None:
    promo = get_promotion_by_id(promotion_id)

    # Rule: deletion is blocked if any active promotion exists for this type.
    if has_active_promotion_for_type(promo.promo_type):
        raise BadRequest("Nie można usunąć promocji: istnieje aktywna promocja tego typu")

    db.session.delete(promo)
    db.session.commit()

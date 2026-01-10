"""Promotions REST API endpoints."""

import os
import uuid

from flask import Blueprint, jsonify, request, send_file
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.utils import secure_filename

from app.core.decorators import api_endpoint
from app.core.permissions import Permission
from app.promotions import services
from app.extensions import db
from app.promotions.schemas import (
    promotion_schema,
    promotions_schema,
    promotion_create_schema,
    promotion_update_schema,
)


promotions_bp = Blueprint("promotions", __name__)


def _upload_base_dir() -> str:
    from flask import current_app

    base = current_app.config.get("UPLOAD_FOLDER") or "uploads"
    return os.path.abspath(base)


def _voucher_templates_dir() -> str:
    path = os.path.join(_upload_base_dir(), "vouchers", "templates")
    os.makedirs(path, exist_ok=True)
    return path


@promotions_bp.route("", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_SETTINGS)
def list_promotions():
    promo_type = request.args.get("promo_type")
    active_only_raw = request.args.get("active_only")

    filters = {}
    if promo_type:
        filters["promo_type"] = promo_type
    if active_only_raw is not None and active_only_raw != "":
        filters["active_only"] = str(active_only_raw).lower() in ("true", "1", "yes")

    promos = services.list_promotions(filters=filters or None)
    return jsonify({"success": True, "data": promotions_schema.dump(promos)})


@promotions_bp.route("", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def create_promotion():
    payload = request.get_json() or {}
    errors = promotion_create_schema.validate(payload)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    promo = services.create_promotion(payload)
    return (
        jsonify({"success": True, "data": promotion_schema.dump(promo), "message": "Promocja utworzona"}),
        201,
    )


@promotions_bp.route("/<int:promotion_id>", methods=["PUT"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def update_promotion(promotion_id: int):
    payload = request.get_json() or {}
    errors = promotion_update_schema.validate(payload)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    promo = services.update_promotion(promotion_id, payload)
    return jsonify({"success": True, "data": promotion_schema.dump(promo), "message": "Promocja zaktualizowana"})


@promotions_bp.route("/<int:promotion_id>", methods=["DELETE"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def delete_promotion(promotion_id: int):
    services.delete_promotion(promotion_id)
    return jsonify({"success": True, "message": "Promocja usunięta"})


@promotions_bp.route("/<int:promotion_id>/voucher-template", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def upload_voucher_template(promotion_id: int):
    """Attach voucher template metadata/files to a promotion.

    Multipart form fields:
    - canva_project_url (optional)
    - (layout fields are configured via the JSON create/update endpoints)
    - front (optional file: png/jpg/jpeg)
    - back (optional file: png/jpg/jpeg)
    """
    promo = services.get_promotion_by_id(promotion_id)

    # URL update
    if "canva_project_url" in request.form:
        raw = request.form.get("canva_project_url")
        promo.canva_project_url = None if raw is None or str(raw).strip() == "" else str(raw).strip()

    def _save(which: str):
        f = request.files.get(which)
        if not f or not f.filename:
            return

        filename = secure_filename(f.filename)
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
        if ext not in {"png", "jpg", "jpeg"}:
            raise ValueError("Dozwolone formaty: PNG/JPG")

        out_name = f"promo_{promo.id}_{which}_{uuid.uuid4().hex}.{ext}"
        out_abs = os.path.join(_voucher_templates_dir(), out_name)
        f.save(out_abs)

        rel = os.path.join("vouchers", "templates", out_name)
        setattr(promo, f"voucher_bg_{'front' if which == 'front' else 'back'}_path", rel)

    try:
        _save("front")
        _save("back")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    db.session.commit()
    return jsonify({"success": True, "message": "Szablon vouchera zapisany"})


@promotions_bp.route("/<int:promotion_id>/voucher-template/<string:side>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_SETTINGS)
def get_voucher_template_file(promotion_id: int, side: str):
    """Serve voucher template image (front/back) for preview in admin UI."""
    if side not in {"front", "back"}:
        raise BadRequest("Nieprawidłowy parametr: side")

    promo = services.get_promotion_by_id(promotion_id)
    rel = promo.voucher_bg_front_path if side == "front" else promo.voucher_bg_back_path
    if not rel:
        raise NotFound("Brak pliku")

    base = _upload_base_dir()
    abs_path = os.path.abspath(os.path.join(base, rel))
    # Path traversal guard
    if not abs_path.startswith(base + os.sep):
        raise BadRequest("Nieprawidłowa ścieżka")
    if not os.path.exists(abs_path):
        raise NotFound("Brak pliku")

    return send_file(abs_path)

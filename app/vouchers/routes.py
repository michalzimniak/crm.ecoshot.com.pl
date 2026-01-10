"""Vouchers REST API endpoints."""

import os

from flask import Blueprint, jsonify, request, send_file, after_this_request
from werkzeug.exceptions import BadRequest

from app.core.decorators import api_endpoint
from app.core.permissions import Permission
from app.vouchers import services
from app.vouchers.schemas import vouchers_schema, voucher_generate_schema, voucher_lottery_send_schema
from app.vouchers.models import Voucher


vouchers_bp = Blueprint("vouchers", __name__)


def _get_voucher_or_404(voucher_id: int) -> Voucher:
    v = Voucher.query.get(int(voucher_id))
    if not v:
        raise BadRequest("Nie znaleziono vouchera")
    return v


@vouchers_bp.route("/validate", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_JOBS)
def validate_voucher():
    code = (request.args.get("code") or "").strip()
    job_id_raw = (request.args.get("job_id") or "").strip()
    total_raw = (request.args.get("total") or "").strip()

    job_id = None
    if job_id_raw:
        try:
            job_id = int(job_id_raw)
        except Exception:
            job_id = None

    total = None
    if total_raw:
        total = total_raw

    data = services.validate_voucher_code(code, job_id=job_id, total=total)
    return jsonify({"success": True, "data": data})


@vouchers_bp.route("", methods=["GET"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def list_vouchers():
    promotion_id = request.args.get("promotion_id")
    status = (request.args.get("status") or "").strip().lower()

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    if per_page <= 0:
        per_page = 50
    if per_page > 200:
        per_page = 200

    query = Voucher.query
    if promotion_id:
        try:
            query = query.filter(Voucher.promotion_id == int(promotion_id))
        except Exception:
            pass

    now = services._now()
    if status == "unused":
        query = query.filter(Voucher.used_at.is_(None)).filter(Voucher.expires_at >= now)
    elif status == "used":
        query = query.filter(Voucher.used_at.isnot(None))
    elif status == "expired":
        query = query.filter(Voucher.used_at.is_(None)).filter(Voucher.expires_at < now)

    query = query.order_by(Voucher.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "success": True,
            "data": vouchers_schema.dump(pagination.items),
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
                "total": pagination.total,
            },
        }
    )


@vouchers_bp.route("/generate", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def generate_vouchers_pdf():
    payload = request.get_json() or {}
    errors = voucher_generate_schema.validate(payload)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    promotion_id = int(payload["promotion_id"])
    count = int(payload["count"])

    vouchers = services.generate_vouchers(promotion_id, count)
    promo = vouchers[0].promotion if vouchers else None
    if not promo:
        return jsonify({"success": False, "error": "Nie udało się wygenerować voucherów"}), 400

    pdf_path, download_name = services.build_vouchers_pdf(promo, vouchers)

    @after_this_request
    def _cleanup(resp):
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        return resp

    return send_file(pdf_path, as_attachment=True, download_name=download_name)


@vouchers_bp.route("/<int:voucher_id>/pdf", methods=["GET"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def download_single_voucher_pdf(voucher_id: int):
    v = _get_voucher_or_404(voucher_id)
    if not getattr(v, "is_valid", False):
        raise BadRequest("Można wygenerować PDF tylko dla ważnego (niewykorzystanego) vouchera")

    promo = v.promotion
    if not promo:
        raise BadRequest("Voucher nie ma poprawnej promocji")

    pdf_path, download_name = services.build_vouchers_pdf(promo, [v])

    @after_this_request
    def _cleanup(resp):
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        return resp

    return send_file(pdf_path, as_attachment=True, download_name=download_name)


@vouchers_bp.route("/<int:voucher_id>/png", methods=["GET"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def download_single_voucher_png(voucher_id: int):
    v = _get_voucher_or_404(voucher_id)
    if not getattr(v, "is_valid", False):
        raise BadRequest("Można wygenerować PNG tylko dla ważnego (niewykorzystanego) vouchera")

    promo = v.promotion
    if not promo:
        raise BadRequest("Voucher nie ma poprawnej promocji")

    zip_path, download_name = services.build_voucher_png_zip(promo, v)

    @after_this_request
    def _cleanup(resp):
        try:
            os.remove(zip_path)
        except Exception:
            pass
        return resp

    return send_file(zip_path, as_attachment=True, download_name=download_name)


@vouchers_bp.route("/lottery/send", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def send_voucher_lottery():
    payload = request.get_json() or {}
    errors = voucher_lottery_send_schema.validate(payload)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    promotion_id = payload.get("promotion_id")
    if promotion_id is not None and str(promotion_id).strip() != "":
        try:
            promotion_id = int(promotion_id)
        except Exception:
            promotion_id = None
    else:
        promotion_id = None

    count = int(payload["count"])
    result = services.send_voucher_lottery(promotion_id=promotion_id, count=count)
    return jsonify({"success": True, "data": result})

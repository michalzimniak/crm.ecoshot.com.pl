"""Consents REST API endpoints.

Handles image publication consents.
"""

from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, request, send_file

from app.consents import services
from app.consents.schemas import (
    consent_create_schema,
    consent_grant_schema,
    consent_revoke_schema,
    consent_schema,
    consents_schema,
)
from app.core.decorators import api_endpoint, public_endpoint
from app.core.permissions import Permission
from app.settings.services import get_setting
from app.jobs.services import get_job_by_id

consents_bp = Blueprint("consents", __name__)


@consents_bp.route("/templates/<string:consent_type>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONSENTS)
def get_consent_template(consent_type: str):
    """Return default consent text template filled with company config."""
    allowed = {"image_publication", "data_processing"}
    if consent_type not in allowed:
        return jsonify({"success": False, "error": "Nieznany typ zgody"}), 400

    company_name = get_setting("COMPANY_NAME", "")

    customer_type = None
    job_id = request.args.get("job_id")
    if job_id:
        try:
            job = get_job_by_id(int(job_id))
            customer = getattr(job, "customer", None)
            customer_type = getattr(customer, "customer_type", None)
        except Exception:
            customer_type = None

    if consent_type == "image_publication":
        text = services.get_default_image_publication_consent_text(
            company_name,
            customer_type=customer_type,
        )
    else:
        text = services.get_default_data_processing_consent_text(
            company_name=company_name,
            company_address=get_setting("COMPANY_ADDRESS", ""),
            company_nip=get_setting("COMPANY_NIP", ""),
            company_email=get_setting("COMPANY_EMAIL", ""),
        )

    return jsonify({"success": True, "data": {"consent_type": consent_type, "consent_text": text}})


@consents_bp.route("", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONSENTS)
def get_consents():
    filters = {}

    if request.args.get("job_id"):
        filters["job_id"] = int(request.args.get("job_id"))
    if request.args.get("consent_type"):
        filters["consent_type"] = request.args.get("consent_type")
    if request.args.get("status"):
        # status: granted|revoked|pending
        filters["status"] = request.args.get("status")

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    result = services.get_all_consents(filters, page, per_page)

    return jsonify(
        {
            "success": True,
            "data": consents_schema.dump(result["items"]),
            "pagination": {
                "page": result["page"],
                "per_page": result["per_page"],
                "pages": result["pages"],
                "total": result["total"],
            },
        }
    )


@consents_bp.route("", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_CONSENTS)
def create_consent():
    data = request.get_json() or {}

    errors = consent_create_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    consent = services.create_consent(data)
    return (
        jsonify(
            {
                "success": True,
                "data": consent_schema.dump(consent),
                "message": "Zgoda utworzona",
            }
        ),
        201,
    )


@consents_bp.route("/<int:consent_id>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONSENTS)
def get_consent(consent_id):
    consent = services.get_consent_by_id(consent_id)
    return jsonify({"success": True, "data": consent_schema.dump(consent)})


@consents_bp.route("/job/<int:job_id>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONSENTS)
def get_consents_by_job(job_id):
    consents = services.get_consents_by_job_id(job_id)
    return jsonify({"success": True, "data": consents_schema.dump(consents)})


@consents_bp.route("/<int:consent_id>/pdf", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONSENTS)
def download_consent_pdf(consent_id):
    consent = services.get_consent_by_id(consent_id)

    needs_regen = not consent.pdf_path or not os.path.exists(consent.pdf_path)
    if not needs_regen:
        try:
            with open(consent.pdf_path, "rb") as f:
                header = f.read(4)
            if header != b"%PDF":
                needs_regen = True
        except OSError:
            needs_regen = True

    if needs_regen:
        services.generate_consent_pdf(consent)

    if not consent.pdf_path or not os.path.exists(consent.pdf_path):
        return jsonify({"success": False, "error": "Brak pliku PDF"}), 404

    return send_file(
        consent.pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"zgoda_{consent.id}.pdf",
    )


@consents_bp.route("/<int:consent_id>/signed-scan", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_CONSENTS)
def upload_signed_scan(consent_id):
    if "file" not in request.files:
        return jsonify({"success": False, "error": "Brak pliku"}), 400

    consent = services.upload_signed_scan(consent_id, request.files["file"])
    return jsonify(
        {
            "success": True,
            "data": consent_schema.dump(consent),
            "message": "Skan podpisanej zgody zapisany (zgoda udzielona)",
        }
    )


@consents_bp.route("/<int:consent_id>/signed-scan", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONSENTS)
def download_signed_scan(consent_id):
    consent = services.get_consent_by_id(consent_id)

    if not consent.signed_scan_path or not os.path.exists(consent.signed_scan_path):
        return jsonify({"success": False, "error": "Brak wgranego skanu"}), 404

    download_name = consent.signed_scan_original_filename or os.path.basename(consent.signed_scan_path)

    return send_file(
        consent.signed_scan_path,
        mimetype=consent.signed_scan_mime_type or None,
        as_attachment=True,
        download_name=download_name,
    )


@consents_bp.route("/<int:consent_id>/grant", methods=["POST"])
@public_endpoint
def grant_consent(consent_id):
    data = request.get_json() or {}

    errors = consent_grant_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    ip_address = request.remote_addr
    consent = services.grant_consent(consent_id, data["signature_data"], ip_address)

    return jsonify(
        {"success": True, "data": consent_schema.dump(consent), "message": "Zgoda udzielona"}
    )


@consents_bp.route("/<int:consent_id>/revoke", methods=["POST"])
@public_endpoint
def revoke_consent(consent_id):
    data = request.get_json() or {}

    errors = consent_revoke_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    consent = services.revoke_consent(consent_id, data["reason"])

    return jsonify(
        {"success": True, "data": consent_schema.dump(consent), "message": "Zgoda wycofana"}
    )


@consents_bp.route("/<int:consent_id>/send", methods=["POST"])
@api_endpoint(permission=Permission.MANAGE_CONSENTS)
def send_consent(consent_id):
    consent = services.send_consent(consent_id)

    return jsonify(
        {"success": True, "data": consent_schema.dump(consent), "message": "Zgoda wysłana"}
    )

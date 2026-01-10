"""Contracts REST API endpoints.

Handles contract generation, PDF download, and digital signatures.
"""

import os

from flask import Blueprint, jsonify, request, send_file
from marshmallow import ValidationError

from app.contracts import services
from app.contracts.schemas import (
    contract_create_schema,
    contract_schema,
    contracts_schema,
    contract_sign_schema,
    contract_status_update_schema,
    contract_update_schema,
)
from app.core.decorators import api_endpoint, public_endpoint
from app.core.permissions import Permission

contracts_bp = Blueprint("contracts", __name__)


@contracts_bp.route("", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONTRACTS)
def get_contracts():
    """Get all contracts with filters and pagination."""
    filters = {}

    if request.args.get("status"):
        filters["status"] = request.args.get("status")
    if request.args.get("job_id"):
        filters["job_id"] = int(request.args.get("job_id"))
    if request.args.get("customer_id"):
        filters["customer_id"] = int(request.args.get("customer_id"))

    search = request.args.get("search")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    result = services.get_all_contracts(filters, search, page, per_page)

    return jsonify(
        {
            "success": True,
            "data": contracts_schema.dump(result["items"]),
            "pagination": {
                "page": result["page"],
                "per_page": result["per_page"],
                "pages": result["pages"],
                "total": result["total"],
            },
        }
    )


@contracts_bp.route("", methods=["POST"])
@api_endpoint(permission=Permission.CREATE_CONTRACT)
def create_contract():
    """Create new contract for job."""
    data = request.get_json()

    errors = contract_create_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    contract = services.create_contract(data)

    return (
        jsonify(
            {
                "success": True,
                "data": contract_schema.dump(contract),
                "message": "Umowa utworzona",
            }
        ),
        201,
    )


@contracts_bp.route("/<int:contract_id>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONTRACTS)
def get_contract(contract_id):
    """Get contract by ID."""
    contract = services.get_contract_by_id(contract_id)
    return jsonify({"success": True, "data": contract_schema.dump(contract)})


@contracts_bp.route("/job/<int:job_id>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONTRACTS)
def get_contract_by_job(job_id):
    """Get contract for job."""
    contract = services.get_contract_by_job_id(job_id)
    return jsonify({"success": True, "data": contract_schema.dump(contract)})


@contracts_bp.route("/<int:contract_id>", methods=["PUT"])
@api_endpoint(permission=Permission.CREATE_CONTRACT)
def update_contract(contract_id):
    """Update contract."""
    payload = request.get_json() or {}

    try:
        data = contract_update_schema.load(payload, partial=True)
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 400

    contract = services.update_contract(contract_id, data)
    return jsonify(
        {
            "success": True,
            "data": contract_schema.dump(contract),
            "message": "Umowa zaktualizowana",
        }
    )


@contracts_bp.route("/<int:contract_id>/sign", methods=["POST"])
@public_endpoint
def sign_contract(contract_id):
    """Sign contract (public endpoint for client)."""
    data = request.get_json()

    errors = contract_sign_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    ip_address = request.remote_addr
    contract = services.sign_contract(contract_id, data["signature_data"], ip_address)

    return jsonify(
        {
            "success": True,
            "data": contract_schema.dump(contract),
            "message": "Umowa podpisana",
        }
    )


@contracts_bp.route("/<int:contract_id>/send", methods=["POST"])
@api_endpoint(permission=Permission.CREATE_CONTRACT)
def send_contract(contract_id):
    """Send contract to client."""
    contract = services.send_contract(contract_id)
    return jsonify(
        {
            "success": True,
            "data": contract_schema.dump(contract),
            "message": "Umowa wysłana",
        }
    )


@contracts_bp.route("/<int:contract_id>/status", methods=["PUT"])
@api_endpoint(permission=Permission.CREATE_CONTRACT)
def update_status(contract_id):
    """Update contract status."""
    payload = request.get_json() or {}

    try:
        data = contract_status_update_schema.load(payload)
    except ValidationError as err:
        return jsonify({"success": False, "errors": err.messages}), 400

    contract = services.get_contract_by_id(contract_id)
    new_status = data["status"]

    # When marking as signed in CRM, allow either a digital signature or an uploaded scan.
    if new_status == "signed":
        if not contract.signature_data and not contract.signed_scan_path:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Nie można oznaczyć jako podpisanej bez podpisu elektronicznego lub skanu podpisanej umowy",
                    }
                ),
                400,
            )
        if not contract.signed_at:
            from datetime import datetime

            contract.signed_at = datetime.utcnow()

    contract.status = new_status

    from app.extensions import db

    db.session.commit()
    return jsonify(
        {
            "success": True,
            "data": contract_schema.dump(contract),
            "message": "Status zaktualizowany",
        }
    )


@contracts_bp.route("/<int:contract_id>/pdf", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONTRACTS)
def download_pdf(contract_id):
    """Download contract PDF."""
    contract = services.get_contract_by_id(contract_id)

    if not contract.pdf_path:
        return jsonify({"success": False, "error": "Brak pliku PDF"}), 404

    needs_regen = not os.path.exists(contract.pdf_path)
    if not needs_regen:
        # If an old placeholder file exists, it won't be a valid PDF.
        try:
            with open(contract.pdf_path, "rb") as f:
                header = f.read(4)
            if header != b"%PDF":
                needs_regen = True
        except OSError:
            needs_regen = True

    if needs_regen:
        # Safe regeneration only for non-signed contracts.
        if contract.status != "signed":
            services.generate_contract_pdf(contract)

        if not contract.pdf_path or not os.path.exists(contract.pdf_path):
            return jsonify({"success": False, "error": "Brak pliku PDF"}), 404

    return send_file(
        contract.pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{contract.contract_number.replace('/', '_')}.pdf",
    )


@contracts_bp.route("/<int:contract_id>/signed-scan", methods=["POST"])
@api_endpoint(permission=Permission.CREATE_CONTRACT)
def upload_signed_scan(contract_id):
    """Upload signed contract scan/photo for archiving."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "Brak pliku"}), 400

    contract = services.upload_signed_scan(contract_id, request.files["file"])
    return jsonify(
        {
            "success": True,
            "data": contract_schema.dump(contract),
            "message": "Skan podpisanej umowy zapisany",
        }
    )


@contracts_bp.route("/<int:contract_id>/signed-scan", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_CONTRACTS)
def download_signed_scan(contract_id):
    """Download signed contract scan/photo."""
    contract = services.get_contract_by_id(contract_id)

    if not contract.signed_scan_path:
        return jsonify({"success": False, "error": "Brak skanu podpisanej umowy"}), 404

    if not os.path.exists(contract.signed_scan_path):
        return jsonify({"success": False, "error": "Brak skanu podpisanej umowy"}), 404

    download_name = contract.signed_scan_original_filename or f"signed_contract_{contract.id}"
    return send_file(
        contract.signed_scan_path,
        mimetype=contract.signed_scan_mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=download_name,
    )
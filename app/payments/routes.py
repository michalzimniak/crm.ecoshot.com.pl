"""Payments REST API endpoints.

Manual payments + PayU initiation + PayU webhook.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.core.decorators import api_endpoint, public_endpoint
from app.core.permissions import Permission
from app.payments import services
from app.payments.schemas import (
    payment_complete_schema,
    payment_create_schema,
    payment_refund_schema,
    payment_schema,
    payments_schema,
    payu_create_order_schema,
)

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_PAYMENTS)
def get_payments():
    """Get all payments with filters and pagination."""
    filters: dict = {}

    if request.args.get("status"):
        filters["status"] = request.args.get("status")
    if request.args.get("payment_method"):
        filters["payment_method"] = request.args.get("payment_method")
    if request.args.get("source"):
        filters["source"] = request.args.get("source")
    if request.args.get("kind"):
        filters["kind"] = request.args.get("kind")
    if request.args.get("invoice_id"):
        filters["invoice_id"] = int(request.args.get("invoice_id"))
    if request.args.get("job_id"):
        filters["job_id"] = int(request.args.get("job_id"))

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    result = services.get_all_payments(filters, page=page, per_page=per_page)

    return jsonify(
        {
            "success": True,
            "data": payments_schema.dump(result["items"]),
            "pagination": {
                "page": result["page"],
                "per_page": result["per_page"],
                "pages": result["pages"],
                "total": result["total"],
            },
        }
    )


@payments_bp.route("/<int:payment_id>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_PAYMENTS)
def get_payment(payment_id: int):
    payment = services.get_payment_by_id(payment_id)
    return jsonify({"success": True, "data": payment_schema.dump(payment)})


@payments_bp.route("", methods=["POST"])
@api_endpoint(permission=Permission.CREATE_PAYMENT)
def create_payment():
    data = request.get_json() or {}

    errors = payment_create_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    payment = services.create_payment(data)

    return (
        jsonify(
            {
                "success": True,
                "data": payment_schema.dump(payment),
                "message": "Płatność utworzona",
            }
        ),
        201,
    )


@payments_bp.route("/<int:payment_id>/complete", methods=["POST"])
@api_endpoint(permission=Permission.EDIT_PAYMENT)
def complete_payment(payment_id: int):
    data = request.get_json() or {}

    errors = payment_complete_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    payment = services.complete_payment(payment_id, transaction_id=data.get("transaction_id"))

    return jsonify(
        {
            "success": True,
            "data": payment_schema.dump(payment),
            "message": "Płatność została zrealizowana",
        }
    )


@payments_bp.route("/<int:payment_id>/refund", methods=["POST"])
@api_endpoint(permission=Permission.EDIT_PAYMENT)
def refund_payment(payment_id: int):
    data = request.get_json() or {}

    errors = payment_refund_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    payment = services.refund_payment(payment_id, data["reason"])

    return jsonify(
        {
            "success": True,
            "data": payment_schema.dump(payment),
            "message": "Zwrot zrealizowany",
        }
    )


@payments_bp.route("/<int:payment_id>", methods=["DELETE"])
@api_endpoint(permission=Permission.DELETE_PAYMENT)
def delete_payment(payment_id: int):
    services.delete_payment(payment_id)
    return jsonify({"success": True, "message": "Płatność anulowana"})


@payments_bp.route("/payu/orders", methods=["POST"])
@api_endpoint(permission=Permission.CREATE_PAYMENT)
def payu_create_order():
    """Create a PayU order for an invoice and return redirectUrl."""
    data = request.get_json() or {}

    errors = payu_create_order_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    result = services.payu_create_order_for_invoice(
        invoice_id=int(data["invoice_id"]),
        buyer_email=data.get("buyer_email"),
    )

    return jsonify({"success": True, "data": result, "message": "Utworzono płatność PayU"})


@payments_bp.route("/payu/notify", methods=["POST"])
@public_endpoint
def payu_notify():
    """PayU notification webhook (public)."""
    raw_body = request.get_data() or b""
    payload = request.get_json(silent=True) or {}
    signature_header = request.headers.get("OpenPayu-Signature")

    updated = services.payu_handle_notification(payload, raw_body=raw_body, signature_header=signature_header)

    return jsonify({"success": True, "data": updated})

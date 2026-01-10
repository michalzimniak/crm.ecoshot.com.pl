"""
Invoices REST API endpoints.
Handles invoice generation and management.
"""

from flask import Blueprint, request, jsonify, send_file
from marshmallow import ValidationError
from app.core.decorators import api_endpoint
from app.core.permissions import Permission
from app.invoices import services
from app.invoices.schemas import (
    invoice_schema, invoices_schema,
    invoice_create_schema, invoice_update_schema,
    invoice_status_update_schema, invoice_item_schema
)

invoices_bp = Blueprint('invoices', __name__)


@invoices_bp.route('', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_INVOICES)
def get_invoices():
    """Get all invoices with filters and pagination."""
    filters = {}
    
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('payment_status'):
        filters['payment_status'] = request.args.get('payment_status')
    if request.args.get('job_id'):
        filters['job_id'] = int(request.args.get('job_id'))
    if request.args.get('customer_id'):
        filters['customer_id'] = int(request.args.get('customer_id'))
    if request.args.get('invoice_type'):
        filters['invoice_type'] = request.args.get('invoice_type')
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    result = services.get_all_invoices(filters, page, per_page)
    
    return jsonify({
        'success': True,
        'data': invoices_schema.dump(result['items']),
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'pages': result['pages'],
            'total': result['total']
        }
    })


@invoices_bp.route('/<int:invoice_id>', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_INVOICES)
def get_invoice(invoice_id):
    """Get invoice by ID."""
    invoice = services.get_invoice_by_id(invoice_id)
    
    return jsonify({
        'success': True,
        'data': invoice_schema.dump(invoice)
    })


@invoices_bp.route('', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_INVOICE)
def create_invoice():
    """Create new invoice for job."""
    data = request.get_json()
    
    # Deserialize + validate
    try:
        data = invoice_create_schema.load(data or {})
    except ValidationError as err:
        return jsonify({'success': False, 'errors': err.messages}), 400
    
    # Create
    invoice = services.create_invoice(data)
    
    return jsonify({
        'success': True,
        'data': invoice_schema.dump(invoice),
        'message': 'Faktura utworzona'
    }), 201


@invoices_bp.route('/deposit', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_INVOICE)
def create_deposit_invoice():
    """Create deposit invoice for a job (idempotent)."""
    data = request.get_json() or {}
    job_id = data.get('job_id')
    if not job_id:
        return jsonify({'success': False, 'error': 'job_id is required'}), 400

    invoice = services.create_deposit_invoice_for_job(int(job_id))
    return jsonify({'success': True, 'data': invoice_schema.dump(invoice)}), 201


@invoices_bp.route('/final', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_INVOICE)
def create_final_invoice():
    """Create final VAT invoice for a job (idempotent)."""
    data = request.get_json() or {}
    job_id = data.get('job_id')
    if not job_id:
        return jsonify({'success': False, 'error': 'job_id is required'}), 400

    invoice = services.create_final_invoice_for_job(int(job_id))
    return jsonify({'success': True, 'data': invoice_schema.dump(invoice)}), 201


@invoices_bp.route('/<int:invoice_id>/correction', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_INVOICE)
def create_invoice_correction(invoice_id):
    """Create correction invoice linked to an existing invoice."""
    data = request.get_json() or {}
    invoice = services.create_correction_invoice(invoice_id, data)
    return jsonify({'success': True, 'data': invoice_schema.dump(invoice)}), 201


@invoices_bp.route('/<int:invoice_id>', methods=['PUT'])
@api_endpoint(permission=Permission.EDIT_INVOICE)
def update_invoice(invoice_id):
    """Update invoice."""
    data = request.get_json()
    
    # Deserialize + validate
    try:
        data = invoice_update_schema.load(data or {}, partial=True)
    except ValidationError as err:
        return jsonify({'success': False, 'errors': err.messages}), 400
    
    # Update
    invoice = services.update_invoice(invoice_id, data)
    
    return jsonify({
        'success': True,
        'data': invoice_schema.dump(invoice),
        'message': 'Faktura zaktualizowana'
    })


@invoices_bp.route('/<int:invoice_id>/status', methods=['PUT'])
@api_endpoint(permission=Permission.EDIT_INVOICE)
def update_invoice_status(invoice_id):
    """Update invoice status."""
    data = request.get_json()
    
    # Validate
    errors = invoice_status_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Update
    invoice = services.update_invoice_status(invoice_id, data['status'])
    
    return jsonify({
        'success': True,
        'data': invoice_schema.dump(invoice),
        'message': 'Status faktury zaktualizowany'
    })


@invoices_bp.route('/<int:invoice_id>/send', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_INVOICE)
def send_invoice(invoice_id):
    """Send invoice to client."""
    invoice = services.send_invoice(invoice_id)
    
    return jsonify({
        'success': True,
        'data': invoice_schema.dump(invoice),
        'message': 'Faktura wysłana'
    })


@invoices_bp.route('/<int:invoice_id>/pdf', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_INVOICES)
def download_pdf(invoice_id):
    """Download invoice PDF."""
    invoice = services.get_invoice_by_id(invoice_id)
    # Safe/idempotent: won't overwrite an existing valid PDF.
    pdf_path = services.generate_invoice_pdf(invoice)
    
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{invoice.invoice_number.replace('/', '_')}.pdf"
    )


@invoices_bp.route('/<int:invoice_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.DELETE_INVOICE)
def delete_invoice(invoice_id):
    """Delete invoice (cancel)."""
    services.delete_invoice(invoice_id)
    
    return jsonify({
        'success': True,
        'message': 'Faktura anulowana'
    })

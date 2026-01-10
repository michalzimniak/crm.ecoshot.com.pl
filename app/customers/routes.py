"""Customers REST API endpoints.
Handles customer CRUD operations.
"""

from flask import Blueprint, jsonify, request
from marshmallow import ValidationError

from app.core.decorators import api_endpoint
from app.core.permissions import Permission
from app.customers import services
from app.customers.schemas import (
    customer_create_schema,
    customer_schema,
    customer_update_schema,
    customers_schema,
)

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_CUSTOMERS)
def get_customers():
    """Get all customers with filters and pagination."""
    filters = {}

    if request.args.get('customer_type'):
        filters['customer_type'] = request.args.get('customer_type')
    if request.args.get('is_active'):
        filters['is_active'] = request.args.get('is_active') == 'true'

    search = request.args.get('search')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    result = services.get_all_customers(filters, search, page, per_page)

    return jsonify(
        {
            'success': True,
            'data': customers_schema.dump(result['items']),
            'pagination': {
                'page': result['page'],
                'per_page': result['per_page'],
                'pages': result['pages'],
                'total': result['total'],
            },
        }
    )


@customers_bp.route('/<int:customer_id>', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_CUSTOMERS)
def get_customer(customer_id):
    """Get customer by ID."""
    customer = services.get_customer_by_id(customer_id)

    return jsonify({'success': True, 'data': customer_schema.dump(customer)})


@customers_bp.route('', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_CUSTOMER)
def create_customer():
    """Create new customer."""
    data = request.get_json() or {}

    try:
        payload = customer_create_schema.load(data)
    except ValidationError as err:
        return jsonify({'success': False, 'errors': err.messages}), 400

    customer = services.create_customer(payload)

    return (
        jsonify(
            {
                'success': True,
                'data': customer_schema.dump(customer),
                'message': 'Klient utworzony',
            }
        ),
        201,
    )


@customers_bp.route('/<int:customer_id>', methods=['PUT'])
@api_endpoint(permission=Permission.EDIT_CUSTOMER)
def update_customer(customer_id):
    """Update customer."""
    data = request.get_json() or {}

    try:
        payload = customer_update_schema.load(data, partial=True)
    except ValidationError as err:
        return jsonify({'success': False, 'errors': err.messages}), 400

    customer = services.update_customer(customer_id, payload)

    return jsonify(
        {
            'success': True,
            'data': customer_schema.dump(customer),
            'message': 'Klient zaktualizowany',
        }
    )


@customers_bp.route('/<int:customer_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.DELETE_CUSTOMER)
def delete_customer(customer_id):
    """Delete customer (soft delete)."""
    services.delete_customer(customer_id)

    return jsonify({'success': True, 'message': 'Klient usunięty'})


@customers_bp.route('/search/email', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_CUSTOMERS)
def search_by_email():
    """Search customers by email."""
    email = request.args.get('email')

    if not email:
        return jsonify({'success': False, 'error': 'Email wymagany'}), 400

    customers = services.search_customers_by_email(email)

    return jsonify({'success': True, 'data': customers_schema.dump(customers)})


@customers_bp.route('/search/nip', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_CUSTOMERS)
def search_by_nip():
    """Search customer by NIP."""
    nip = request.args.get('nip')

    if not nip:
        return jsonify({'success': False, 'error': 'NIP wymagany'}), 400

    customer = services.search_customers_by_nip(nip)

    return jsonify({'success': True, 'data': customer_schema.dump(customer) if customer else None})

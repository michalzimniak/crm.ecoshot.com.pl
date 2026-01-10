"""
Jobs REST API endpoints.
Handles job workflow and add-ons management.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from app.core.decorators import api_endpoint
from app.core.permissions import Permission
from app.jobs import services
from app.jobs.schemas import (
    job_schema, jobs_schema,
    job_create_schema, job_update_schema,
    job_status_update_schema, job_addon_toggle_schema,
    offer_schema, offers_schema, offer_create_schema,
    offer_addon_create_schema,
    offer_update_schema,
    offer_addon_update_schema,
)

jobs_bp = Blueprint('jobs', __name__)


# Jobs

@jobs_bp.route('', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_JOBS)
def get_jobs():
    """Get all jobs with filters and pagination."""
    filters = {}
    
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('customer_id'):
        filters['customer_id'] = int(request.args.get('customer_id'))
    if request.args.get('offer_id'):
        filters['offer_id'] = int(request.args.get('offer_id'))

    # Optional date range filters (used by frontend)
    if request.args.get('date_from'):
        filters['date_from'] = request.args.get('date_from')
    if request.args.get('date_to'):
        filters['date_to'] = request.args.get('date_to')
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    result = services.get_all_jobs(filters, page, per_page)
    
    return jsonify({
        'success': True,
        'data': jobs_schema.dump(result['items']),
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'pages': result['pages'],
            'total': result['total']
        }
    })


@jobs_bp.route('/calendar', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_JOBS)
def get_calendar():
    """Get reserved time slots for calendar view."""
    raw_from = request.args.get('from')
    raw_to = request.args.get('to')

    range_start = None
    range_end = None

    try:
        if raw_from:
            range_start = datetime.fromisoformat(raw_from)
    except Exception:
        range_start = None

    try:
        if raw_to:
            range_end = datetime.fromisoformat(raw_to)
    except Exception:
        range_end = None

    jobs = services.get_calendar_reservations(range_start, range_end)
    return jsonify({'success': True, 'data': jobs_schema.dump(jobs)})


@jobs_bp.route('/<int:job_id>', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_JOBS)
def get_job(job_id):
    """Get job by ID."""
    job = services.get_job_by_id(job_id)
    
    return jsonify({
        'success': True,
        'data': job_schema.dump(job)
    })


@jobs_bp.route('', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_JOB)
def create_job():
    """Create new job."""
    data = request.get_json()
    
    # Validate
    errors = job_create_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Create
    job = services.create_job(data)
    
    return jsonify({
        'success': True,
        'data': job_schema.dump(job),
        'message': 'Zlecenie utworzone'
    }), 201


@jobs_bp.route('/<int:job_id>', methods=['PUT'])
@api_endpoint(permission=Permission.EDIT_JOB)
def update_job(job_id):
    """Update job."""
    data = request.get_json()
    
    # Validate
    errors = job_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Update
    job = services.update_job(job_id, data)
    
    return jsonify({
        'success': True,
        'data': job_schema.dump(job),
        'message': 'Zlecenie zaktualizowane'
    })


@jobs_bp.route('/<int:job_id>/status', methods=['PUT'])
@api_endpoint(permission=Permission.CHANGE_JOB_STATUS)
def update_job_status(job_id):
    """Update job status with workflow enforcement."""
    data = request.get_json()
    
    # Validate
    errors = job_status_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Update status
    job = services.update_job_status(job_id, data['status'])
    
    return jsonify({
        'success': True,
        'data': job_schema.dump(job),
        'message': f"Status zmieniony na: {data['status']}"
    })


@jobs_bp.route('/<int:job_id>/addons/<int:addon_id>', methods=['PUT'])
@api_endpoint(permission=Permission.EDIT_JOB)
def toggle_addon(job_id, addon_id):
    """Toggle job addon selection."""
    data = request.get_json()
    
    # Validate
    errors = job_addon_toggle_schema.validate({'addon_id': addon_id, **data})
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Toggle
    job = services.toggle_job_addon(job_id, addon_id, data['is_selected'])
    
    return jsonify({
        'success': True,
        'data': job_schema.dump(job),
        'message': 'Dodatek zaktualizowany'
    })


@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.DELETE_JOB)
def delete_job(job_id):
    """Delete job (cancel)."""
    services.delete_job(job_id)
    
    return jsonify({
        'success': True,
        'message': 'Zlecenie anulowane'
    })


# Offers (seed data)

@jobs_bp.route('/offers', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_JOBS)
def get_offers():
    """Get all offers."""
    active_only = request.args.get('active_only', 'true') == 'true'
    offers = services.get_all_offers(active_only)
    
    return jsonify({
        'success': True,
        'data': offers_schema.dump(offers)
    })


@jobs_bp.route('/offers', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def create_offer():
    """Create new offer."""
    data = request.get_json()
    
    # Validate
    errors = offer_create_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Create
    offer = services.create_offer(data)
    
    return jsonify({
        'success': True,
        'data': offer_schema.dump(offer),
        'message': 'Oferta utworzona'
    }), 201


@jobs_bp.route('/offers/<int:offer_id>', methods=['PUT'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def update_offer(offer_id):
    """Update offer."""
    data = request.get_json() or {}

    errors = offer_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    offer = services.update_offer(offer_id, data)
    return jsonify({'success': True, 'data': offer_schema.dump(offer), 'message': 'Oferta zaktualizowana'})


@jobs_bp.route('/offers/<int:offer_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def delete_offer(offer_id):
    """Deactivate offer (soft delete)."""
    services.deactivate_offer(offer_id)
    return jsonify({'success': True, 'message': 'Oferta usunięta'})


@jobs_bp.route('/offers/addons', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def create_offer_addon():
    """Create new offer addon."""
    data = request.get_json()
    
    # Validate
    errors = offer_addon_create_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Create
    addon = services.create_offer_addon(data)
    
    return jsonify({
        'success': True,
        'data': addon.to_dict(),
        'message': 'Dodatek utworzony'
    }), 201


@jobs_bp.route('/offers/addons/<int:addon_id>', methods=['PUT'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def update_offer_addon(addon_id):
    """Update offer addon."""
    data = request.get_json() or {}

    errors = offer_addon_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    addon = services.update_offer_addon(addon_id, data)
    return jsonify({'success': True, 'data': addon.to_dict(), 'message': 'Dodatek zaktualizowany'})


@jobs_bp.route('/offers/addons/<int:addon_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def delete_offer_addon(addon_id):
    """Deactivate offer addon (soft delete)."""
    services.deactivate_offer_addon(addon_id)
    return jsonify({'success': True, 'message': 'Dodatek usunięty'})

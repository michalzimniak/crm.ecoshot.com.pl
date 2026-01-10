"""
Galleries REST API endpoints.
Handles photo galleries with access control.
"""

from flask import Blueprint, request, jsonify, redirect
from app.core.decorators import api_endpoint, public_endpoint
from app.core.permissions import Permission
from app.galleries import services
from app.galleries.schemas import (
    gallery_schema, galleries_schema,
    gallery_create_schema, gallery_update_schema,
    gallery_status_update_schema,
    GalleryTypePatchSchema,
    GallerySettingsPatchSchema,
    GalleryTypePatchSchema,
    GallerySettingsPatchSchema,
)

from app.photos.models import Photo
from app.photos.schemas import photos_schema


def _normalize_gallery_payload(payload: dict | None) -> dict:
    """Normalize frontend payload to backend schema/service expectations."""
    data = dict(payload or {})

    # Frontend uses `name` (legacy); backend model uses `title`.
    if data.get('title') is None and data.get('name') is not None:
        data['title'] = data.get('name')

    # Accept date-only expiry (YYYY-MM-DD) from <input type="date">.
    expires_at = data.get('expires_at')
    if isinstance(expires_at, str):
        raw = expires_at.strip()
        if raw and 'T' not in raw and ' ' not in raw:
            data['expires_at'] = f"{raw}T23:59:59"

    return data

galleries_bp = Blueprint('galleries', __name__)


@galleries_bp.route('', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_GALLERIES)
def get_galleries():
    """Get all galleries with filters and pagination."""
    filters = {}
    
    if request.args.get('gallery_type'):
        filters['gallery_type'] = request.args.get('gallery_type')
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('job_id'):
        filters['job_id'] = int(request.args.get('job_id'))

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))
    if per_page <= 0:
        per_page = 25
    if per_page > 200:
        per_page = 200

    result = services.get_all_galleries(filters, page=page, per_page=per_page)
    
    return jsonify({
        'success': True,
        'data': galleries_schema.dump(result['items']),
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'pages': result['pages'],
            'total': result['total'],
        },
    })


@galleries_bp.route('/<int:gallery_id>', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_GALLERIES)
def get_gallery(gallery_id):
    """Get gallery by ID."""
    gallery = services.get_gallery_by_id(gallery_id)
    
    return jsonify({
        'success': True,
        'data': gallery_schema.dump(gallery)
    })


@galleries_bp.route('', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_GALLERY)
def create_gallery():
    """Create new gallery for job."""
    data = _normalize_gallery_payload(request.get_json())
    
    # Validate
    errors = gallery_create_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Create
    gallery = services.create_gallery(data)
    
    return jsonify({
        'success': True,
        'data': gallery_schema.dump(gallery),
        'message': 'Galeria utworzona'
    }), 201


@galleries_bp.route('/<int:gallery_id>', methods=['PUT'])
@api_endpoint(permission=Permission.EDIT_GALLERY)
def update_gallery(gallery_id):
    """Update gallery."""
    data = _normalize_gallery_payload(request.get_json())
    
    # Validate
    errors = gallery_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400
    
    # Update
    gallery = services.update_gallery(gallery_id, data)
    
    return jsonify({
        'success': True,
        'data': gallery_schema.dump(gallery),
        'message': 'Galeria zaktualizowana'
    })


@galleries_bp.route('/<int:gallery_id>/publish', methods=['POST'])
@api_endpoint(permission=Permission.PUBLISH_GALLERY)
def publish_gallery(gallery_id):
    """Publish gallery (with enforcement)."""
    gallery = services.publish_gallery(gallery_id)
    
    return jsonify({
        'success': True,
        'data': gallery_schema.dump(gallery),
        'message': 'Galeria opublikowana'
    })


@galleries_bp.route('/<int:gallery_id>/unpublish', methods=['POST'])
@api_endpoint(permission=Permission.EDIT_GALLERY)
def unpublish_gallery(gallery_id):
    """Unpublish gallery."""
    gallery = services.unpublish_gallery(gallery_id)
    
    return jsonify({
        'success': True,
        'data': gallery_schema.dump(gallery),
        'message': 'Galeria ukryta'
    })


@galleries_bp.route('/<int:gallery_id>/send', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_GALLERY)
def send_gallery(gallery_id):
    """Send gallery access link to client."""
    gallery = services.send_gallery(gallery_id)
    
    return jsonify({
        'success': True,
        'data': gallery_schema.dump(gallery),
        'message': 'Link do galerii wysłany'
    })


@galleries_bp.route('/<int:gallery_id>/send-access', methods=['POST'])
@api_endpoint(permission=Permission.CREATE_GALLERY)
def send_gallery_access(gallery_id):
    """Prepare link + PIN for the client (GALLERYPROMPT.md)."""
    data = services.prepare_gallery_public_access(gallery_id)
    return jsonify({'success': True, 'data': data, 'message': 'Dostęp do galerii przygotowany'})


@galleries_bp.route('/<int:gallery_id>/type', methods=['PATCH'])
@api_endpoint(permission=Permission.EDIT_GALLERY)
def patch_gallery_type(gallery_id):
    payload = request.get_json() or {}
    schema = GalleryTypePatchSchema()
    errors = schema.validate(payload)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    gallery = services.patch_gallery_type(gallery_id, payload.get('gallery_type'))
    return jsonify({'success': True, 'data': gallery_schema.dump(gallery), 'message': 'Typ galerii zaktualizowany'})


@galleries_bp.route('/<int:gallery_id>/settings', methods=['PATCH'])
@api_endpoint(permission=Permission.EDIT_GALLERY)
def patch_gallery_settings(gallery_id):
    payload = request.get_json() or {}
    schema = GallerySettingsPatchSchema()
    errors = schema.validate(payload)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    gallery = services.patch_gallery_settings(gallery_id, payload)
    return jsonify({'success': True, 'data': gallery_schema.dump(gallery), 'message': 'Ustawienia galerii zaktualizowane'})


# Public endpoints for client access

@galleries_bp.route('/access/<access_token>', methods=['GET'])
@public_endpoint
def access_gallery(access_token):
    """Access gallery by token (public endpoint for client).

    If opened directly in a browser (Accept: text/html), redirect to the
    client-facing page so the user sees UI instead of raw JSON.
    """

    wants_html = request.accept_mimetypes.accept_html and (
        request.accept_mimetypes.best == 'text/html'
    )
    if wants_html and request.args.get('format') != 'json':
        return redirect(f"/galleries/access/{access_token}", code=302)

    password = request.args.get('password')
    gallery = services.access_gallery(access_token, password=password)

    data = gallery_schema.dump(gallery)

    # Only expose client-visible photos.
    photos = (
        Photo.query
        .filter_by(gallery_id=gallery.id)
        .filter(Photo.status == 'ready')
        .order_by(Photo.display_order, Photo.uploaded_at)
        .all()
    )
    data['photos'] = photos_schema.dump(photos)

    return jsonify({'success': True, 'data': data})


@galleries_bp.route('/<int:gallery_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.DELETE_GALLERY)
def delete_gallery(gallery_id):
    """Delete gallery."""
    services.delete_gallery(gallery_id)
    
    return jsonify({
        'success': True,
        'message': 'Galeria usunięta'
    })

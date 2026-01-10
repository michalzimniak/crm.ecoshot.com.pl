"""Public Gallery API endpoints.

Implements the hash + PIN flow from GALLERYPROMPT.md:
- GET  /api/gallery/<hash>
- POST /api/gallery/<hash>/pin
- GET  /api/gallery/<hash>/download

The PIN grants a short-lived JWT (session token) scoped to a single gallery.
"""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request, send_file, after_this_request
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from werkzeug.exceptions import BadRequest, Forbidden, Unauthorized

from app.core.decorators import public_endpoint
from app.galleries import services
from app.extensions import db
from app.photos.models import Photo
from app.photos.schemas import photos_schema
from app.contracts.models import Contract
from app.consents.models import Consent


public_gallery_bp = Blueprint('public_gallery', __name__)


def _get_client_meta() -> tuple[str | None, str | None]:
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    ua = request.headers.get('User-Agent')
    return ip or None, ua or None


def _require_gallery_jwt(gallery_id: int) -> None:
    verify_jwt_in_request()
    claims = get_jwt() or {}
    if claims.get('token_type') != 'gallery':
        raise Unauthorized('Nieprawidłowy token')
    if int(claims.get('gallery_id') or 0) != int(gallery_id):
        raise Unauthorized('Token nie pasuje do galerii')


@public_gallery_bp.route('/<string:public_hash>', methods=['GET'])
@public_endpoint
def get_public_gallery(public_hash: str):
    """Public metadata for gallery.

    Without a valid gallery JWT, returns a minimal payload for the PIN screen.
    With a valid gallery JWT for this gallery, returns full gallery data + photos.
    """

    gallery = services.get_gallery_by_public_hash(public_hash)

    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')
    if gallery.is_expired:
        raise BadRequest('Dostęp do galerii wygasł')
    if getattr(gallery, 'gallery_type', None) == 'archive':
        raise BadRequest('Galeria jest archiwalna i nie jest dostępna dla klienta')

    # Minimal payload for the PIN screen.
    minimal = {
        'public_hash': gallery.public_hash,
        'title': gallery.title,
        'name': gallery.title,
        'description': gallery.description,
        'requires_pin': True,
    }

    # If a valid gallery JWT is present and scoped to this gallery, return full data.
    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt() or {}
        if claims.get('token_type') == 'gallery' and int(claims.get('gallery_id') or 0) == int(gallery.id):
            photos = (
                Photo.query
                .filter_by(gallery_id=gallery.id)
                .filter(Photo.status == 'ready')
                .order_by(Photo.display_order, Photo.uploaded_at)
                .all()
            )

            data = {
                **minimal,
                **services.compute_public_gallery_flags(gallery),
                'requires_pin': False,
                'id': gallery.id,
                'job_id': gallery.job_id,
                'gallery_type': gallery.gallery_type,
                'allow_download': bool(gallery.allow_download),
                'allow_selection': bool(gallery.allow_selection),
                'max_selections': gallery.max_selections,
                'selected_count': gallery.selected_count,
                'photo_count': gallery.photo_count,
                'photos': photos_schema.dump(photos),
            }

            # Job details (plan + selected add-ons) and document links.
            try:
                job = gallery.job
                if job is not None:
                    offer = getattr(job, 'offer', None)
                    selected_addons = []
                    try:
                        # job.addons is a dynamic relationship
                        selected_addons = [a for a in job.addons.all() if getattr(a, 'is_selected', False)]
                    except Exception:
                        selected_addons = []

                    contract = Contract.query.filter_by(job_id=job.id).first()
                    contract_available = bool(contract and contract.signed_scan_path and os.path.exists(contract.signed_scan_path))

                    consent_items = []
                    try:
                        # job.consents is a dynamic relationship
                        consents = job.consents.all()
                    except Exception:
                        consents = []

                    for c in consents or []:
                        if not getattr(c, 'signed_scan_path', None):
                            continue
                        if not os.path.exists(c.signed_scan_path):
                            continue
                        consent_items.append({
                            'id': c.id,
                            'consent_type': c.consent_type,
                            'scope': c.scope,
                            'signed_scan_original_filename': c.signed_scan_original_filename,
                            'download_url': f"/api/gallery/{gallery.public_hash}/consent-scan/{c.id}",
                        })

                    data['job'] = {
                        'id': job.id,
                        'title': getattr(job, 'title', None),
                        'event_date': job.event_date.isoformat() if getattr(job, 'event_date', None) else None,
                        'offer': offer.to_dict(include_addons=False) if offer else None,
                        'selected_addons': [a.to_dict() for a in selected_addons],
                    }

                    data['documents'] = {
                        'contract': {
                            'available': bool(contract_available),
                            'signed_scan_original_filename': getattr(contract, 'signed_scan_original_filename', None) if contract else None,
                            'download_url': f"/api/gallery/{gallery.public_hash}/contract-scan" if contract_available else None,
                        },
                        'consents': consent_items,
                    }
            except Exception:
                # Best-effort only; gallery access should still work.
                pass

            # Track views once the user is authenticated via PIN.
            gallery.increment_view_count()
            db.session.commit()

            return jsonify({'success': True, 'data': data})

    except Exception:
        # If token is missing, we intentionally fall back to minimal response.
        # If token is invalid, jwt handlers will normally return 401.
        pass

    return jsonify({'success': True, 'data': minimal})


@public_gallery_bp.route('/<string:public_hash>/contract-scan', methods=['GET'])
@public_endpoint
def download_contract_scan(public_hash: str):
    """Download signed contract scan for the job, gated by gallery JWT."""

    gallery = services.get_gallery_by_public_hash(public_hash)

    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')
    if gallery.is_expired:
        raise BadRequest('Dostęp do galerii wygasł')
    if getattr(gallery, 'gallery_type', None) == 'archive':
        raise BadRequest('Galeria jest archiwalna i nie jest dostępna dla klienta')

    _require_gallery_jwt(gallery.id)

    contract = Contract.query.filter_by(job_id=int(gallery.job_id)).first()
    if not contract or not contract.signed_scan_path or not os.path.exists(contract.signed_scan_path):
        raise BadRequest('Brak skanu podpisanej umowy')

    download_name = contract.signed_scan_original_filename or f"signed_contract_{contract.id}"
    return send_file(
        contract.signed_scan_path,
        mimetype=contract.signed_scan_mime_type or 'application/octet-stream',
        as_attachment=True,
        download_name=download_name,
    )


@public_gallery_bp.route('/<string:public_hash>/consent-scan/<int:consent_id>', methods=['GET'])
@public_endpoint
def download_consent_scan(public_hash: str, consent_id: int):
    """Download signed consent scan for the job, gated by gallery JWT."""

    gallery = services.get_gallery_by_public_hash(public_hash)

    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')
    if gallery.is_expired:
        raise BadRequest('Dostęp do galerii wygasł')
    if getattr(gallery, 'gallery_type', None) == 'archive':
        raise BadRequest('Galeria jest archiwalna i nie jest dostępna dla klienta')

    _require_gallery_jwt(gallery.id)

    consent = Consent.query.filter_by(id=int(consent_id), job_id=int(gallery.job_id)).first()
    if not consent or not consent.signed_scan_path or not os.path.exists(consent.signed_scan_path):
        raise BadRequest('Brak wgranego skanu zgody')

    download_name = consent.signed_scan_original_filename or os.path.basename(consent.signed_scan_path)
    return send_file(
        consent.signed_scan_path,
        mimetype=consent.signed_scan_mime_type or 'application/octet-stream',
        as_attachment=True,
        download_name=download_name,
    )


@public_gallery_bp.route('/<string:public_hash>/pin', methods=['POST'])
@public_endpoint
def verify_gallery_pin(public_hash: str):
    """Verify PIN and issue a short-lived gallery JWT."""

    payload = request.get_json() or {}
    pin = (payload.get('pin') or '').strip()

    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        raise BadRequest('PIN musi mieć 4–6 cyfr')

    gallery = services.get_gallery_by_public_hash(public_hash)

    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')
    if gallery.is_expired:
        raise BadRequest('Dostęp do galerii wygasł')
    if getattr(gallery, 'gallery_type', None) == 'archive':
        raise BadRequest('Galeria jest archiwalna i nie jest dostępna dla klienta')

    ip, ua = _get_client_meta()

    if services.is_pin_rate_limited(gallery.id, ip):
        return (
            jsonify({'success': False, 'error': 'Zbyt wiele prób PIN. Spróbuj ponownie później.', 'code': 'RATE_LIMIT'}),
            429,
        )

    if not services.verify_pin(pin, getattr(gallery, 'access_pin_hash', None)):
        services.log_pin_attempt(gallery.id, ip, ua, is_success=False)
        raise Unauthorized('Nieprawidłowy PIN')

    services.log_pin_attempt(gallery.id, ip, ua, is_success=True)

    token = services.issue_gallery_access_token(gallery, expires_minutes=30)
    return jsonify({'success': True, 'data': {'access_token': token, 'expires_minutes': 30}})


@public_gallery_bp.route('/<string:public_hash>/download', methods=['GET'])
@public_endpoint
def download_gallery_zip(public_hash: str):
    """Download ZIP, gated by business rules (final + paid + completed + watermark disabled)."""

    gallery = services.get_gallery_by_public_hash(public_hash)

    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')
    if gallery.is_expired:
        raise BadRequest('Dostęp do galerii wygasł')
    if getattr(gallery, 'gallery_type', None) == 'archive':
        raise BadRequest('Galeria jest archiwalna i nie jest dostępna dla klienta')

    _require_gallery_jwt(gallery.id)

    # Hard block per prompt.
    if gallery.gallery_type != 'final':
        raise Forbidden('Pobieranie dostępne tylko dla galerii finalnej')

    flags = services.compute_public_gallery_flags(gallery)
    if not flags.get('invoice_paid'):
        raise Forbidden('Galeria będzie dostępna po opłaceniu')

    if flags.get('job_status') != 'completed':
        raise Forbidden('Galeria będzie dostępna po zakończeniu zlecenia')

    if getattr(gallery, 'watermark_enabled', False):
        raise Forbidden('Aby pobrać ZIP, watermark musi być wyłączony')

    if not getattr(gallery, 'allow_download', False):
        raise Forbidden('Pobieranie nie jest włączone dla tej galerii')

    # Also enforce existing rule for final galleries.
    services.can_download_final_gallery(gallery.job_id)

    zip_path, size = services.generate_gallery_zip_file(gallery)

    ip, ua = _get_client_meta()
    services.log_gallery_download(gallery.id, ip, ua, size)

    @after_this_request
    def _cleanup(response):
        try:
            if zip_path and os.path.exists(zip_path):
                os.remove(zip_path)
        except Exception:
            pass
        return response

    download_name = f"gallery_{gallery.id}.zip"
    try:
        title = (gallery.title or '').strip()
        if title:
            safe = ''.join(ch for ch in title if ch.isalnum() or ch in (' ', '-', '_')).strip().replace(' ', '_')
            if safe:
                download_name = f"{safe}.zip"
    except Exception:
        pass

    return send_file(zip_path, as_attachment=True, download_name=download_name, mimetype='application/zip')

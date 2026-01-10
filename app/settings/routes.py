"""Settings REST API endpoints."""

import os
import tempfile
import uuid

from flask import after_this_request

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import NotFound

from app.core.decorators import api_endpoint, public_endpoint
from app.core.permissions import Permission
from app.settings.schemas import settings_update_schema
from app.settings import services
from app.settings import maintenance
from app.extensions import db


settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/branding', methods=['GET'])
@public_endpoint
def get_branding_public():
    """Public branding configuration (title/name + logo presence/url)."""
    return jsonify({'success': True, 'data': services.get_branding()})


@settings_bp.route('/branding/logo', methods=['GET'])
@public_endpoint
def get_brand_logo():
    """Serve currently configured brand logo (public)."""
    abs_path = services.get_brand_logo_abs_path()
    if not abs_path or not os.path.exists(abs_path):
        raise NotFound('Brak logo')
    return send_file(abs_path)


@settings_bp.route('/branding/gallery-logo', methods=['GET'])
@public_endpoint
def get_gallery_logo():
    """Serve currently configured gallery (public client view) logo (public)."""
    abs_path = services.get_gallery_logo_abs_path()
    if not abs_path or not os.path.exists(abs_path):
        raise NotFound('Brak logo galerii')
    return send_file(abs_path)


@settings_bp.route('/branding/logo', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def upload_brand_logo():
    """Upload brand logo (admin)."""
    file = request.files.get('logo') or request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Brak pliku'}), 400

    filename = secure_filename(file.filename)
    ext = (filename.rsplit('.', 1)[-1] if '.' in filename else '').lower()
    allowed = {'png', 'jpg', 'jpeg', 'gif'}
    if ext not in allowed:
        return jsonify({'success': False, 'error': 'Dozwolone formaty: PNG, JPG, JPEG, GIF'}), 400

    base = os.path.abspath(services._get_upload_base_dir())
    branding_dir = os.path.join(base, 'branding')
    os.makedirs(branding_dir, exist_ok=True)

    # Remove previous file if present.
    old_abs = services.get_brand_logo_abs_path()
    if old_abs and os.path.exists(old_abs):
        try:
            os.remove(old_abs)
        except Exception:
            pass

    out_name = f"logo_{uuid.uuid4().hex}.{ext}"
    out_abs = os.path.join(branding_dir, out_name)
    file.save(out_abs)

    # Store relative path under upload base.
    rel = os.path.join('branding', out_name)
    services.set_setting(services.BRANDING_FIELD_TO_KEY['logo_path'], rel)
    db.session.commit()

    try:
        from flask import g
        g._settings_db_cache = None
    except Exception:
        pass

    return jsonify({'success': True, 'data': services.get_branding(), 'message': 'Logo zapisane'})


@settings_bp.route('/branding/gallery-logo', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def upload_gallery_logo():
    """Upload gallery (public client view) logo (admin)."""
    file = request.files.get('logo') or request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Brak pliku'}), 400

    filename = secure_filename(file.filename)
    ext = (filename.rsplit('.', 1)[-1] if '.' in filename else '').lower()
    allowed = {'png', 'jpg', 'jpeg', 'gif'}
    if ext not in allowed:
        return jsonify({'success': False, 'error': 'Dozwolone formaty: PNG, JPG, JPEG, GIF'}), 400

    base = os.path.abspath(services._get_upload_base_dir())
    branding_dir = os.path.join(base, 'branding')
    os.makedirs(branding_dir, exist_ok=True)

    # Remove previous file if present.
    old_abs = services.get_gallery_logo_abs_path()
    if old_abs and os.path.exists(old_abs):
        try:
            os.remove(old_abs)
        except Exception:
            pass

    out_name = f"gallery_logo_{uuid.uuid4().hex}.{ext}"
    out_abs = os.path.join(branding_dir, out_name)
    file.save(out_abs)

    # Store relative path under upload base.
    rel = os.path.join('branding', out_name)
    services.set_setting(services.BRANDING_FIELD_TO_KEY['gallery_logo_path'], rel)
    db.session.commit()

    try:
        from flask import g
        g._settings_db_cache = None
    except Exception:
        pass

    return jsonify({'success': True, 'data': services.get_branding(), 'message': 'Logo galerii zapisane'})


@settings_bp.route('/branding/logo', methods=['DELETE'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def delete_brand_logo():
    """Delete brand logo (admin)."""
    abs_path = services.get_brand_logo_abs_path()
    if abs_path and os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass

    services.set_setting(services.BRANDING_FIELD_TO_KEY['logo_path'], None)
    db.session.commit()

    try:
        from flask import g
        g._settings_db_cache = None
    except Exception:
        pass

    return jsonify({'success': True, 'data': services.get_branding(), 'message': 'Logo usunięte'})


@settings_bp.route('/branding/gallery-logo', methods=['DELETE'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def delete_gallery_logo():
    """Delete gallery (public client view) logo (admin)."""
    abs_path = services.get_gallery_logo_abs_path()
    if abs_path and os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass

    services.set_setting(services.BRANDING_FIELD_TO_KEY['gallery_logo_path'], None)
    db.session.commit()

    try:
        from flask import g
        g._settings_db_cache = None
    except Exception:
        pass

    return jsonify({'success': True, 'data': services.get_branding(), 'message': 'Logo galerii usunięte'})


@settings_bp.route('', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_SETTINGS)
def get_settings():
    """Return settings with DB overrides and config fallback."""
    data = services.get_settings_snapshot()
    return jsonify({'success': True, 'data': data})


@settings_bp.route('', methods=['PUT'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def update_settings():
    payload = request.get_json() or {}

    errors = settings_update_schema.validate(payload)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    services.update_settings_from_payload(payload)
    data = services.get_settings_snapshot()
    return jsonify({'success': True, 'data': data, 'message': 'Ustawienia zapisane'})


@settings_bp.route('/maintenance/backup/db', methods=['GET'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def download_db_backup():
    """Download a DB dump (SQL)."""
    path, download_name = maintenance.create_db_dump_file()

    @after_this_request
    def _cleanup(response):
        try:
            os.remove(path)
        except Exception:
            pass
        return response

    return send_file(path, as_attachment=True, download_name=download_name)


@settings_bp.route('/maintenance/backup/full', methods=['GET'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def download_full_backup():
    """Download a full backup ZIP (DB dump + uploads folder)."""
    path, download_name = maintenance.create_full_backup_zip()

    @after_this_request
    def _cleanup(response):
        try:
            os.remove(path)
        except Exception:
            pass
        return response

    return send_file(path, as_attachment=True, download_name=download_name)


@settings_bp.route('/maintenance/backups/full', methods=['GET'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def list_full_backups():
    """List persisted full backups stored on disk."""
    items = maintenance.list_full_backups()
    return jsonify({'success': True, 'data': items})


@settings_bp.route('/maintenance/backups/full', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def create_full_backup_persisted():
    """Create and store a full backup ZIP on disk (keeps 3 newest)."""
    info = maintenance.create_persisted_full_backup(kind='manual')
    return jsonify({'success': True, 'data': info, 'message': 'Backup zapisany na serwerze'})


@settings_bp.route('/maintenance/backups/full/<name>', methods=['GET'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def download_full_backup_persisted(name):
    """Download a persisted full backup ZIP by name."""
    abs_path = maintenance.get_full_backup_abs_path(name)
    return send_file(abs_path, as_attachment=True, download_name=name)


@settings_bp.route('/maintenance/backups/full/<name>/restore', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def restore_full_backup_persisted(name):
    """Restore DB + uploads from a persisted full backup ZIP."""
    payload = request.get_json() or {}
    confirm = (payload.get('confirm') or '').strip()
    if confirm != 'PRZYWRÓĆ':
        return jsonify({'success': False, 'error': 'Aby przywrócić backup wpisz dokładnie: PRZYWRÓĆ'}), 400

    result = maintenance.restore_full_backup_from_zip(name)
    return jsonify({'success': True, 'data': result, 'message': 'Backup przywrócony'})


@settings_bp.route('/maintenance/restore/db', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def restore_db_backup():
    """Restore DB from uploaded SQL file."""
    confirm = (request.form.get('confirm') or '').strip()
    if confirm != 'PRZYWRÓĆ':
        return jsonify({'success': False, 'error': 'Aby przywrócić backup wpisz dokładnie: PRZYWRÓĆ'}), 400

    file = request.files.get('file') or request.files.get('backup')
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'Brak pliku backupu'}), 400

    # Save to temp file and restore from it.
    fd, tmp_path = tempfile.mkstemp(prefix='db_restore_', suffix='.sql')
    os.close(fd)
    try:
        file.save(tmp_path)
        maintenance.restore_db_from_sql_file(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return jsonify({'success': True, 'message': 'Backup bazy przywrócony'})


@settings_bp.route('/maintenance/purge', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_SETTINGS)
def purge_data():
    """Danger zone: delete selected domain data and optionally uploaded files."""
    payload = request.get_json() or {}
    targets = payload.get('targets') or []
    delete_files = bool(payload.get('delete_files', True))
    confirm = (payload.get('confirm') or '').strip()

    if confirm != 'USUŃ DANE':
        return jsonify({'success': False, 'error': 'Aby usunąć dane wpisz dokładnie: USUŃ DANE'}), 400

    result = maintenance.purge_data(targets, delete_files=delete_files)
    return jsonify({'success': True, 'data': result, 'message': 'Dane usunięte'})

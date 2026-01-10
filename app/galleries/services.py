"""
Galleries business logic.
Handles gallery management, access control, and ZIP generation with enforcement.
"""

import os
import secrets
from datetime import datetime
from datetime import timedelta
import tempfile
import zipfile
import bcrypt
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized
from flask import current_app
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.galleries.models import Gallery, GalleryPinAttempt, GalleryDownloadLog
from app.jobs.services import get_job_by_id
from app.core.enforcement import can_publish_gallery, can_download_final_gallery


def generate_access_token():
    """Generuje unikalny token dostępu."""
    return secrets.token_urlsafe(32)


def create_gallery(data):
    """
    Tworzy nową galerię dla zlecenia.
    
    Args:
        data: dict z danymi galerii
    
    Returns:
        Gallery: nowa galeria
    """
    # Walidacja job
    job = get_job_by_id(data['job_id'])
    
    # Utwórz galerię
    title = data.get('title') if isinstance(data, dict) else None
    if title is None and isinstance(data, dict):
        title = data.get('name')

    # Backwards compatibility: old UI used 'proofing'.
    if data.get('gallery_type') == 'proofing':
        data['gallery_type'] = 'proof'

    gallery = Gallery(
        job_id=data['job_id'],
        gallery_type=data['gallery_type'],
        title=title,
        description=data.get('description'),
        access_token=generate_access_token(),
        public_hash=_generate_public_hash(),
        expires_at=data.get('expires_at'),
        expiration_days=data.get('expiration_days'),
        allow_download=data.get('allow_download', False),
        allow_selection=data.get('allow_selection', True),
        max_selections=data.get('max_selections'),
        watermark_enabled=data.get('watermark_enabled', True),
        notes=data.get('notes'),
        status='draft'
    )
    
    # Hasło opcjonalne
    if data.get('password'):
        gallery.password_hash = generate_password_hash(data['password'])
    
    db.session.add(gallery)
    db.session.commit()
    
    return gallery


def get_gallery_by_id(gallery_id):
    """Pobiera galerię po ID."""
    gallery = db.session.get(Gallery, gallery_id)
    if not gallery:
        raise NotFound(f'Galeria #{gallery_id} nie istnieje')
    return gallery


def get_galleries_by_job(job_id):
    """Pobiera wszystkie galerie dla zlecenia."""
    return Gallery.query.filter_by(job_id=job_id).order_by(Gallery.created_at.desc()).all()


def update_gallery(gallery_id, data):
    """Aktualizuje galerię."""
    gallery = get_gallery_by_id(gallery_id)

    if data.get('gallery_type') == 'proofing':
        data['gallery_type'] = 'proof'
    
    allowed_fields = [
        'title', 'description', 'expires_at', 'allow_download',
        'allow_selection', 'max_selections', 'watermark_enabled', 'notes', 'expiration_days'
    ]

    # Prompt requirement: gallery type can be changed without deleting photos.
    if 'gallery_type' in data and data['gallery_type'] != gallery.gallery_type:
        gallery.gallery_type = data['gallery_type']
    
    for field in allowed_fields:
        if field in data:
            setattr(gallery, field, data[field])
    
    # Aktualizuj hasło jeśli podano
    if 'password' in data:
        if data['password']:
            gallery.password_hash = generate_password_hash(data['password'])
        else:
            gallery.password_hash = None
    
    db.session.commit()
    return gallery


def publish_gallery(gallery_id):
    """
    Publikuje galerię.
    
    Args:
        gallery_id: ID galerii
    
    Returns:
        Gallery: galeria
        
    Raises:
        BadRequest: jeśli warunki nie są spełnione
    """
    gallery = get_gallery_by_id(gallery_id)
    
    # Enforcement - sprawdź czy można opublikować
    can_publish_gallery(gallery.job_id)
    
    if gallery.photo_count == 0:
        raise BadRequest('Nie można opublikować pustej galerii')
    
    gallery.status = 'published'
    gallery.published_at = datetime.utcnow()

    # Ensure public access credentials exist (hash + PIN hash).
    ensure_public_hash(gallery)
    if not getattr(gallery, 'access_pin_hash', None):
        # Generate PIN hash without leaking plaintext.
        _gallery, _pin = ensure_pin_for_gallery(gallery)

    # Auto-set expiry from selected online album validity (if not set manually)
    if not gallery.expires_at:
        months = _get_online_album_months_for_job(gallery.job_id)
        if months:
            gallery.expires_at = _add_months(gallery.published_at, months)

    db.session.commit()
    
    # TODO: Wysłanie emaila z linkiem do galerii
    
    return gallery


def archive_gallery(gallery_id):
    """Archiwizuje galerię."""
    gallery = get_gallery_by_id(gallery_id)
    gallery.status = 'archived'
    db.session.commit()
    return gallery


def access_gallery(access_token, password=None):
    """
    Daje dostęp do galerii dla klienta.
    
    Args:
        access_token: token dostępu
        password: hasło (jeśli wymagane)
    
    Returns:
        Gallery: galeria
        
    Raises:
        NotFound: jeśli galeria nie istnieje
        Unauthorized: jeśli hasło jest nieprawidłowe
        BadRequest: jeśli dostęp wygasł
    """
    gallery = Gallery.query.filter_by(access_token=access_token).first()
    
    if not gallery:
        raise NotFound('Galeria nie istnieje')
    
    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')
    
    if gallery.is_expired:
        raise BadRequest('Dostęp do galerii wygasł')
    
    # Sprawdź hasło jeśli wymagane
    if gallery.password_hash:
        if not password:
            raise Unauthorized('Wymagane hasło')
        if not check_password_hash(gallery.password_hash, password):
            raise Unauthorized('Nieprawidłowe hasło')
    
    # Inkrementuj licznik wyświetleń
    gallery.increment_view_count()
    db.session.commit()
    
    return gallery


def generate_gallery_zip(gallery_id):
    """
    Generuje ZIP galerii.
    
    Args:
        gallery_id: ID galerii
    
    Returns:
        str: ścieżka do pliku ZIP
        
    Raises:
        BadRequest: jeśli nie można wygenerować ZIP
    """
    gallery = get_gallery_by_id(gallery_id)
    
    # Enforcement - sprawdź czy można pobrać
    if gallery.gallery_type == 'final':
        can_download_final_gallery(gallery.job_id)
    
    if not gallery.allow_download:
        raise BadRequest('Pobieranie nie jest włączone dla tej galerii')
    
    zip_path, _bytes = generate_gallery_zip_file(gallery)

    gallery.zip_path = zip_path
    gallery.zip_generated_at = datetime.utcnow()
    db.session.commit()

    return zip_path


def get_all_galleries(filters=None, page: int = 1, per_page: int = 25):
    """Pobiera galerie z filtrami i paginacją."""
    query = Gallery.query

    if filters:
        if filters.get('gallery_type'):
            query = query.filter_by(gallery_type=filters['gallery_type'])
        if filters.get('status'):
            query = query.filter_by(status=filters['status'])
        if filters.get('job_id'):
            query = query.filter_by(job_id=filters['job_id'])

    query = query.order_by(Gallery.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
    }


def unpublish_gallery(gallery_id):
    """Ukrywa galerię (z published -> draft)."""
    gallery = get_gallery_by_id(gallery_id)

    if gallery.status != 'published':
        raise BadRequest('Galeria nie jest opublikowana')

    gallery.status = 'draft'
    db.session.commit()
    return gallery


def send_gallery(gallery_id):
    """Placeholder: wysłanie linku do galerii klientowi (email/SMS)."""
    gallery = get_gallery_by_id(gallery_id)

    if gallery.status != 'published':
        raise BadRequest('Galeria musi być opublikowana, aby wysłać link')

    # TODO: Integracja z wysyłką email/SMS
    return gallery


def rotate_gallery_pin(gallery: Gallery, length: int = 6) -> str:
    """Rotate PIN and return the new plaintext PIN."""
    pin = generate_gallery_pin(length)
    gallery.access_pin_hash = hash_pin(pin)
    db.session.commit()
    return pin


def prepare_gallery_public_access(gallery_id: int) -> dict:
    """Ensure gallery has public hash + PIN and return link+PIN for sending."""
    gallery = get_gallery_by_id(gallery_id)

    if gallery.status != 'published':
        raise BadRequest('Galeria musi być opublikowana, aby wysłać dostęp')

    ensure_public_hash(gallery)
    pin = rotate_gallery_pin(gallery, length=6)

    link = f"/g/{gallery.public_hash}"
    return {'link': link, 'pin': pin}


def patch_gallery_type(gallery_id: int, gallery_type: str) -> Gallery:
    """Change gallery_type without deleting photos (prompt requirement)."""
    gallery = get_gallery_by_id(gallery_id)

    if gallery_type == 'proofing':
        gallery_type = 'proof'

    allowed = {'proof', 'selection', 'final', 'archive'}
    if gallery_type not in allowed:
        raise BadRequest('Nieprawidłowy typ galerii')

    gallery.gallery_type = gallery_type
    db.session.commit()
    return gallery


def patch_gallery_settings(gallery_id: int, data: dict) -> Gallery:
    gallery = get_gallery_by_id(gallery_id)

    allowed_fields = {'allow_download', 'allow_selection', 'watermark_enabled', 'expiration_days'}
    for key in allowed_fields:
        if key in data and data[key] is not None:
            setattr(gallery, key, data[key])

    db.session.commit()
    return gallery


def send_gallery_access(gallery_id: int) -> dict:
    """Prepare public access link + PIN.

    For now, returns the link + plaintext PIN in the response.
    In production, this should be delivered via email/SMS and PIN should not be logged.
    """
    gallery = get_gallery_by_id(gallery_id)

    if gallery.status != 'published':
        raise BadRequest('Galeria musi być opublikowana, aby wysłać dostęp')

    ensure_public_hash(gallery)

    # Rotate PIN on each send to avoid requiring DB access to recover it.
    pin = generate_gallery_pin(6)
    gallery.access_pin_hash = hash_pin(pin)
    db.session.commit()

    link = f"/g/{gallery.public_hash}"
    return {
        'gallery_id': gallery.id,
        'public_hash': gallery.public_hash,
        'link': link,
        'pin': pin,
    }


def patch_gallery_type(gallery_id: int, gallery_type: str) -> Gallery:
    """Patch gallery type without deleting photos.

    Business rules (download / watermark) are enforced elsewhere.
    """
    gallery = get_gallery_by_id(gallery_id)
    if not gallery_type:
        raise BadRequest('gallery_type wymagane')

    gallery.gallery_type = gallery_type
    db.session.commit()
    return gallery


def patch_gallery_settings(gallery_id: int, payload: dict) -> Gallery:
    gallery = get_gallery_by_id(gallery_id)

    allowed = ['allow_download', 'allow_selection', 'watermark_enabled', 'expiration_days']
    for key in allowed:
        if key in payload:
            setattr(gallery, key, payload[key])

    db.session.commit()
    return gallery


def delete_gallery(gallery_id):
    """Usuwa galerię."""
    gallery = get_gallery_by_id(gallery_id)
    db.session.delete(gallery)
    db.session.commit()


def _add_months(dt, months):
    """Add months to datetime, clamping day when needed."""
    import calendar

    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])

    return dt.replace(year=year, month=month, day=day)


def _get_online_album_months_for_job(job_id):
    """Return selected online album validity (months) for a job, if any."""
    job = get_job_by_id(job_id)

    selected = [a for a in job.addons if a.is_selected and a.category == 'online_album' and a.duration_months]
    if not selected:
        return None

    # If multiple selected (should not happen), pick the longest.
    return max(int(a.duration_months) for a in selected)


def expire_published_galleries(now=None):
    """Archive published galleries that are past expires_at."""
    now = now or datetime.utcnow()

    expired = (
        Gallery.query
        .filter(Gallery.status == 'published')
        .filter(Gallery.expires_at.isnot(None))
        .filter(Gallery.expires_at <= now)
        .all()
    )

    for g in expired:
        g.status = 'archived'

    if expired:
        db.session.commit()

    return len(expired)


def _generate_public_hash() -> str:
    # token_urlsafe(24) is typically 32+ chars; keep URL-safe.
    return secrets.token_urlsafe(24)


def ensure_public_hash(gallery: Gallery) -> Gallery:
    if not getattr(gallery, 'public_hash', None):
        gallery.public_hash = _generate_public_hash()
        db.session.commit()
    return gallery


def generate_gallery_pin(length: int = 6) -> str:
    """Generate 4-6 digit numeric PIN."""
    length = int(length)
    if length < 4:
        length = 4
    if length > 6:
        length = 6
    # Avoid leading zeros confusion by allowing them; spec doesn't forbid.
    return ''.join(str(secrets.randbelow(10)) for _ in range(length))


def hash_pin(pin: str) -> str:
    pin_bytes = (pin or '').encode('utf-8')
    hashed = bcrypt.hashpw(pin_bytes, bcrypt.gensalt(rounds=12))
    return hashed.decode('utf-8')


def verify_pin(pin: str, pin_hash: str | None) -> bool:
    if not pin_hash:
        return False
    try:
        return bcrypt.checkpw((pin or '').encode('utf-8'), pin_hash.encode('utf-8'))
    except Exception:
        return False


def get_gallery_by_public_hash(public_hash: str) -> Gallery:
    gallery = Gallery.query.filter_by(public_hash=public_hash).first()
    if not gallery:
        raise NotFound('Galeria nie istnieje')
    return gallery


def is_pin_rate_limited(gallery_id: int, ip_address: str | None, window_seconds: int = 900, max_attempts: int = 5) -> bool:
    """Simple rate limit: max failed attempts per IP+gallery in a rolling window."""
    ip_address = (ip_address or '').strip() or None
    if not ip_address:
        return False
    since = datetime.utcnow() - timedelta(seconds=int(window_seconds))
    failed = (
        GalleryPinAttempt.query
        .filter(GalleryPinAttempt.gallery_id == int(gallery_id))
        .filter(GalleryPinAttempt.ip_address == ip_address)
        .filter(GalleryPinAttempt.is_success == False)  # noqa: E712
        .filter(GalleryPinAttempt.attempted_at >= since)
        .count()
    )
    return failed >= int(max_attempts)


def log_pin_attempt(gallery_id: int, ip_address: str | None, user_agent: str | None, is_success: bool) -> None:
    attempt = GalleryPinAttempt(
        gallery_id=int(gallery_id),
        ip_address=(ip_address or None),
        user_agent=(user_agent or None),
        is_success=bool(is_success),
    )
    db.session.add(attempt)
    db.session.commit()


def ensure_pin_for_gallery(gallery: Gallery) -> tuple[Gallery, str]:
    """Ensure gallery has a PIN hash. Returns (gallery, plain_pin)."""
    if getattr(gallery, 'access_pin_hash', None):
        # Don't rotate automatically.
        return gallery, ''

    pin = generate_gallery_pin(6)
    gallery.access_pin_hash = hash_pin(pin)
    db.session.commit()
    return gallery, pin


def issue_gallery_access_token(gallery: Gallery, expires_minutes: int = 30) -> str:
    token = create_access_token(
        identity=f"gallery:{gallery.id}",
        additional_claims={
            'token_type': 'gallery',
            'gallery_id': int(gallery.id),
        },
        expires_delta=timedelta(minutes=int(expires_minutes)),
    )
    return token


def get_invoice_paid_status_for_job(job_id: int) -> bool:
    from app.invoices.models import Invoice

    invoice = Invoice.query.filter_by(job_id=int(job_id)).first()
    if not invoice:
        return False
    try:
        return float(invoice.paid_amount or 0) >= float(invoice.total_amount or 0)
    except Exception:
        return False


def compute_public_gallery_flags(gallery: Gallery) -> dict:
    job = gallery.job
    job_status = getattr(job, 'status', None) if job else None
    invoice_paid = False
    if getattr(gallery, 'job_id', None):
        invoice_paid = get_invoice_paid_status_for_job(gallery.job_id)

    watermark_required = (not invoice_paid) or bool(getattr(gallery, 'watermark_enabled', False))

    download_available = (
        getattr(gallery, 'gallery_type', None) == 'final'
        and getattr(gallery, 'status', None) == 'published'
        and bool(invoice_paid)
        and (job_status == 'completed')
        and (not bool(getattr(gallery, 'watermark_enabled', False)))
        and bool(getattr(gallery, 'allow_download', False))
    )

    return {
        'invoice_paid': bool(invoice_paid),
        'job_status': job_status,
        'watermark_required': bool(watermark_required),
        'download_available': bool(download_available),
    }


def generate_gallery_zip_file(gallery: Gallery) -> tuple[str, int]:
    """Generate a ZIP for a gallery on-the-fly. Returns (zip_path, bytes)."""
    from app.photos.models import Photo

    galleries_folder = current_app.config.get('GALLERIES_FOLDER', 'uploads/galleries')
    os.makedirs(galleries_folder, exist_ok=True)

    fd, zip_path = tempfile.mkstemp(prefix=f"gallery_{gallery.id}_", suffix='.zip', dir=galleries_folder)
    os.close(fd)

    photos = (
        Photo.query
        .filter(Photo.gallery_id == gallery.id)
        .filter(Photo.status != 'deleted')
        .order_by(Photo.display_order, Photo.uploaded_at)
        .all()
    )

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, photo in enumerate(photos, start=1):
            path = getattr(photo, 'original_path', None)
            if not path or not os.path.exists(path):
                continue
            # Keep filenames stable and safe.
            base = os.path.basename(getattr(photo, 'filename', '') or f"photo_{photo.id}.jpg")
            arcname = f"{idx:04d}_{base}"
            zf.write(path, arcname)

    size = 0
    try:
        size = int(os.path.getsize(zip_path))
    except OSError:
        size = 0

    return zip_path, size


def log_gallery_download(gallery_id: int, ip_address: str | None, user_agent: str | None, bytes_sent: int | None) -> None:
    entry = GalleryDownloadLog(
        gallery_id=int(gallery_id),
        ip_address=(ip_address or None),
        user_agent=(user_agent or None),
        bytes_sent=(int(bytes_sent) if bytes_sent is not None else None),
    )
    db.session.add(entry)
    db.session.commit()

    return None

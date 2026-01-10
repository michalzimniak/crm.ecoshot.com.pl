"""
Photos business logic.
Handles photo upload, EXIF extraction, watermarking, and selection.
"""

import os
from uuid import uuid4
from datetime import datetime
from werkzeug.exceptions import BadRequest, NotFound
from flask import current_app
from app.extensions import db
from app.photos.models import Photo
from app.galleries.services import get_gallery_by_id

from PIL import Image, ImageOps, ImageDraw, ImageFont


def create_photo(data, file=None):
    """
    Tworzy nowe zdjęcie w galerii.
    
    Args:
        data: dict z danymi zdjęcia
        file: plik zdjęcia (werkzeug.FileStorage)
    
    Returns:
        Photo: nowe zdjęcie
    """
    # Walidacja gallery
    gallery = get_gallery_by_id(data['gallery_id'])
    
    # Minimalna implementacja: zapis pliku + generowanie miniaturki.
    if file is None:
        raise BadRequest("Brak pliku")
    
    photos_folder = current_app.config.get('PHOTOS_FOLDER', 'uploads/photos')
    os.makedirs(photos_folder, exist_ok=True)
    
    original_filename = data['filename']
    storage_name = f"{uuid4().hex}_{original_filename}"
    original_path = os.path.join(photos_folder, storage_name)

    # Zapisz plik na dysk
    file.save(original_path)

    file_size = None
    try:
        file_size = os.path.getsize(original_path)
    except OSError:
        pass

    width = height = None
    try:
        with Image.open(original_path) as img:
            img = ImageOps.exif_transpose(img)
            width, height = img.size
    except Exception:
        # Jeśli to nie obraz lub Pillow ma problem, nie blokuj zapisu
        width = height = None

    stem = os.path.splitext(storage_name)[0]
    thumbnail_path = os.path.join(photos_folder, f"thumb_{stem}.jpg")

    watermarked_path = os.path.join(photos_folder, f"wm_{stem}.jpg")

    try:
        generate_thumbnail(original_path, thumbnail_path, size=(300, 300))
    except Exception:
        thumbnail_path = None

    # Generate watermark for non-final galleries when enabled.
    wm_created = False
    if getattr(gallery, 'watermark_enabled', False) and getattr(gallery, 'gallery_type', None) != 'final':
        watermark_src = current_app.config.get('WATERMARK_PATH')
        try:
            apply_watermark(original_path, watermarked_path, watermark_src)
            wm_created = True
        except Exception:
            wm_created = False
    
    # Utwórz zdjęcie
    photo = Photo(
        gallery_id=data['gallery_id'],
        filename=original_filename,
        original_path=original_path,
        thumbnail_path=thumbnail_path,
        watermarked_path=watermarked_path if wm_created else None,
        file_size=file_size,
        width=width,
        height=height,
        mime_type=getattr(file, "mimetype", None),
        caption=data.get('caption'),
        display_order=data.get('display_order', 0),
        is_favorite=data.get('is_favorite', False),
        notes=data.get('notes'),
        status='ready' if thumbnail_path else 'processing'
    )
    
    db.session.add(photo)
    db.session.commit()
    
    # TODO: Kolejka do przetworzenia (celery task)
    # process_photo_task.delay(photo.id)
    
    return photo


def ensure_watermark(photo: Photo, *, force: bool = False, text_override: str | None = None) -> Photo:
    """Ensure watermarked image exists.

    By default, respects gallery settings (watermark_enabled and non-final galleries).
    When force=True, generates watermark even if watermark_enabled is False and/or
    for final galleries (used for unpaid previews).
    """
    gallery = photo.gallery
    if not gallery:
        return photo

    if not force:
        if not getattr(gallery, 'watermark_enabled', False):
            return photo
        if getattr(gallery, 'gallery_type', None) == 'final':
            return photo

    if photo.watermarked_path and os.path.exists(photo.watermarked_path):
        return photo

    if not photo.original_path or not os.path.exists(photo.original_path):
        return photo

    watermark_src = current_app.config.get('WATERMARK_PATH')

    photos_folder = os.path.dirname(photo.original_path)
    original_base = os.path.splitext(os.path.basename(photo.original_path))[0]
    watermarked_path = os.path.join(photos_folder, f"wm_{original_base}.jpg")

    try:
        apply_watermark(photo.original_path, watermarked_path, watermark_src, text_override=text_override)
    except Exception:
        return photo

    photo.watermarked_path = watermarked_path
    if photo.status != 'deleted':
        photo.status = 'ready'
    db.session.commit()
    return photo


def ensure_thumbnail(photo: Photo, size=(300, 300)) -> Photo:
    """Ensure thumbnail exists on disk and in DB for a photo."""
    if photo.thumbnail_path and os.path.exists(photo.thumbnail_path):
        return photo

    if not photo.original_path or not os.path.exists(photo.original_path):
        return photo

    photos_folder = os.path.dirname(photo.original_path)
    original_base = os.path.splitext(os.path.basename(photo.original_path))[0]
    thumbnail_path = os.path.join(photos_folder, f"thumb_{original_base}.jpg")

    try:
        generate_thumbnail(photo.original_path, thumbnail_path, size=size)
    except Exception:
        return photo

    photo.thumbnail_path = thumbnail_path
    if photo.status != 'deleted':
        photo.status = 'ready'
    db.session.commit()
    return photo


def ensure_watermarked_thumbnail(photo: Photo, *, size=(300, 300), text_override: str | None = None) -> str | None:
    """Create (and cache) a watermarked thumbnail on disk.

    Returns the path to the watermarked thumbnail, or None if unavailable.
    """
    if not photo:
        return None

    ensure_thumbnail(photo, size=size)
    if not photo.thumbnail_path or not os.path.exists(photo.thumbnail_path):
        return None

    photos_folder = os.path.dirname(photo.thumbnail_path)
    thumb_base = os.path.splitext(os.path.basename(photo.thumbnail_path))[0]
    wm_thumb_path = os.path.join(photos_folder, f"wm_{thumb_base}.jpg")

    if os.path.exists(wm_thumb_path):
        return wm_thumb_path

    watermark_src = current_app.config.get('WATERMARK_PATH')
    try:
        apply_watermark(photo.thumbnail_path, wm_thumb_path, watermark_src, text_override=text_override)
        return wm_thumb_path
    except Exception:
        return None


def get_photo_by_id(photo_id):
    """Pobiera zdjęcie po ID."""
    photo = db.session.get(Photo, photo_id)
    if not photo:
        raise NotFound(f'Zdjęcie #{photo_id} nie istnieje')
    return photo


def get_photos_by_gallery(gallery_id, include_hidden=False):
    """Pobiera wszystkie zdjęcia galerii."""
    query = Photo.query.filter_by(gallery_id=gallery_id)

    # Soft-deleted photos should never be listed.
    query = query.filter(Photo.status != 'deleted')
    
    if not include_hidden:
        query = query.filter(Photo.status != 'hidden')
    
    return query.order_by(Photo.display_order, Photo.uploaded_at).all()


def update_photo(photo_id, data):
    """Aktualizuje zdjęcie."""
    photo = get_photo_by_id(photo_id)
    
    allowed_fields = [
        'caption', 'display_order', 'is_favorite', 
        'is_selected', 'status', 'notes'
    ]
    
    for field in allowed_fields:
        if field in data:
            setattr(photo, field, data[field])
    
    db.session.commit()
    return photo


def toggle_photo_selection(photo_id, is_selected):
    """
    Przełącza status wyboru zdjęcia.
    
    Args:
        photo_id: ID zdjęcia
        is_selected: True/False
    
    Returns:
        Photo: zdjęcie
        
    Raises:
        BadRequest: jeśli przekroczono limit wyborów
    """
    photo = get_photo_by_id(photo_id)
    gallery = photo.gallery
    
    # Sprawdź czy galeria pozwala na wybór
    if not gallery.allow_selection:
        raise BadRequest('Wybór zdjęć nie jest włączony dla tej galerii')
    
    # Sprawdź limit wyborów
    if is_selected and gallery.max_selections:
        selected_count = gallery.selected_count
        if selected_count >= gallery.max_selections:
            raise BadRequest(
                f'Osiągnięto limit wyborów ({gallery.max_selections})'
            )
    
    photo.is_selected = is_selected
    db.session.commit()
    
    return photo


def batch_update_photos(photo_ids, action):
    """
    Aktualizuje wiele zdjęć naraz.
    
    Args:
        photo_ids: lista ID zdjęć
        action: akcja (select, deselect, favorite, unfavorite, hide, delete)
    
    Returns:
        int: liczba zaktualizowanych zdjęć
    """
    photos = Photo.query.filter(Photo.id.in_(photo_ids)).all()
    
    if not photos:
        raise NotFound('Nie znaleziono zdjęć')
    
    count = 0
    for photo in photos:
        if action == 'select':
            photo.is_selected = True
        elif action == 'deselect':
            photo.is_selected = False
        elif action == 'favorite':
            photo.is_favorite = True
        elif action == 'unfavorite':
            photo.is_favorite = False
        elif action == 'hide':
            photo.status = 'hidden'
        elif action == 'delete':
            photo.status = 'deleted'
        else:
            continue
        
        count += 1
    
    db.session.commit()
    return count


def reorder_photos(photo_orders):
    """
    Zmienia kolejność zdjęć.
    
    Args:
        photo_orders: lista dict [{photo_id, display_order}, ...]
    
    Returns:
        int: liczba zaktualizowanych zdjęć
    """
    count = 0
    for item in photo_orders:
        photo = db.session.get(Photo, item['photo_id'])
        if photo:
            photo.display_order = item['display_order']
            count += 1
    
    db.session.commit()
    return count


def delete_photo(photo_id):
    """
    Usuwa zdjęcie (soft delete).
    
    Args:
        photo_id: ID zdjęcia
    
    Returns:
        Photo: zdjęcie
    """
    photo = get_photo_by_id(photo_id)
    photo.status = 'deleted'
    db.session.commit()
    
    # TODO: Usunięcie plików z dysku (opcjonalnie)
    
    return photo


# Funkcje pomocnicze (TODO: implementacja)

def extract_exif(file_path):
    """Ekstrahuje dane EXIF ze zdjęcia."""
    # TODO: Użyć Pillow/PIL do ekstrakcji EXIF
    pass


def generate_thumbnail(original_path, thumbnail_path, size=(300, 300)):
    """Generuje miniaturkę."""
    os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

    with Image.open(original_path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")

        thumb = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
        thumb.save(thumbnail_path, format="JPEG", quality=85, optimize=True, progressive=True)


def apply_watermark(original_path, watermarked_path, watermark_path, *, text_override: str | None = None):
    """Dodaje watermark do zdjęcia.

    If watermark_path is missing/unavailable, falls back to a text watermark
    using the configured company/brand name.
    """
    os.makedirs(os.path.dirname(watermarked_path), exist_ok=True)

    def _get_brand_text() -> str:
        if isinstance(text_override, str) and text_override.strip():
            return text_override.strip()
        try:
            from app.settings.services import get_watermark_text

            return get_watermark_text()
        except Exception:
            name = (current_app.config.get('COMPANY_NAME') or 'EcoShot CRM').strip()
            return name or 'EcoShot CRM'

    def _load_font(size: int):
        # Try a common system font first, then fallback.
        try:
            return ImageFont.truetype('DejaVuSans.ttf', size=size)
        except Exception:
            try:
                return ImageFont.load_default()
            except Exception:
                return None

    def _build_text_watermark(text: str, target_w: int):
        # Create a transparent RGBA image with text and a subtle shadow.
        font_size = max(18, int(target_w * 0.16))
        font = _load_font(font_size)
        if font is None:
            raise ValueError('No font available')

        # Measure
        tmp = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        bbox = d.textbbox((0, 0), text, font=font)
        tw = max(1, bbox[2] - bbox[0])
        th = max(1, bbox[3] - bbox[1])

        pad = max(6, int(font_size * 0.4))
        img = Image.new('RGBA', (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Shadow
        sx, sy = pad + 2, pad + 2
        draw.text((sx, sy), text, font=font, fill=(0, 0, 0, 140))
        # Main text
        draw.text((pad, pad), text, font=font, fill=(255, 255, 255, 160))
        return img

    with Image.open(original_path) as base_img:
        base_img = ImageOps.exif_transpose(base_img)
        if base_img.mode != 'RGBA':
            base = base_img.convert('RGBA')
        else:
            base = base_img.copy()

    wm = None
    if watermark_path and os.path.exists(watermark_path):
        with Image.open(watermark_path) as wm_img:
            wm = wm_img.convert('RGBA')

    bw, bh = base.size
    if bw <= 0 or bh <= 0:
        raise ValueError('Invalid base image size')

    # Resize watermark to ~25% of image width.
    target_w = max(160, int(bw * 0.25))

    if wm is None:
        wm = _build_text_watermark(_get_brand_text(), target_w)

    ratio = target_w / float(wm.size[0] or 1)
    target_h = max(60, int(wm.size[1] * ratio))
    wm = wm.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Reduce opacity.
    alpha = wm.split()[-1]
    alpha = alpha.point(lambda p: int(p * 0.35))
    wm.putalpha(alpha)

    # Create tiled overlay and composite.
    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))

    # Rotate watermark for a classic diagonal pattern.
    rot = wm.rotate(-30, expand=True, resample=Image.Resampling.BICUBIC)

    pad = int(min(bw, bh) * 0.06)
    step_x = max(1, rot.size[0] + pad)
    step_y = max(1, rot.size[1] + pad)

    # Start slightly negative to cover edges.
    start_x = -rot.size[0]
    start_y = -rot.size[1]

    for y in range(start_y, bh + rot.size[1], step_y):
        for x in range(start_x, bw + rot.size[0], step_x):
            overlay.paste(rot, (x, y), rot)

    out = Image.alpha_composite(base, overlay)

    # Save as JPEG
    out_rgb = out.convert('RGB')
    out_rgb.save(watermarked_path, format='JPEG', quality=85, optimize=True, progressive=True)

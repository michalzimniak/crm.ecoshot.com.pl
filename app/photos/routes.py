"""Photos REST API endpoints.

Handles photo upload, selection, reordering, and basic metadata management.
"""

import os

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from werkzeug.exceptions import NotFound, Forbidden
from werkzeug.utils import secure_filename

from app.core.decorators import api_endpoint, public_endpoint
from app.core.enforcement import can_download_final_gallery, EnforcementError
from app.core.permissions import Permission
from app.photos import services
from app.photos.schemas import (
    photo_batch_update_schema,
    photo_reorder_schema,
    photo_schema,
    photo_update_schema,
    photos_schema,
)

photos_bp = Blueprint("photos", __name__)


@photos_bp.route("", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_GALLERIES)
def get_photos():
    """Get photos for a gallery."""
    gallery_id = request.args.get("gallery_id")
    if not gallery_id:
        return jsonify({"success": False, "error": "gallery_id wymagane"}), 400

    include_hidden = request.args.get("include_hidden") == "true"
    photos = services.get_photos_by_gallery(int(gallery_id), include_hidden=include_hidden)

    if request.args.get("is_selected") is not None:
        is_selected = request.args.get("is_selected") == "true"
        photos = [p for p in photos if bool(p.is_selected) == is_selected]

    return jsonify({"success": True, "data": photos_schema.dump(photos)})


@photos_bp.route("/<int:photo_id>", methods=["GET"])
@api_endpoint(permission=Permission.VIEW_GALLERIES)
def get_photo(photo_id: int):
    """Get photo by ID."""
    photo = services.get_photo_by_id(photo_id)
    return jsonify({"success": True, "data": photo_schema.dump(photo)})


@photos_bp.route("/upload", methods=["POST"])
@api_endpoint(permission=Permission.UPLOAD_PHOTO)
def upload_photos():
    """Upload multiple photos to a gallery (multipart)."""
    if "files" not in request.files and "file" not in request.files:
        return jsonify({"success": False, "error": "Brak plików"}), 400

    gallery_id = request.form.get("gallery_id")
    if not gallery_id:
        return jsonify({"success": False, "error": "gallery_id wymagane"}), 400

    files = request.files.getlist("files")
    if not files and "file" in request.files:
        files = [request.files["file"]]

    created = []
    for f in files:
        filename = secure_filename(getattr(f, "filename", "") or "")
        if not filename:
            continue
        photo = services.create_photo({"gallery_id": int(gallery_id), "filename": filename}, file=f)
        created.append(photo)

    return (
        jsonify(
            {
                "success": True,
                "data": photos_schema.dump(created),
                "message": f"Dodano {len(created)} zdjęć",
            }
        ),
        201,
    )


@photos_bp.route("/<int:photo_id>", methods=["PUT"])
@api_endpoint(permission=Permission.EDIT_PHOTO)
def update_photo(photo_id: int):
    """Update photo metadata."""
    data = request.get_json() or {}

    errors = photo_update_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    photo = services.update_photo(photo_id, data)
    return jsonify(
        {
            "success": True,
            "data": photo_schema.dump(photo),
            "message": "Zdjęcie zaktualizowane",
        }
    )


@photos_bp.route("/<int:photo_id>/toggle-selection", methods=["POST"])
@public_endpoint
def toggle_selection(photo_id: int):
    """Toggle photo selection (public for client)."""
    # Must be authorized by gallery PIN session (GALLERYPROMPT.md).
    verify_jwt_in_request()
    claims = get_jwt() or {}
    if claims.get('token_type') != 'gallery':
        return jsonify({'success': False, 'error': 'Nieprawidłowy token', 'code': 'UNAUTHORIZED'}), 401

    data = request.get_json() or {}
    is_selected = data.get("is_selected", True)

    photo = services.get_photo_by_id(photo_id)
    if int(claims.get('gallery_id') or 0) != int(photo.gallery_id):
        return jsonify({'success': False, 'error': 'Token nie pasuje do galerii', 'code': 'UNAUTHORIZED'}), 401

    photo = services.toggle_photo_selection(photo_id, is_selected)

    return jsonify(
        {
            "success": True,
            "data": photo_schema.dump(photo),
            "message": "Wybrano zdjęcie" if is_selected else "Odznaczono zdjęcie",
        }
    )


@photos_bp.route("/batch-update", methods=["PUT"])
@api_endpoint(permission=Permission.EDIT_PHOTO)
def batch_update_photos():
    """Batch update photos (select/deselect/favorite/etc.)."""
    data = request.get_json() or {}

    errors = photo_batch_update_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    updated_count = services.batch_update_photos(data["photo_ids"], data["action"])

    return jsonify(
        {
            "success": True,
            "data": {"updated": updated_count},
            "message": f"Zaktualizowano {updated_count} zdjęć",
        }
    )


@photos_bp.route("/reorder", methods=["PUT"])
@api_endpoint(permission=Permission.EDIT_PHOTO)
def reorder_photos():
    """Reorder photos in gallery."""
    data = request.get_json() or {}

    errors = photo_reorder_schema.validate(data)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    updated = services.reorder_photos(data["photo_orders"])

    return jsonify(
        {
            "success": True,
            "data": {"updated": updated},
            "message": "Kolejność zdjęć zaktualizowana",
        }
    )


@photos_bp.route("/<int:photo_id>/download", methods=["GET"])
@public_endpoint
def download_photo(photo_id: int):
    """Download photo (watermarked for proofing, original for final)."""
    version = request.args.get("version", "watermarked")  # watermarked, original, thumbnail

    photo = services.get_photo_by_id(photo_id)
    gallery = photo.gallery
    gallery_type = getattr(gallery, "gallery_type", None)

    # Payment-aware watermark enforcement (GALLERYPROMPT.md):
    # If invoice is not paid -> ALWAYS watermark for any preview/web image and
    # NO access to full-res originals.
    invoice_paid = False
    watermark_text = None
    if gallery and getattr(gallery, 'job_id', None):
        try:
            from app.invoices.models import Invoice

            invoice = Invoice.query.filter_by(job_id=gallery.job_id).first()
            if invoice and float(invoice.paid_amount or 0) >= float(invoice.total_amount or 0):
                invoice_paid = True
        except Exception:
            invoice_paid = False

        try:
            customer_name = None
            if getattr(gallery, 'job', None) and getattr(gallery.job, 'customer', None):
                customer_name = getattr(gallery.job.customer, 'display_name', None) or getattr(gallery.job.customer, 'full_name', None)
            customer_name = (customer_name or '').strip()
            watermark_text = f"{customer_name} • Zlecenie #{gallery.job_id}" if customer_name else f"Zlecenie #{gallery.job_id}"
        except Exception:
            watermark_text = None

    mimetype = photo.mime_type or "application/octet-stream"
    as_attachment = version == "original"

    if not invoice_paid:
        # Unpaid: always watermark for any preview/web version; never allow original.
        if version == 'original':
            raise Forbidden('Pliki full-res będą dostępne po opłaceniu')

        if version == 'thumbnail':
            wm_thumb = services.ensure_watermarked_thumbnail(photo, text_override=watermark_text)
            if wm_thumb:
                file_path = wm_thumb
                mimetype = 'image/jpeg'
            else:
                services.ensure_thumbnail(photo)
                file_path = photo.thumbnail_path or photo.original_path
            as_attachment = False
        else:
            services.ensure_watermark(photo, force=True, text_override=watermark_text)
            file_path = photo.watermarked_path or photo.original_path
            mimetype = "image/jpeg" if photo.watermarked_path else mimetype
            as_attachment = False
    else:
        if version == "thumbnail":
            services.ensure_thumbnail(photo)
            file_path = photo.thumbnail_path or photo.original_path
            mimetype = "image/jpeg" if photo.thumbnail_path else mimetype
            as_attachment = False
        elif version == "original":
            if gallery_type != "final":
                raise Forbidden("Oryginał dostępny tylko dla galerii finalnej")
            # If someone can fetch originals by id, it bypasses ZIP enforcement,
            # so enforce the same business rule here.
            if gallery and getattr(gallery, "job_id", None):
                can_download_final_gallery(gallery.job_id)
            file_path = photo.original_path
        else:
            # Default: 'watermarked'
            as_attachment = False

            if gallery_type == "final":
                # Final galleries: originals are paywalled by enforcement.
                eligible = False
                if gallery and getattr(gallery, "job_id", None):
                    try:
                        can_download_final_gallery(gallery.job_id)
                        eligible = True
                    except EnforcementError:
                        eligible = False

                if eligible:
                    file_path = photo.original_path
                else:
                    # If not eligible (e.g., unpaid/other enforcement), serve watermark
                    # when enabled so UI can show previews.
                    if gallery:
                        services.ensure_watermark(photo, force=bool(getattr(gallery, 'watermark_enabled', False)), text_override=watermark_text)
                    if photo.watermarked_path:
                        file_path = photo.watermarked_path
                        mimetype = "image/jpeg" if photo.watermarked_path else mimetype
                    else:
                        raise Forbidden("Finalna galeria będzie dostępna po spełnieniu warunków")
            else:
                if gallery and getattr(gallery, "watermark_enabled", False):
                    services.ensure_watermark(photo, text_override=watermark_text)
                    file_path = photo.watermarked_path
                    mimetype = "image/jpeg" if photo.watermarked_path else mimetype
                else:
                    # Watermark disabled (or missing gallery): fall back to original.
                    file_path = photo.original_path

    if not file_path or not os.path.exists(file_path):
        raise NotFound("Plik nie istnieje")

    kwargs = {
        "mimetype": mimetype,
        "as_attachment": as_attachment,
    }
    if as_attachment:
        kwargs["download_name"] = photo.filename

    return send_file(file_path, **kwargs)


@photos_bp.route("/<int:photo_id>", methods=["DELETE"])
@api_endpoint(permission=Permission.DELETE_PHOTO)
def delete_photo(photo_id: int):
    """Delete photo (soft delete)."""
    services.delete_photo(photo_id)
    return jsonify({"success": True, "message": "Zdjęcie usunięte"})

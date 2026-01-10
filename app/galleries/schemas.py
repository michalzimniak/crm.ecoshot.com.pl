"""
Marshmallow schemas for galleries.
Handles validation and serialization for Gallery model.
"""

from marshmallow import EXCLUDE, Schema, fields, validate, pre_load
from app.extensions import ma
from app.galleries.models import Gallery


class GallerySchema(ma.SQLAlchemyAutoSchema):
    """Schema for Gallery model."""
    
    class Meta:
        model = Gallery
        load_instance = True
        include_fk = True
        exclude = ('password_hash',)  # Nigdy nie zwracamy hasha hasła
        dump_only = ('id', 'created_at', 'updated_at', 'published_at', 'zip_generated_at', 'last_viewed_at')
    
    # Custom fields
    is_published = fields.Boolean(dump_only=True)
    is_expired = fields.Boolean(dump_only=True)
    photo_count = fields.Integer(dump_only=True)
    selected_count = fields.Integer(dump_only=True)
    has_password = fields.Boolean(dump_only=True)

    public_hash = fields.String(dump_only=True)

    # Backward-compatible alias expected by the frontend.
    name = fields.String(attribute="title", dump_only=True)
    
    # Nested
    job = fields.Nested('JobSchema', dump_only=True)
    photos = fields.Nested('PhotoSchema', many=True, dump_only=True)
    
    # Validation
    gallery_type = fields.String(
        required=True,
        validate=validate.OneOf(['proof', 'selection', 'final', 'archive'])
    )
    status = fields.String(
        validate=validate.OneOf(['draft', 'published', 'archived'])
    )


class GalleryCreateSchema(Schema):
    """Schema for creating new gallery."""

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def normalize_payload(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        data = dict(data)

        # Frontend sends `name` for the title.
        if data.get('title') is None and data.get('name') is not None:
            data['title'] = data.get('name')

        # Backwards compatibility: old UI used 'proofing'.
        if data.get('gallery_type') == 'proofing':
            data['gallery_type'] = 'proof'

        # Accept date-only expiry (YYYY-MM-DD) from <input type="date">.
        expires_at = data.get('expires_at')
        if isinstance(expires_at, str):
            raw = expires_at.strip()
            if raw and 'T' not in raw and ' ' not in raw:
                data['expires_at'] = f"{raw}T23:59:59"

        return data
    
    job_id = fields.Integer(required=True)
    gallery_type = fields.String(
        required=True,
        validate=validate.OneOf(['proof', 'selection', 'final', 'archive'])
    )
    title = fields.String(
        required=True,
        validate=validate.Length(min=1, max=200)
    )
    description = fields.String(allow_none=True)
    
    password = fields.String(load_only=True)  # Opcjonalne hasło
    expires_at = fields.DateTime(allow_none=True)
    
    allow_download = fields.Boolean()
    allow_selection = fields.Boolean()
    max_selections = fields.Integer(allow_none=True, validate=validate.Range(min=0))
    watermark_enabled = fields.Boolean()
    expiration_days = fields.Integer(allow_none=True, validate=validate.Range(min=1))
    
    notes = fields.String(allow_none=True)


class GalleryUpdateSchema(Schema):
    """Schema for updating gallery."""

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def normalize_payload(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        data = dict(data)

        # Frontend uses `name`.
        if data.get('title') is None and data.get('name') is not None:
            data['title'] = data.get('name')

        # Backwards compatibility: old UI used 'proofing'.
        if data.get('gallery_type') == 'proofing':
            data['gallery_type'] = 'proof'

        expires_at = data.get('expires_at')
        if isinstance(expires_at, str):
            raw = expires_at.strip()
            if raw and 'T' not in raw and ' ' not in raw:
                data['expires_at'] = f"{raw}T23:59:59"

        return data
    
    title = fields.String(validate=validate.Length(min=1, max=200))
    gallery_type = fields.String(
        validate=validate.OneOf(['proof', 'selection', 'final', 'archive'])
    )
    description = fields.String(allow_none=True)
    
    password = fields.String(load_only=True)
    expires_at = fields.DateTime(allow_none=True)
    
    allow_download = fields.Boolean()
    allow_selection = fields.Boolean()
    max_selections = fields.Integer(allow_none=True, validate=validate.Range(min=0))
    watermark_enabled = fields.Boolean()
    expiration_days = fields.Integer(allow_none=True, validate=validate.Range(min=1))
    
    notes = fields.String(allow_none=True)


class GalleryStatusUpdateSchema(Schema):
    """Schema for updating gallery status."""
    
    status = fields.String(
        required=True,
        validate=validate.OneOf(['draft', 'published', 'archived'])
    )


class GalleryAccessSchema(Schema):
    """Schema for gallery access (client view)."""
    
    access_token = fields.String(required=True)
    password = fields.String()


class GalleryTypePatchSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    gallery_type = fields.String(required=True, validate=validate.OneOf(['proof', 'selection', 'final', 'archive']))


class GallerySettingsPatchSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    allow_download = fields.Boolean(allow_none=True)
    allow_selection = fields.Boolean(allow_none=True)
    watermark_enabled = fields.Boolean(allow_none=True)
    expiration_days = fields.Integer(allow_none=True, validate=validate.Range(min=1))


# Schema instances
gallery_schema = GallerySchema()
galleries_schema = GallerySchema(many=True)
gallery_create_schema = GalleryCreateSchema()
gallery_update_schema = GalleryUpdateSchema()
gallery_status_update_schema = GalleryStatusUpdateSchema()
gallery_access_schema = GalleryAccessSchema()

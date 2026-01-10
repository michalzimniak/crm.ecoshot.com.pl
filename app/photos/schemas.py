"""
Marshmallow schemas for photos.
Handles validation and serialization for Photo model.
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app.extensions import ma
from app.photos.models import Photo


class PhotoSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Photo model."""
    
    class Meta:
        model = Photo
        load_instance = True
        dump_only = ('id', 'created_at', 'updated_at', 'uploaded_at')
    
    # Custom fields
    resolution = fields.String(dump_only=True)
    file_size_mb = fields.Float(dump_only=True)
    display_path = fields.String(dump_only=True)
    
    # Nested
    gallery = fields.Nested('GallerySchema', dump_only=True, exclude=('photos',))
    
    # Validation
    status = fields.String(
        validate=validate.OneOf(['processing', 'ready', 'hidden', 'deleted'])
    )


class PhotoUploadSchema(Schema):
    """Schema for photo upload metadata."""
    
    gallery_id = fields.Integer(required=True)
    filename = fields.String(required=True, validate=validate.Length(min=1, max=255))
    
    caption = fields.String(validate=validate.Length(max=500))
    display_order = fields.Integer()
    is_favorite = fields.Boolean()
    notes = fields.String()


class PhotoUpdateSchema(Schema):
    """Schema for updating photo."""
    
    caption = fields.String(validate=validate.Length(max=500))
    display_order = fields.Integer()
    is_favorite = fields.Boolean()
    is_selected = fields.Boolean()
    status = fields.String(
        validate=validate.OneOf(['processing', 'ready', 'hidden', 'deleted'])
    )
    notes = fields.String()


class PhotoSelectionToggleSchema(Schema):
    """Schema for toggling photo selection."""
    
    is_selected = fields.Boolean(required=True)


class PhotoBatchUpdateSchema(Schema):
    """Schema for batch photo operations."""
    
    photo_ids = fields.List(
        fields.Integer(),
        required=True,
        validate=validate.Length(min=1)
    )
    action = fields.String(
        required=True,
        validate=validate.OneOf(['select', 'deselect', 'favorite', 'unfavorite', 'hide', 'delete'])
    )


class PhotoReorderSchema(Schema):
    """Schema for reordering photos."""
    
    photo_orders = fields.List(
        fields.Dict(
            keys=fields.String(),
            values=fields.Integer()
        ),
        required=True,
        validate=validate.Length(min=1)
    )
    
    @validates_schema
    def validate_photo_orders(self, data, **kwargs):
        """Walidacja struktury danych."""
        for item in data.get('photo_orders', []):
            if 'photo_id' not in item or 'display_order' not in item:
                raise ValidationError(
                    'Każdy element musi zawierać photo_id i display_order',
                    'photo_orders'
                )


# Schema instances
photo_schema = PhotoSchema()
photos_schema = PhotoSchema(many=True)
photo_upload_schema = PhotoUploadSchema()
photo_update_schema = PhotoUpdateSchema()
photo_selection_toggle_schema = PhotoSelectionToggleSchema()
photo_batch_update_schema = PhotoBatchUpdateSchema()
photo_reorder_schema = PhotoReorderSchema()

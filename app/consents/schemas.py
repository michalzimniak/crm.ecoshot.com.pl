"""Marshmallow schemas for consents.

Validation and serialization for Consent model.
"""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.consents.models import Consent
from app.extensions import ma


class ConsentSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Consent model."""

    class Meta:
        model = Consent
        load_instance = True
        include_fk = True
        # Don't expose signature data nor server file paths.
        exclude = ("signature_data", "pdf_path", "signed_scan_path")
        dump_only = (
            "id",
            "created_at",
            "updated_at",
            "granted_at",
            "revoked_at",
            "signed_scan_uploaded_at",
        )

    is_active = fields.Boolean(dump_only=True)
    has_signature = fields.Boolean(dump_only=True)
    has_signed_scan = fields.Boolean(dump_only=True)

    job = fields.Nested("JobSchema", dump_only=True)

    consent_type = fields.String(
        required=True,
        validate=validate.OneOf(["image_publication", "data_processing", "marketing"]),
    )


class ConsentCreateSchema(Schema):
    """Schema for creating new consent."""

    job_id = fields.Integer(required=True)
    consent_type = fields.String(
        required=True,
        validate=validate.OneOf(["image_publication", "data_processing", "marketing"]),
    )
    # For image_publication, backend can fill in default template.
    consent_text = fields.String(required=False, allow_none=True)
    scope = fields.String(validate=validate.Length(max=200))
    notes = fields.String()

    @validates_schema
    def validate_text(self, data, **kwargs):
        consent_type = data.get("consent_type")
        consent_text = (data.get("consent_text") or "").strip()

        # For image_publication and data_processing backend can fill in default templates.
        if consent_type not in {"image_publication", "data_processing"} and not consent_text:
            raise ValidationError("Treść zgody jest wymagana", "consent_text")


class ConsentUpdateSchema(Schema):
    """Schema for updating consent."""

    consent_text = fields.String()
    scope = fields.String(validate=validate.Length(max=200))
    notes = fields.String()


class ConsentGrantSchema(Schema):
    """Schema for granting consent."""

    signature_data = fields.String(required=True)  # Base64
    ip_address = fields.String()

    @validates_schema
    def validate_signature(self, data, **kwargs):
        signature = data.get("signature_data")
        if not signature or len(signature) < 100:
            raise ValidationError("Nieprawidłowe dane podpisu", "signature_data")


class ConsentRevokeSchema(Schema):
    """Schema for revoking consent."""

    reason = fields.String(required=True, validate=validate.Length(min=10))


consent_schema = ConsentSchema()
consents_schema = ConsentSchema(many=True)
consent_create_schema = ConsentCreateSchema()
consent_update_schema = ConsentUpdateSchema()
consent_grant_schema = ConsentGrantSchema()
consent_revoke_schema = ConsentRevokeSchema()

"""Marshmallow schemas for settings."""

from marshmallow import EXCLUDE, Schema, fields, validate


class CompanySettingsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(allow_none=True, validate=validate.Length(max=255))
    address = fields.String(allow_none=True, validate=validate.Length(max=255))
    nip = fields.String(allow_none=True, validate=validate.Length(max=50))
    phone = fields.String(allow_none=True, validate=validate.Length(max=50))
    email = fields.String(allow_none=True, validate=validate.Length(max=255))
    bank = fields.String(allow_none=True, validate=validate.Length(max=255))
    account = fields.String(allow_none=True, validate=validate.Length(max=255))


class InvoiceSettingsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    prefix = fields.String(allow_none=True, validate=validate.Length(max=50))
    deposit_prefix = fields.String(allow_none=True, validate=validate.Length(max=50))
    year_format = fields.String(allow_none=True, validate=validate.Length(max=50))
    vat_rate = fields.String(
        allow_none=True,
        validate=validate.OneOf(["0", "5", "8", "23", "0.00", "5.00", "8.00", "23.00"]),
    )
    vat_exempt = fields.Boolean()


class BrandingSettingsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.String(allow_none=True, validate=validate.Length(max=100))


class WatermarkSettingsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    text = fields.String(allow_none=True, validate=validate.Length(max=120))


class CanvaIntegrationSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    access_token = fields.String(allow_none=True, validate=validate.Length(max=2000))
    client_id = fields.String(allow_none=True, validate=validate.Length(max=255))
    client_secret = fields.String(allow_none=True, validate=validate.Length(max=2000))


class IntegrationsSettingsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    canva = fields.Nested(CanvaIntegrationSchema)


class SettingsUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    company = fields.Nested(CompanySettingsSchema)
    invoice = fields.Nested(InvoiceSettingsSchema)
    branding = fields.Nested(BrandingSettingsSchema)
    watermark = fields.Nested(WatermarkSettingsSchema)
    integrations = fields.Nested(IntegrationsSettingsSchema)


settings_update_schema = SettingsUpdateSchema()

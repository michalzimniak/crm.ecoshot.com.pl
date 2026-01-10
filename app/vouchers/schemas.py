"""Marshmallow schemas for vouchers."""

from marshmallow import EXCLUDE, Schema, fields, validate

from app.extensions import ma
from app.vouchers.models import Voucher


class VoucherSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Voucher
        load_instance = True
        dump_only = ("id", "created_at", "updated_at")

    code = fields.String(dump_only=True)
    issued_at = fields.DateTime(dump_only=True)
    expires_at = fields.DateTime(dump_only=True)
    used_at = fields.DateTime(dump_only=True, allow_none=True)
    is_used = fields.Boolean(dump_only=True)
    is_expired = fields.Boolean(dump_only=True)
    is_valid = fields.Boolean(dump_only=True)

    promotion_id = fields.Integer(required=True)


class VoucherGenerateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    promotion_id = fields.Integer(required=True)
    count = fields.Integer(required=True, validate=validate.Range(min=1, max=200))


voucher_schema = VoucherSchema()
vouchers_schema = VoucherSchema(many=True)

voucher_generate_schema = VoucherGenerateSchema()

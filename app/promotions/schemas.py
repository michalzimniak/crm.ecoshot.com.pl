"""Marshmallow schemas for promotions."""

from datetime import datetime

from marshmallow import EXCLUDE, Schema, fields, validate
from sqlalchemy import func

from app.extensions import db
from app.extensions import ma
from app.promotions.models import Promotion
from app.vouchers.models import Voucher


class PromotionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Promotion
        load_instance = True
        dump_only = ("id", "created_at", "updated_at")

    promo_type = fields.String(required=True, validate=validate.Length(min=1, max=50))
    value = fields.Decimal(required=True, as_string=True)
    duration_days = fields.Integer(required=True)

    activated_at = fields.DateTime(dump_only=True, allow_none=True)
    active_until = fields.Method("get_active_until", dump_only=True, allow_none=True)

    canva_project_url = fields.String(allow_none=True)
    voucher_bg_front_path = fields.String(dump_only=True, allow_none=True)
    voucher_bg_back_path = fields.String(dump_only=True, allow_none=True)

    voucher_text_x_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_y_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_x_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_y_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_font_family = fields.String(allow_none=True)
    voucher_text_font_size_pt = fields.Decimal(as_string=True, allow_none=True)

    is_active = fields.Boolean(dump_only=True)

    def get_active_until(self, obj: Promotion):
        now = datetime.utcnow()
        value = (
            db.session.query(func.max(Voucher.expires_at))
            .filter(Voucher.promotion_id == obj.id)
            .filter(Voucher.used_at.is_(None))
            .filter(Voucher.expires_at >= now)
            .scalar()
        )
        return value.isoformat() if value else None


class PromotionCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    promo_type = fields.String(required=True, validate=validate.Length(min=1, max=50))
    value = fields.Decimal(required=True, as_string=True, validate=validate.Range(min=0))
    duration_days = fields.Integer(required=True, validate=validate.Range(min=1, max=3650))

    canva_project_url = fields.String(allow_none=True, validate=validate.Length(max=500))

    voucher_text_x_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_y_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_x_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_y_px = fields.Decimal(as_string=True, allow_none=True)

    # Legacy: mm inputs (converted to px by services).
    voucher_text_x_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_y_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_x_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_y_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_font_family = fields.String(allow_none=True, validate=validate.Length(max=200))
    voucher_text_font_size_pt = fields.Decimal(as_string=True, allow_none=True)


class PromotionUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    promo_type = fields.String(validate=validate.Length(min=1, max=50))
    value = fields.Decimal(as_string=True, validate=validate.Range(min=0))
    duration_days = fields.Integer(validate=validate.Range(min=1, max=3650))

    canva_project_url = fields.String(allow_none=True, validate=validate.Length(max=500))

    voucher_text_x_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_y_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_x_px = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_y_px = fields.Decimal(as_string=True, allow_none=True)

    # Legacy: mm inputs (converted to px by services).
    voucher_text_x_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_y_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_x_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_qr_y_mm = fields.Decimal(as_string=True, allow_none=True)
    voucher_text_font_family = fields.String(allow_none=True, validate=validate.Length(max=200))
    voucher_text_font_size_pt = fields.Decimal(as_string=True, allow_none=True)


promotion_schema = PromotionSchema()
promotions_schema = PromotionSchema(many=True)

promotion_create_schema = PromotionCreateSchema()
promotion_update_schema = PromotionUpdateSchema()

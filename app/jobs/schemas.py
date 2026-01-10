"""Marshmallow schemas for jobs.

Handles validation and serialization for Job, Offer, OfferAddon models.
"""

from marshmallow import EXCLUDE, Schema, fields, validate

from app.extensions import ma
from app.jobs.models import Job, Offer, OfferAddon, JobAddon


class OfferAddonSchema(ma.SQLAlchemyAutoSchema):
    """Schema for OfferAddon model."""

    class Meta:
        model = OfferAddon
        load_instance = True
        dump_only = ("id",)


class OfferSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Offer model."""

    class Meta:
        model = Offer
        load_instance = True
        dump_only = ("id", "created_at", "updated_at")

    addons = fields.Nested(OfferAddonSchema, many=True, dump_only=True)


class JobAddonSchema(ma.SQLAlchemyAutoSchema):
    """Schema for JobAddon model."""

    class Meta:
        model = JobAddon
        load_instance = True
        dump_only = ("id", "created_at")


class JobSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Job model."""

    class Meta:
        model = Job
        load_instance = True
        dump_only = (
            "id",
            "created_at",
            "updated_at",
            "quote_sent_at",
            "accepted_at",
            "completed_at",
        )

    # Nested relationships
    customer = fields.Nested("CustomerSchema", dump_only=True)
    offer = fields.Nested(OfferSchema, dump_only=True)
    addons = fields.Nested(JobAddonSchema, many=True, dump_only=True)

    # Contract relationship exists on the model, but we keep it minimal here.
    # This also allows other schemas to safely exclude("contract") when nesting JobSchema.
    contract = fields.Integer(attribute="contract.id", dump_only=True)

    voucher_id = fields.Integer(dump_only=True, allow_none=True)
    discount_amount = fields.Decimal(as_string=True, dump_only=True)
    voucher_code = fields.String(attribute="voucher.code", dump_only=True, allow_none=True)

    # Validation
    status = fields.String(
        validate=validate.OneOf(
            [
                "draft",
                "quote_sent",
                "accepted",
                "rejected",
                "in_progress",
                "completed",
                "cancelled",
            ]
        )
    )


class JobCreateSchema(Schema):
    """Schema for creating new job."""

    class Meta:
        unknown = EXCLUDE

    customer_id = fields.Integer(required=True)
    offer_id = fields.Integer(required=True)

    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(allow_none=True)
    # Preferred field going forward (includes time). Frontend uses datetime-local.
    event_start = fields.DateTime()
    # Backward-compatibility for older clients.
    event_date = fields.Date()
    event_location = fields.String(validate=validate.Length(max=300))

    base_price = fields.Decimal(as_string=True, allow_none=True)
    notes = fields.String(allow_none=True)
    internal_notes = fields.String(allow_none=True)

    voucher_code = fields.String(allow_none=True, validate=validate.Length(max=100))

    # Add-ons can be empty.
    selected_addon_ids = fields.List(fields.Integer(), load_default=list)
    addon_quantities = fields.Dict(
        keys=fields.String(),
        values=fields.Integer(),
        load_default=dict,
    )


class JobUpdateSchema(Schema):
    """Schema for updating job."""

    title = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String(allow_none=True)
    event_start = fields.DateTime()
    event_date = fields.Date()
    event_location = fields.String(validate=validate.Length(max=300))

    notes = fields.String(allow_none=True)
    internal_notes = fields.String(allow_none=True)

    voucher_code = fields.String(allow_none=True, validate=validate.Length(max=100))


class JobStatusUpdateSchema(Schema):
    """Schema for updating job status."""

    status = fields.String(
        required=True,
        validate=validate.OneOf(
            [
                "draft",
                "quote_sent",
                "accepted",
                "rejected",
                "in_progress",
                "completed",
                "cancelled",
            ]
        ),
    )


class JobAddonToggleSchema(Schema):
    """Schema for toggling job addon selection."""

    addon_id = fields.Integer(required=True)
    is_selected = fields.Boolean(required=True)


class OfferCreateSchema(Schema):
    """Schema for creating offer (seed data)."""

    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String()
    base_price = fields.Decimal(required=True, as_string=True)

    hours_included = fields.Integer()
    photos_count = fields.Integer()
    video_included = fields.Boolean()

    is_active = fields.Boolean()
    display_order = fields.Integer()


class OfferUpdateSchema(Schema):
    """Schema for updating offer."""

    name = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String(allow_none=True)
    base_price = fields.Decimal(as_string=True)

    hours_included = fields.Integer(allow_none=True)
    photos_count = fields.Integer(allow_none=True)
    video_included = fields.Boolean(allow_none=True)

    is_active = fields.Boolean()
    display_order = fields.Integer()


class OfferAddonCreateSchema(Schema):
    """Schema for creating offer addon."""

    offer_id = fields.Integer(required=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String()
    price = fields.Decimal(required=True, as_string=True)

    pricing_model = fields.String(validate=validate.OneOf(["fixed", "per_unit"]))
    category = fields.String(validate=validate.Length(max=50))
    duration_months = fields.Integer(allow_none=True)

    is_available = fields.Boolean()
    display_order = fields.Integer()


class OfferAddonUpdateSchema(Schema):
    """Schema for updating offer addon."""

    offer_id = fields.Integer()
    name = fields.String(validate=validate.Length(min=1, max=200))
    description = fields.String(allow_none=True)
    price = fields.Decimal(as_string=True)

    pricing_model = fields.String(validate=validate.OneOf(["fixed", "per_unit"]))
    category = fields.String(validate=validate.Length(max=50))
    duration_months = fields.Integer(allow_none=True)

    is_available = fields.Boolean()
    display_order = fields.Integer()


# Schema instances
job_schema = JobSchema()
jobs_schema = JobSchema(many=True)
job_create_schema = JobCreateSchema()
job_update_schema = JobUpdateSchema()
job_status_update_schema = JobStatusUpdateSchema()
job_addon_toggle_schema = JobAddonToggleSchema()

offer_schema = OfferSchema()
offers_schema = OfferSchema(many=True)
offer_create_schema = OfferCreateSchema()
offer_update_schema = OfferUpdateSchema()

offer_addon_schema = OfferAddonSchema()
offer_addons_schema = OfferAddonSchema(many=True)
offer_addon_create_schema = OfferAddonCreateSchema()
offer_addon_update_schema = OfferAddonUpdateSchema()

job_addon_schema = JobAddonSchema()
job_addons_schema = JobAddonSchema(many=True)

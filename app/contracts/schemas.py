"""Marshmallow schemas for contracts.

Validation + serialization for Contract model.
"""

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.contracts.models import Contract
from app.extensions import ma


class ContractSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Contract model."""

    class Meta:
        model = Contract
        load_instance = True
        include_fk = True
        exclude = ("signature_data",)
        dump_only = ("id", "created_at", "updated_at", "signed_at", "sent_at")

    # Computed
    is_signed = fields.Boolean(dump_only=True)
    is_valid = fields.Boolean(dump_only=True)
    has_signature = fields.Boolean(dump_only=True)
    has_signed_scan = fields.Boolean(dump_only=True)

    # Nested
    job = fields.Nested("JobSchema", dump_only=True, exclude=("contract",))

    status = fields.String(
        validate=validate.OneOf(["draft", "sent", "signed", "rejected", "cancelled"])
    )


class ContractCreateSchema(Schema):
    """Schema for creating new contract."""

    job_id = fields.Integer(required=True)
    valid_until = fields.Date()
    terms_content = fields.String()
    notes = fields.String()


class ContractUpdateSchema(Schema):
    """Schema for updating contract."""

    valid_until = fields.Date()
    terms_content = fields.String()
    notes = fields.String()

    # Zaliczka (tracking)
    deposit_percent = fields.Decimal(as_string=True)
    deposit_amount = fields.Decimal(as_string=True)
    deposit_status = fields.String(validate=validate.OneOf(["unpaid", "paid", "waived"]))
    deposit_paid_amount = fields.Decimal(as_string=True)
    deposit_paid_at = fields.DateTime()
    deposit_notes = fields.String()


class ContractSignSchema(Schema):
    """Schema for signing contract."""

    signature_data = fields.String(required=True)  # Base64
    ip_address = fields.String()

    @validates_schema
    def validate_signature(self, data, **kwargs):
        signature = data.get("signature_data")
        if not signature or len(signature) < 100:
            raise ValidationError("Nieprawidłowe dane podpisu", "signature_data")


class ContractStatusUpdateSchema(Schema):
    """Schema for updating contract status."""

    status = fields.String(
        required=True,
        validate=validate.OneOf(["draft", "sent", "signed", "rejected", "cancelled"]),
    )


contract_schema = ContractSchema()
contracts_schema = ContractSchema(many=True)
contract_create_schema = ContractCreateSchema()
contract_update_schema = ContractUpdateSchema()
contract_sign_schema = ContractSignSchema()
contract_status_update_schema = ContractStatusUpdateSchema()

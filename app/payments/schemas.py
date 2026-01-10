"""Marshmallow schemas for payments."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.extensions import ma
from app.payments.models import Payment


class PaymentSchema(ma.SQLAlchemyAutoSchema):
	class Meta:
		model = Payment
		load_instance = True
		dump_only = ('id', 'created_at', 'updated_at')

	is_completed = fields.Boolean(dump_only=True)

	invoice = fields.Nested('InvoiceSchema', dump_only=True, exclude=('payments',))
	job = fields.Nested('JobSchema', dump_only=True, exclude=('addons', 'offer', 'customer'))

	kind = fields.String(validate=validate.OneOf(['invoice', 'deposit', 'prepayment']))
	source = fields.String(validate=validate.OneOf(['manual', 'payu']))
	currency = fields.String(validate=validate.Length(equal=3))
	status = fields.String(validate=validate.OneOf(['pending', 'completed', 'failed', 'refunded']))
	payment_method = fields.String(validate=validate.OneOf(['transfer', 'cash', 'card', 'paypal', 'other']))


class PaymentCreateSchema(Schema):
	invoice_id = fields.Integer(allow_none=True)
	job_id = fields.Integer(allow_none=True)

	amount = fields.Decimal(required=True, as_string=True, validate=validate.Range(min=0.01))
	currency = fields.String(validate=validate.Length(equal=3))

	kind = fields.String(required=True, validate=validate.OneOf(['invoice', 'deposit', 'prepayment']))
	source = fields.String(required=True, validate=validate.OneOf(['manual', 'payu']))
	payment_method = fields.String(required=True, validate=validate.OneOf(['transfer', 'cash', 'card', 'paypal', 'other']))
	status = fields.String(validate=validate.OneOf(['pending', 'completed']))

	payment_date = fields.DateTime()
	transaction_id = fields.String(validate=validate.Length(max=100))
	reference = fields.String(validate=validate.Length(max=200))
	notes = fields.String()

	@validates_schema
	def validate_links(self, data, **kwargs):
		if data.get('source') == 'payu':
			raise ValidationError('Dla PayU użyj endpointu /api/payments/payu/orders', 'source')

		invoice_id = data.get('invoice_id')
		job_id = data.get('job_id')
		kind = data.get('kind')

		if not invoice_id and not job_id:
			raise ValidationError('Podaj invoice_id lub job_id')

		if kind == 'invoice' and not invoice_id:
			raise ValidationError('Typ "invoice" wymaga invoice_id', 'invoice_id')

		if kind in ('deposit', 'prepayment') and not job_id:
			raise ValidationError('Typ zaliczki/przedpłaty wymaga job_id', 'job_id')


class PaymentCompleteSchema(Schema):
	transaction_id = fields.String(validate=validate.Length(max=100))


class PaymentRefundSchema(Schema):
	reason = fields.String(required=True, validate=validate.Length(min=3))


class PayUOrderCreateSchema(Schema):
	invoice_id = fields.Integer(required=True)
	buyer_email = fields.Email(allow_none=True)


payment_schema = PaymentSchema()
payments_schema = PaymentSchema(many=True)

payment_create_schema = PaymentCreateSchema()
payment_complete_schema = PaymentCompleteSchema()
payment_refund_schema = PaymentRefundSchema()

payu_order_create_schema = PayUOrderCreateSchema()

# Backwards-compatible alias (older code used this name).
payu_create_order_schema = payu_order_create_schema
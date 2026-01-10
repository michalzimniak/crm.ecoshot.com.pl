"""Payment model.

Supports:
- invoice-linked payments (kind=invoice, invoice_id required)
- job-level deposits/prepayments (kind=deposit/prepayment, job_id required)
- manual payments + provider-backed (PayU) payments.
"""

from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Payment(db.Model):
	__tablename__ = 'payments'

	id = db.Column(db.Integer, primary_key=True)

	job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True, index=True)
	invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True, index=True)

	kind = db.Column(
		db.Enum('invoice', 'deposit', 'prepayment', name='payment_kind_enum'),
		nullable=False,
		default='invoice',
		index=True,
	)
	source = db.Column(
		db.Enum('manual', 'payu', name='payment_source_enum'),
		nullable=False,
		default='manual',
		index=True,
	)

	currency = db.Column(db.String(3), nullable=False, default='PLN')
	amount = db.Column(db.Numeric(10, 2), nullable=False)

	payment_method = db.Column(
		db.Enum('transfer', 'cash', 'card', 'paypal', 'other', name='payment_method_enum'),
		nullable=False,
		default='transfer',
	)
	status = db.Column(
		db.Enum('pending', 'completed', 'failed', 'refunded', name='payment_status_enum'),
		nullable=False,
		default='pending',
		index=True,
	)

	payment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

	transaction_id = db.Column(db.String(100))
	reference = db.Column(db.String(200))
	notes = db.Column(db.Text)

	provider_order_id = db.Column(db.String(64), index=True)
	provider_ext_order_id = db.Column(db.String(64), unique=True, index=True)
	provider_status = db.Column(db.String(50))
	provider_payload = db.Column(db.JSON)
	redirect_url = db.Column(db.String(500))

	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

	invoice = db.relationship('Invoice', back_populates='payments')
	job = db.relationship('Job', back_populates='payments')

	def __repr__(self) -> str:
		return f'<Payment #{self.id}: {self.amount} {self.currency} ({self.status})>'

	@property
	def is_completed(self) -> bool:
		return self.status == 'completed'

	def complete(self) -> None:
		self.status = 'completed'
		self.payment_date = datetime.utcnow()

		if self.invoice:
			self.invoice.recalculate_paid_amount()
			self.invoice.update_payment_status()

	def refund(self) -> None:
		if self.status != 'completed':
			raise ValueError('Można zwrócić tylko zrealizowaną płatność')

		self.status = 'refunded'

		if self.invoice:
			self.invoice.recalculate_paid_amount()
			self.invoice.update_payment_status()
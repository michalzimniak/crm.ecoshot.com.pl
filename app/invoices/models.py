"""Invoice model.

Handles invoice generation, numbering, and payment tracking.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db


class Invoice(db.Model):
	"""Model faktury."""

	__tablename__ = 'invoices'

	id = db.Column(db.Integer, primary_key=True)

	job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
	invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

	invoice_type = db.Column(
		db.Enum('standard', 'deposit', 'final', 'correction', name='invoice_type_enum'),
		nullable=False,
		default='final',
		index=True,
	)

	original_invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True, index=True)
	correction_reason = db.Column(db.Text)

	status = db.Column(
		db.Enum('draft', 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled', name='invoice_status_enum'),
		nullable=False,
		default='draft',
		index=True,
	)

	issue_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
	due_date = db.Column(db.Date, nullable=False)
	payment_date = db.Column(db.Date)

	subtotal = db.Column(db.Numeric(10, 2), nullable=False)
	tax_rate = db.Column(db.Numeric(5, 2), default=23.00)
	tax_amount = db.Column(db.Numeric(10, 2), nullable=False)
	total_amount = db.Column(db.Numeric(10, 2), nullable=False)
	paid_amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)

	items = db.Column(db.JSON)

	buyer_name = db.Column(db.String(200), nullable=False)
	buyer_address = db.Column(db.String(500))
	buyer_nip = db.Column(db.String(20))
	buyer_email = db.Column(db.String(150))

	payment_method = db.Column(db.String(50))
	bank_account = db.Column(db.String(50))

	pdf_path = db.Column(db.String(500))

	notes = db.Column(db.Text)
	internal_notes = db.Column(db.Text)

	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

	job = db.relationship('Job', back_populates='invoices')
	original_invoice = db.relationship('Invoice', remote_side=[id], foreign_keys=[original_invoice_id], backref=db.backref('corrections', lazy='dynamic'))
	payments = db.relationship('Payment', back_populates='invoice', lazy='dynamic', cascade='all, delete-orphan')

	def __repr__(self) -> str:
		return f'<Invoice {self.invoice_number} ({self.status})>'

	@property
	def remaining_amount(self) -> float:
		return float(self.total_amount) - float(self.paid_amount)

	@property
	def is_paid(self) -> bool:
		return self.paid_amount >= self.total_amount

	@property
	def is_overdue(self) -> bool:
		if self.is_paid:
			return False
		return self.due_date < datetime.utcnow().date()

	def calculate_totals(self) -> None:
		if not self.items:
			return

		self.subtotal = sum(item.get('total', 0) for item in self.items)
		self.tax_amount = float(self.subtotal) * (float(self.tax_rate) / 100)
		self.total_amount = float(self.subtotal) + self.tax_amount

	def recalculate_paid_amount(self) -> None:
		from app.payments.models import Payment

		total = (
			db.session.query(func.coalesce(func.sum(Payment.amount), 0))
			.filter(Payment.invoice_id == self.id)
			.filter(Payment.status == 'completed')
			.scalar()
		)
		self.paid_amount = total or 0

	def update_payment_status(self) -> None:
		if self.paid_amount >= self.total_amount:
			self.status = 'paid'
			self.payment_date = datetime.utcnow().date()
		elif self.paid_amount > 0:
			self.status = 'partially_paid'
		elif self.is_overdue:
			self.status = 'overdue'

	def to_dict(self, include_relations: bool = False):
		data = {
			'id': self.id,
			'job_id': self.job_id,
			'invoice_number': self.invoice_number,
			'invoice_type': self.invoice_type,
			'original_invoice_id': self.original_invoice_id,
			'correction_reason': self.correction_reason,
			'status': self.status,
			'issue_date': self.issue_date.isoformat() if self.issue_date else None,
			'due_date': self.due_date.isoformat() if self.due_date else None,
			'payment_date': self.payment_date.isoformat() if self.payment_date else None,
			'subtotal': float(self.subtotal),
			'tax_rate': float(self.tax_rate),
			'tax_amount': float(self.tax_amount),
			'total_amount': float(self.total_amount),
			'paid_amount': float(self.paid_amount),
			'remaining_amount': self.remaining_amount,
			'is_paid': self.is_paid,
			'is_overdue': self.is_overdue,
			'items': self.items,
			'buyer_name': self.buyer_name,
			'buyer_address': self.buyer_address,
			'buyer_nip': self.buyer_nip,
			'buyer_email': self.buyer_email,
			'payment_method': self.payment_method,
			'bank_account': self.bank_account,
			'pdf_path': self.pdf_path,
			'notes': self.notes,
			'created_at': self.created_at.isoformat() if self.created_at else None,
			'updated_at': self.updated_at.isoformat() if self.updated_at else None,
		}

		if include_relations:
			data['job'] = self.job.to_dict() if self.job else None
			data['payments'] = [payment.to_dict() for payment in self.payments]

		return data
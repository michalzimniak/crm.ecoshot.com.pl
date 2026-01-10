"""Voucher DB model.

A voucher is a one-time code linked to a Promotion.
Validity is computed per voucher: expires_at = issued_at + promotion.duration_days.
"""

from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Voucher(db.Model):
    __tablename__ = "vouchers"

    id = db.Column(db.Integer, primary_key=True)

    promotion_id = db.Column(db.Integer, db.ForeignKey("promotions.id"), nullable=False, index=True)

    # Human-entered / QR scanned code. Unique forever.
    code = db.Column(db.String(80), nullable=False, unique=True, index=True)

    issued_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    # Marked when applied to a job.
    used_at = db.Column(db.DateTime, nullable=True, index=True)

    # Lottery / marketing sends (so we don't resend the same voucher).
    lottery_reserved_at = db.Column(db.DateTime, nullable=True, index=True)
    lottery_sent_at = db.Column(db.DateTime, nullable=True, index=True)
    lottery_customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)
    lottery_sent_email = db.Column(db.String(150), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    promotion = db.relationship("Promotion")
    job = db.relationship("Job", back_populates="voucher", uselist=False)
    lottery_customer = db.relationship("Customer", foreign_keys=[lottery_customer_id])

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return (not self.is_used) and (not self.is_expired)

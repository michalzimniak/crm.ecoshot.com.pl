"""Promotions DB model."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.extensions import db


class Promotion(db.Model):
    __tablename__ = "promotions"

    id = db.Column(db.Integer, primary_key=True)

    # Logical grouping/category. Example: "voucher", "bon", "seasonal".
    promo_type = db.Column(db.String(50), nullable=False, index=True)

    # Promotion value (amount in PLN). Stored as DECIMAL for currency-safe operations.
    value = db.Column(db.Numeric(10, 2), nullable=False)

    # Duration in days. Active until activated_at + duration_days.
    duration_days = db.Column(db.Integer, nullable=False)

    # Promotion becomes active only after vouchers are generated.
    activated_at = db.Column(db.DateTime, nullable=True)
    active_until = db.Column(db.DateTime, nullable=True, index=True)

    # Optional Canva project reference (used only as a source for background artwork).
    canva_project_url = db.Column(db.String(500), nullable=True)

    # Optional background images (relative to UPLOAD_FOLDER).
    voucher_bg_front_path = db.Column(db.String(500), nullable=True)
    voucher_bg_back_path = db.Column(db.String(500), nullable=True)

    # Voucher PDF layout settings (positions in CSS px from top-left of the page).
    # In print/PDF context, CSS px is a fixed unit (WeasyPrint uses CSS pixel sizing).
    voucher_text_x_px = db.Column(db.Numeric(10, 2), nullable=True)
    voucher_text_y_px = db.Column(db.Numeric(10, 2), nullable=True)
    voucher_qr_x_px = db.Column(db.Numeric(10, 2), nullable=True)
    voucher_qr_y_px = db.Column(db.Numeric(10, 2), nullable=True)

    # Text appearance.
    voucher_text_font_family = db.Column(db.String(200), nullable=True)
    voucher_text_font_size_pt = db.Column(db.Numeric(10, 2), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def is_active(self) -> bool:
        # A promotion is considered active only if it has at least one voucher
        # that is unused and not expired.
        from app.vouchers.models import Voucher

        now = datetime.utcnow()
        return (
            db.session.query(Voucher.id)
            .filter(Voucher.promotion_id == self.id)
            .filter(Voucher.used_at.is_(None))
            .filter(Voucher.expires_at >= now)
            .first()
            is not None
        )

    def activate(self, when: datetime | None = None) -> None:
        """Activate promotion (e.g. when vouchers are generated)."""
        when = when or datetime.utcnow()
        self.activated_at = when
        self.active_until = when + timedelta(days=int(self.duration_days or 0))

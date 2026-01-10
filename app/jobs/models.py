"""Job (zlecenie) model.

Represents photography jobs with status workflow and add-ons.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from app.extensions import db


class Job(db.Model):
    """Model zlecenia fotograficznego.

    Flow: draft -> quote_sent -> accepted -> in_progress -> completed
    """

    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)

    # Powiązania
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id'), nullable=False, index=True)

    # Status workflow
    status = db.Column(
        db.Enum(
            'draft',
            'quote_sent',
            'accepted',
            'rejected',
            'in_progress',
            'completed',
            'cancelled',
            name='job_status_enum',
        ),
        nullable=False,
        default='draft',
        index=True,
    )

    # Szczegóły zlecenia
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.Date)
    # New: precise reservation window (calendar / conflict checking)
    event_start = db.Column(db.DateTime, index=True)
    event_end = db.Column(db.DateTime, index=True)
    event_location = db.Column(db.String(300))

    # Finanse (bazowe z oferty)
    base_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    final_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)  # z dodatkami

    # Voucher/discount (one voucher per job)
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'), nullable=True, unique=True, index=True)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Notatki
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # widoczne tylko dla zespołu

    # Metadane
    quote_sent_at = db.Column(db.DateTime)
    accepted_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    customer = db.relationship('Customer', back_populates='jobs')
    offer = db.relationship('Offer', back_populates='jobs')
    addons = db.relationship('JobAddon', back_populates='job', lazy='dynamic', cascade='all, delete-orphan')
    contract = db.relationship('Contract', back_populates='job', uselist=False, cascade='all, delete-orphan')
    consents = db.relationship('Consent', back_populates='job', lazy='dynamic', cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', back_populates='job', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='job', lazy='dynamic', cascade='all, delete-orphan')
    galleries = db.relationship('Gallery', back_populates='job', lazy='dynamic', cascade='all, delete-orphan')

    voucher = db.relationship('Voucher', back_populates='job', uselist=False)

    def __repr__(self):
        return f'<Job #{self.id}: {self.title} ({self.status})>'

    def calculate_final_price(self):
        """Oblicza finalną cenę z dodatkami."""
        base = self.base_price if isinstance(self.base_price, Decimal) else Decimal(str(self.base_price or 0))
        addons_total = Decimal("0")

        for addon in self.addons:
            if not addon.is_selected:
                continue

            price = addon.price if isinstance(addon.price, Decimal) else Decimal(str(addon.price or 0))
            pricing_model = getattr(addon, "pricing_model", "fixed") or "fixed"

            if pricing_model == "per_unit":
                qty = int(getattr(addon, "quantity", 0) or 0)
                if qty <= 0:
                    continue
                addons_total += price * Decimal(qty)
            else:
                addons_total += price

        return base + addons_total

    def update_final_price(self):
        """Aktualizuje final_price na podstawie dodatków."""
        self.final_price = self.calculate_final_price()

    def to_dict(self, include_relations=False):
        """Konwersja do słownika."""
        data = {
            'id': self.id,
            'customer_id': self.customer_id,
            'offer_id': self.offer_id,
            'status': self.status,
            'title': self.title,
            'description': self.description,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_start': self.event_start.isoformat() if self.event_start else None,
            'event_end': self.event_end.isoformat() if self.event_end else None,
            'event_location': self.event_location,
            'base_price': float(self.base_price),
            'final_price': float(self.final_price),
            'notes': self.notes,
            'quote_sent_at': self.quote_sent_at.isoformat() if self.quote_sent_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_relations:
            data['customer'] = self.customer.to_dict() if self.customer else None
            data['addons'] = [addon.to_dict() for addon in self.addons]

        return data


class Offer(db.Model):
    """Szablon oferty (seed data)."""

    __tablename__ = 'offers'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)

    # Zawartość pakietu
    hours_included = db.Column(db.Integer)
    photos_count = db.Column(db.Integer)
    video_included = db.Column(db.Boolean, default=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    jobs = db.relationship('Job', back_populates='offer', lazy='dynamic')
    addons = db.relationship('OfferAddon', back_populates='offer', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Offer {self.name}>'

    def to_dict(self, include_addons=False):
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'base_price': float(self.base_price),
            'hours_included': self.hours_included,
            'photos_count': self.photos_count,
            'video_included': self.video_included,
            'is_active': self.is_active,
            'display_order': self.display_order,
        }

        if include_addons:
            data['addons'] = [addon.to_dict() for addon in self.addons if addon.is_available]

        return data


class OfferAddon(db.Model):
    """Dodatki dostępne dla danej oferty (seed data)."""

    __tablename__ = 'offer_addons'

    id = db.Column(db.Integer, primary_key=True)

    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id'), nullable=False, index=True)

    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    # Pricing semantics (added via migration 3fb0510f5764)
    pricing_model = db.Column(
        db.Enum('fixed', 'per_unit', name='offer_addon_pricing_model_enum'),
        nullable=False,
        default='fixed',
    )
    category = db.Column(db.String(50), nullable=False, default='addon')
    duration_months = db.Column(db.Integer)

    is_available = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0)

    # Relationships
    offer = db.relationship('Offer', back_populates='addons')

    def __repr__(self):
        return f'<OfferAddon {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'offer_id': self.offer_id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price),
            'pricing_model': self.pricing_model,
            'category': self.category,
            'duration_months': self.duration_months,
            'is_available': self.is_available,
            'display_order': self.display_order,
        }


class JobAddon(db.Model):
    """Dodatki wybrane dla konkretnego zlecenia."""

    __tablename__ = 'job_addons'

    id = db.Column(db.Integer, primary_key=True)

    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    offer_addon_id = db.Column(db.Integer, db.ForeignKey('offer_addons.id'), nullable=False)

    # Czy dodatek jest wybrany (klient może dodawać/usuwać)
    is_selected = db.Column(db.Boolean, default=False, nullable=False)

    # Pricing semantics (added via migration 3fb0510f5764)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    pricing_model = db.Column(
        db.Enum('fixed', 'per_unit', name='job_addon_pricing_model_enum'),
        nullable=False,
        default='fixed',
    )
    category = db.Column(db.String(50), nullable=False, default='addon')
    duration_months = db.Column(db.Integer)

    # Kopiujemy cenę z offer_addon (może się zmienić w przyszłości)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    name = db.Column(db.String(200), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job = db.relationship('Job', back_populates='addons')
    offer_addon = db.relationship('OfferAddon')

    def __repr__(self):
        return f'<JobAddon {self.name} for Job #{self.job_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'offer_addon_id': self.offer_addon_id,
            'name': self.name,
            'price': float(self.price),
            'is_selected': self.is_selected,
            'quantity': self.quantity,
            'pricing_model': self.pricing_model,
            'category': self.category,
            'duration_months': self.duration_months,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReminderLog(db.Model):
    """Idempotency log for scheduled emails/automation.

    Prevents sending the same reminder multiple times for the same entity.
    """

    __tablename__ = 'reminder_logs'

    id = db.Column(db.Integer, primary_key=True)

    kind = db.Column(db.String(50), nullable=False, index=True)
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # e.g. 'invoice'
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True, index=True)
    to_email = db.Column(db.String(150))
    meta = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('kind', 'entity_type', 'entity_id', name='uq_reminder_logs_kind_entity'),
    )

    job = db.relationship('Job')

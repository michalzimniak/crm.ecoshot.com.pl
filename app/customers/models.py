"""
Customer model.
Represents both individual persons and companies.
"""

from datetime import datetime
from app.extensions import db


class Customer(db.Model):
    """
    Model klienta - osoba fizyczna lub firma.
    """
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Typ klienta
    customer_type = db.Column(
        db.Enum('person', 'company', name='customer_type_enum'),
        nullable=False,
        default='person'
    )
    
    # Dane podstawowe (wspólne)
    # For customer_type='company' we allow these to be NULL.
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(150), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=False)
    
    # Adres
    street = db.Column(db.String(200))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(10))
    country = db.Column(db.String(100), default='Polska')
    
    # Dane firmowe (tylko dla customer_type='company')
    company_name = db.Column(db.String(200))
    nip = db.Column(db.String(20), unique=True, index=True)
    regon = db.Column(db.String(20))
    
    # Metadane
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    jobs = db.relationship('Job', back_populates='customer', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        if self.customer_type == 'company':
            return f'<Customer {self.company_name} (NIP: {self.nip})>'
        return f'<Customer {self.first_name} {self.last_name}>'
    
    @property
    def full_name(self):
        """Pełna nazwa klienta."""
        if self.customer_type == 'company':
            if self.company_name:
                return self.company_name
            parts = [p for p in [self.first_name, self.last_name] if p]
            return " ".join(parts) if parts else ""
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else ""
    
    @property
    def display_name(self):
        """Nazwa do wyświetlenia w UI."""
        if self.customer_type == 'company' and self.company_name:
            parts = [p for p in [self.first_name, self.last_name] if p]
            if parts:
                return f"{self.company_name} ({' '.join(parts)})"
            return self.company_name
        return self.full_name
    
    def to_dict(self):
        """Konwersja do słownika (podstawowa)."""
        return {
            'id': self.id,
            'customer_type': self.customer_type,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'display_name': self.display_name,
            'email': self.email,
            'phone': self.phone,
            'street': self.street,
            'city': self.city,
            'postal_code': self.postal_code,
            'country': self.country,
            'company_name': self.company_name,
            'nip': self.nip,
            'regon': self.regon,
            'notes': self.notes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

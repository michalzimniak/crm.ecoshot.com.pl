"""
User authentication model.
Handles user accounts with role-based access.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    """
    Model użytkownika systemu CRM.
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Dane logowania
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Dane osobowe
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    
    # Rola (admin, photographer, accountant, viewer)
    role = db.Column(
        db.Enum('admin', 'photographer', 'accountant', 'viewer', name='user_role_enum'),
        nullable=False,
        default='viewer'
    )
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)
    
    # Metadane
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
    
    def set_password(self, password):
        """Hashuje i zapisuje hasło."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Sprawdza czy hasło jest poprawne."""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Pełne imię i nazwisko."""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self, include_sensitive=False):
        """Konwersja do słownika."""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_sensitive:
            data['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        
        return data

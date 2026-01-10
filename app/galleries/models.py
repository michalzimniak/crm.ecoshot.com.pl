"""
Gallery model.
Handles photo galleries (proof, selection, final, archive).
"""

from datetime import datetime
from app.extensions import db


class Gallery(db.Model):
    """
    Model galerii - proof (podgląd), selection (wybór), final (gotowe), archive.
    """
    __tablename__ = 'galleries'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Powiązanie
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    
    # Typ galerii
    gallery_type = db.Column(
        db.Enum('proof', 'selection', 'final', 'archive', name='gallery_type_enum'),
        nullable=False,
        default='proof',
        index=True
    )
    
    # Status
    status = db.Column(
        db.Enum('draft', 'published', 'archived', name='gallery_status_enum'),
        nullable=False,
        default='draft',
        index=True
    )
    
    # Dane podstawowe
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Dostęp
    # Legacy: token + optional password
    access_token = db.Column(db.String(64), unique=True, index=True)  # Token dostępu dla klienta
    password_hash = db.Column(db.String(255))  # Opcjonalne hasło

    # New public access (GALLERYPROMPT.md): hash + PIN
    public_hash = db.Column(db.String(64), unique=True, index=True)
    access_pin_hash = db.Column(db.String(255))

    expires_at = db.Column(db.DateTime)        # Data wygaśnięcia dostępu

    # Settings: expiry policy (optional)
    expiration_days = db.Column(db.Integer)
    
    # Ustawienia
    allow_download = db.Column(db.Boolean, default=False)  # Czy klient może pobierać
    allow_selection = db.Column(db.Boolean, default=True)  # Czy klient może wybierać
    max_selections = db.Column(db.Integer)                 # Limit wyborów
    
    # Watermark
    watermark_enabled = db.Column(db.Boolean, default=True)
    
    # ZIP
    zip_path = db.Column(db.String(500))  # Ścieżka do wygenerowanego ZIP
    zip_generated_at = db.Column(db.DateTime)
    
    # Statystyki
    view_count = db.Column(db.Integer, default=0)
    last_viewed_at = db.Column(db.DateTime)
    
    # Daty
    published_at = db.Column(db.DateTime)
    
    # Metadane
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    job = db.relationship('Job', back_populates='galleries')
    photos = db.relationship('Photo', back_populates='gallery', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Gallery #{self.id}: {self.title} ({self.gallery_type})>'
    
    @property
    def is_published(self):
        """Sprawdza czy galeria jest opublikowana."""
        return self.status == 'published'
    
    @property
    def is_expired(self):
        """Sprawdza czy dostęp do galerii wygasł."""
        if not self.expires_at:
            return False
        return self.expires_at < datetime.utcnow()
    
    @property
    def photo_count(self):
        """Liczba zdjęć w galerii."""
        from app.photos.models import Photo

        return self.photos.filter(Photo.status != 'deleted').count()
    
    @property
    def selected_count(self):
        """Liczba wybranych zdjęć."""
        from app.photos.models import Photo

        return self.photos.filter(Photo.status != 'deleted').filter_by(is_selected=True).count()
    
    def increment_view_count(self):
        """Inkrementuje licznik wyświetleń."""
        self.view_count += 1
        self.last_viewed_at = datetime.utcnow()
    
    def to_dict(self, include_relations=False, include_token=False):
        """Konwersja do słownika."""
        data = {
            'id': self.id,
            'job_id': self.job_id,
            'gallery_type': self.gallery_type,
            'status': self.status,
            'title': self.title,
            'description': self.description,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'expiration_days': self.expiration_days,
            'allow_download': self.allow_download,
            'allow_selection': self.allow_selection,
            'max_selections': self.max_selections,
            'watermark_enabled': self.watermark_enabled,
            'has_password': bool(self.password_hash),
            'zip_path': self.zip_path,
            'zip_generated_at': self.zip_generated_at.isoformat() if self.zip_generated_at else None,
            'view_count': self.view_count,
            'last_viewed_at': self.last_viewed_at.isoformat() if self.last_viewed_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'is_published': self.is_published,
            'is_expired': self.is_expired,
            'photo_count': self.photo_count,
            'selected_count': self.selected_count,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_token:
            data['access_token'] = self.access_token
            data['public_hash'] = self.public_hash
        
        if include_relations:
            data['job'] = self.job.to_dict() if self.job else None
            data['photos'] = [photo.to_dict() for photo in self.photos]
        
        return data


class GalleryPinAttempt(db.Model):
    __tablename__ = 'gallery_pin_attempts'

    id = db.Column(db.Integer, primary_key=True)
    gallery_id = db.Column(db.Integer, db.ForeignKey('galleries.id', ondelete='CASCADE'), nullable=False, index=True)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    is_success = db.Column(db.Boolean, default=False, nullable=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    gallery = db.relationship('Gallery')


class GalleryDownloadLog(db.Model):
    __tablename__ = 'gallery_download_logs'

    id = db.Column(db.Integer, primary_key=True)
    gallery_id = db.Column(db.Integer, db.ForeignKey('galleries.id', ondelete='CASCADE'), nullable=False, index=True)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    bytes_sent = db.Column(db.BigInteger)

    gallery = db.relationship('Gallery')

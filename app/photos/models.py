"""
Photo model.
Handles individual photos with metadata and selection.
"""

from datetime import datetime
from app.extensions import db


class Photo(db.Model):
    """
    Model zdjęcia w galerii.
    """
    __tablename__ = 'photos'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Powiązanie
    gallery_id = db.Column(db.Integer, db.ForeignKey('galleries.id'), nullable=False, index=True)
    
    # Pliki
    filename = db.Column(db.String(255), nullable=False)
    original_path = db.Column(db.String(500), nullable=False)  # Oryginalny plik
    thumbnail_path = db.Column(db.String(500))                 # Miniaturka
    watermarked_path = db.Column(db.String(500))               # Z watermarkiem
    
    # Metadane
    file_size = db.Column(db.Integer)           # Rozmiar w bajtach
    width = db.Column(db.Integer)               # Szerokość px
    height = db.Column(db.Integer)              # Wysokość px
    mime_type = db.Column(db.String(50))        # image/jpeg, etc.
    
    # EXIF (opcjonalne)
    camera_make = db.Column(db.String(100))
    camera_model = db.Column(db.String(100))
    lens = db.Column(db.String(100))
    focal_length = db.Column(db.String(20))
    aperture = db.Column(db.String(20))
    shutter_speed = db.Column(db.String(20))
    iso = db.Column(db.String(20))
    taken_at = db.Column(db.DateTime)
    
    # Kolejność i selekcja
    display_order = db.Column(db.Integer, default=0)
    is_selected = db.Column(db.Boolean, default=False)  # Wybrane przez klienta
    is_favorite = db.Column(db.Boolean, default=False)  # Ulubione fotografa
    
    # Status
    status = db.Column(
        db.Enum('processing', 'ready', 'hidden', 'deleted', name='photo_status_enum'),
        nullable=False,
        default='processing',
        index=True
    )
    
    # Notatki
    caption = db.Column(db.String(500))  # Podpis
    notes = db.Column(db.Text)
    
    # Metadane
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    gallery = db.relationship('Gallery', back_populates='photos')
    
    def __repr__(self):
        return f'<Photo #{self.id}: {self.filename}>'
    
    @property
    def display_path(self):
        """Zwraca ścieżkę do wyświetlenia (z watermarkiem jeśli jest)."""
        if self.watermarked_path and self.gallery and self.gallery.watermark_enabled:
            return self.watermarked_path
        return self.original_path
    
    @property
    def resolution(self):
        """Rozdzielczość jako string."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None
    
    @property
    def file_size_mb(self):
        """Rozmiar pliku w MB."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    def toggle_selection(self):
        """Przełącza status wyboru."""
        self.is_selected = not self.is_selected
    
    def to_dict(self, include_relations=False, include_paths=True):
        """Konwersja do słownika."""
        data = {
            'id': self.id,
            'gallery_id': self.gallery_id,
            'filename': self.filename,
            'file_size': self.file_size,
            'file_size_mb': self.file_size_mb,
            'width': self.width,
            'height': self.height,
            'resolution': self.resolution,
            'mime_type': self.mime_type,
            'display_order': self.display_order,
            'is_selected': self.is_selected,
            'is_favorite': self.is_favorite,
            'status': self.status,
            'caption': self.caption,
            'camera_make': self.camera_make,
            'camera_model': self.camera_model,
            'lens': self.lens,
            'focal_length': self.focal_length,
            'aperture': self.aperture,
            'shutter_speed': self.shutter_speed,
            'iso': self.iso,
            'taken_at': self.taken_at.isoformat() if self.taken_at else None,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_paths:
            data['original_path'] = self.original_path
            data['thumbnail_path'] = self.thumbnail_path
            data['watermarked_path'] = self.watermarked_path
            data['display_path'] = self.display_path
        
        if include_relations:
            data['gallery'] = self.gallery.to_dict() if self.gallery else None
        
        return data

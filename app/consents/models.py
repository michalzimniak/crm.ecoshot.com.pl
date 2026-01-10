"""Consent model.

Handles image publication consents with revoke capability.
"""

from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Consent(db.Model):
    """Model zgody - blokuje publikację galerii jeśli nie wyrażona."""

    __tablename__ = "consents"

    id = db.Column(db.Integer, primary_key=True)

    # Powiązanie
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)

    # Typ zgody
    consent_type = db.Column(
        db.Enum(
            "image_publication",
            "data_processing",
            "marketing",
            name="consent_type_enum",
        ),
        nullable=False,
        default="image_publication",
        index=True,
    )

    # Status
    is_granted = db.Column(db.Boolean, default=False, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False, nullable=False)

    # Szczegóły
    consent_text = db.Column(db.Text, nullable=False)  # Treść zgody
    scope = db.Column(db.String(200))  # Zakres zgody (np. "social media", "website")

    # Podpis
    signature_data = db.Column(db.Text)  # Base64 podpisu
    signature_ip = db.Column(db.String(50))

    # Pliki (PDF + skan podpisanej zgody)
    pdf_path = db.Column(db.String(500), nullable=True)

    signed_scan_path = db.Column(db.String(500), nullable=True)
    signed_scan_original_filename = db.Column(db.String(255), nullable=True)
    signed_scan_mime_type = db.Column(db.String(100), nullable=True)
    signed_scan_size = db.Column(db.Integer, nullable=True)
    signed_scan_uploaded_at = db.Column(db.DateTime, nullable=True)

    # Daty
    granted_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime)
    revoke_reason = db.Column(db.Text)

    # Metadane
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    job = db.relationship("Job", back_populates="consents")

    def __repr__(self) -> str:
        status = (
            "granted"
            if self.is_granted and not self.is_revoked
            else "revoked"
            if self.is_revoked
            else "not_granted"
        )
        return f"<Consent #{self.id} ({self.consent_type}): {status}>"

    def grant(self, signature_data: str | None = None, ip_address: str | None = None):
        """Udziela zgody."""
        self.is_granted = True
        self.is_revoked = False
        self.granted_at = datetime.utcnow()
        self.signature_data = signature_data
        self.signature_ip = ip_address

    def revoke(self, reason: str | None = None):
        """Cofa zgodę."""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoke_reason = reason

    @property
    def is_active(self) -> bool:
        """Sprawdza czy zgoda jest aktywna."""
        return self.is_granted and not self.is_revoked

    @property
    def has_signature(self) -> bool:
        return bool(self.signature_data)

    @property
    def has_signed_scan(self) -> bool:
        return bool(self.signed_scan_path)

    def to_dict(self, include_relations: bool = False) -> dict:
        """Konwersja do słownika."""
        data = {
            "id": self.id,
            "job_id": self.job_id,
            "consent_type": self.consent_type,
            "is_granted": self.is_granted,
            "is_revoked": self.is_revoked,
            "is_active": self.is_active,
            "consent_text": self.consent_text,
            "scope": self.scope,
            "has_signature": bool(self.signature_data),
            "has_signed_scan": self.has_signed_scan,
            "signature_ip": self.signature_ip,
            "pdf_path": self.pdf_path,
            "signed_scan_path": self.signed_scan_path,
            "signed_scan_original_filename": self.signed_scan_original_filename,
            "signed_scan_mime_type": self.signed_scan_mime_type,
            "signed_scan_size": self.signed_scan_size,
            "signed_scan_uploaded_at": self.signed_scan_uploaded_at.isoformat()
            if self.signed_scan_uploaded_at
            else None,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoke_reason": self.revoke_reason,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_relations:
            data["job"] = self.job.to_dict() if self.job else None

        return data

"""Contract model.

Handles PDF generation, digital signatures, signed scan archival, and payment tracking.
"""

from datetime import datetime
import hashlib

from app.extensions import db


class Contract(db.Model):
    """Model umowy - blokuje dalszy flow jeśli nie podpisana."""

    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)

    # Powiązanie
    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Status
    status = db.Column(
        db.Enum(
            "draft",
            "sent",
            "signed",
            "rejected",
            "cancelled",
            name="contract_status_enum",
        ),
        nullable=False,
        default="draft",
        index=True,
    )

    # Numer umowy
    contract_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Pliki
    pdf_path = db.Column(db.String(500))
    pdf_hash = db.Column(db.String(64))

    # Skan/zdjęcie podpisanej umowy (archiwizacja)
    signed_scan_path = db.Column(db.String(500))
    signed_scan_original_filename = db.Column(db.String(255))
    signed_scan_mime_type = db.Column(db.String(100))
    signed_scan_size = db.Column(db.Integer)
    signed_scan_uploaded_at = db.Column(db.DateTime)

    # Podpis
    signature_data = db.Column(db.Text)
    signature_ip = db.Column(db.String(50))
    signed_at = db.Column(db.DateTime)

    # Daty
    sent_at = db.Column(db.DateTime)
    valid_until = db.Column(db.Date)

    # Warunki
    terms_content = db.Column(db.Text)

    # Zaliczka
    deposit_percent = db.Column(db.Numeric(5, 2), nullable=False, default=10)
    deposit_amount = db.Column(db.Numeric(10, 2))
    deposit_status = db.Column(
        db.Enum("unpaid", "paid", "waived", name="deposit_status_enum"),
        nullable=False,
        default="unpaid",
        index=True,
    )
    deposit_paid_amount = db.Column(db.Numeric(10, 2))
    deposit_paid_at = db.Column(db.DateTime)
    deposit_notes = db.Column(db.Text)

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
    job = db.relationship("Job", back_populates="contract")

    def __repr__(self):
        return f"<Contract {self.contract_number} ({self.status})>"

    def generate_hash(self, file_path: str) -> str:
        """Generuje SHA-256 hash pliku PDF."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def verify_hash(self, file_path: str) -> bool:
        """Weryfikuje czy hash się zgadza."""
        return self.generate_hash(file_path) == self.pdf_hash

    @property
    def is_signed(self) -> bool:
        return self.status == "signed"

    @property
    def has_signed_scan(self) -> bool:
        return bool(self.signed_scan_path)

    @property
    def has_signature(self) -> bool:
        return bool(self.signature_data)

    @property
    def is_valid(self) -> bool:
        if not self.is_signed:
            return False
        if self.valid_until and self.valid_until < datetime.utcnow().date():
            return False
        return True

    def to_dict(self, include_relations: bool = False) -> dict:
        data = {
            "id": self.id,
            "job_id": self.job_id,
            "status": self.status,
            "contract_number": self.contract_number,
            "pdf_path": self.pdf_path,
            "pdf_hash": self.pdf_hash,
            "signed_scan_path": self.signed_scan_path,
            "signed_scan_original_filename": self.signed_scan_original_filename,
            "signed_scan_mime_type": self.signed_scan_mime_type,
            "signed_scan_size": self.signed_scan_size,
            "signed_scan_uploaded_at": self.signed_scan_uploaded_at.isoformat()
            if self.signed_scan_uploaded_at
            else None,
            "has_signed_scan": self.has_signed_scan,
            "has_signature": bool(self.signature_data),
            "signature_ip": self.signature_ip,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "is_signed": self.is_signed,
            "is_valid": self.is_valid,
            "deposit_percent": float(self.deposit_percent)
            if self.deposit_percent is not None
            else None,
            "deposit_amount": float(self.deposit_amount)
            if self.deposit_amount is not None
            else None,
            "deposit_status": self.deposit_status,
            "deposit_paid_amount": float(self.deposit_paid_amount)
            if self.deposit_paid_amount is not None
            else None,
            "deposit_paid_at": self.deposit_paid_at.isoformat() if self.deposit_paid_at else None,
            "deposit_notes": self.deposit_notes,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_relations:
            data["job"] = self.job.to_dict() if self.job else None

        return data
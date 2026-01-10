"""
Business flow enforcement.
Critical business rules that MUST be enforced before certain operations.

Flow: Klient → Zlecenie → Umowa → Faktura → Galeria
"""

from flask import jsonify
from werkzeug.exceptions import Forbidden, BadRequest


class EnforcementError(Exception):
    """Custom exception for business rule violations."""
    def __init__(self, message, code=403):
        self.message = message
        self.code = code
        super().__init__(self.message)


def can_generate_invoice(job_id):
    """
    Sprawdza czy można wygenerować fakturę dla zlecenia.
    
    Warunki:
    - Zlecenie musi istnieć i być aktywne
    - Umowa musi być podpisana (status = 'signed')
    - (Zgoda na wizerunek nie jest wymagana do wystawienia faktury)
    
    Args:
        job_id: ID zlecenia
        
    Returns:
        bool: True jeśli można wygenerować fakturę
        
    Raises:
        EnforcementError: jeśli warunki nie są spełnione
    """
    from app.jobs.models import Job
    from app.contracts.models import Contract
    from app.extensions import db
    
    # Sprawdź zlecenie
    job = db.session.get(Job, job_id)
    if not job:
        raise EnforcementError(f"Zlecenie #{job_id} nie istnieje", 404)
    
    if job.status in ['cancelled', 'rejected']:
        raise EnforcementError(
            f"Nie można wygenerować faktury dla zlecenia o statusie: {job.status}"
        )
    
    # Sprawdź umowę
    contract = Contract.query.filter_by(job_id=job_id).first()
    if not contract:
        raise EnforcementError(
            f"Brak umowy dla zlecenia #{job_id}. Najpierw wygeneruj i podpisz umowę."
        )
    
    if contract.status != 'signed':
        raise EnforcementError(
            f"Umowa musi być podpisana. Aktualny status: {contract.status}"
        )
    
    return True


def can_publish_gallery(job_id):
    """
    Sprawdza czy można opublikować galerię dla zlecenia.
    
    Warunki:
    - Wszystkie warunki z can_generate_invoice() muszą być spełnione
    - Faktura musi istnieć
    - Zlecenie musi być w statusie 'in_progress' lub 'completed'
    
    Uwaga:
    - Zgoda na publikację wizerunku nie blokuje publikacji galerii do klienta.
    
    Args:
        job_id: ID zlecenia
        
    Returns:
        bool: True jeśli można opublikować galerię
        
    Raises:
        EnforcementError: jeśli warunki nie są spełnione
    """
    from app.jobs.models import Job
    from app.invoices.models import Invoice
    from app.extensions import db
    
    # Najpierw sprawdź podstawowe warunki
    can_generate_invoice(job_id)
    
    # Sprawdź czy faktura istnieje
    invoice = Invoice.query.filter_by(job_id=job_id).first()
    if not invoice:
        raise EnforcementError(
            f"Brak faktury dla zlecenia #{job_id}. Najpierw wygeneruj fakturę."
        )
    
    # Sprawdź status zlecenia
    job = db.session.get(Job, job_id)
    if job.status not in ['in_progress', 'completed']:
        raise EnforcementError(
            f"Galeria może być publikowana tylko dla zleceń w trakcie lub ukończonych. Aktualny status: {job.status}"
        )
    
    return True


def can_download_final_gallery(job_id):
    """
    Sprawdza czy klient może pobrać finalną galerię.
    
    Warunki:
    - Wszystkie warunki z can_publish_gallery() muszą być spełnione
    - Faktura musi być opłacona (paid_amount >= total_amount)
    - Galeria musi być w statusie 'final'
    
    Args:
        job_id: ID zlecenia
        
    Returns:
        bool: True jeśli można pobrać finalną galerię
        
    Raises:
        EnforcementError: jeśli warunki nie są spełnione
    """
    from app.invoices.models import Invoice
    from app.galleries.models import Gallery
    from app.extensions import db
    
    # Sprawdź warunki publikacji
    can_publish_gallery(job_id)
    
    # Sprawdź płatność
    invoice = Invoice.query.filter_by(job_id=job_id).first()
    if invoice.paid_amount < invoice.total_amount:
        remaining = invoice.total_amount - invoice.paid_amount
        raise EnforcementError(
            f"Faktura nie jest w pełni opłacona. Pozostało do zapłaty: {remaining:.2f} PLN"
        )
    
    # Sprawdź czy galeria finalna istnieje
    gallery = Gallery.query.filter_by(job_id=job_id, gallery_type='final').first()
    if not gallery:
        raise EnforcementError(
            f"Brak finalnej galerii dla zlecenia #{job_id}"
        )
    
    if gallery.status != 'published':
        raise EnforcementError(
            f"Finalna galeria nie jest jeszcze opublikowana. Status: {gallery.status}"
        )
    
    return True


def can_create_contract(job_id):
    """
    Sprawdza czy można utworzyć umowę dla zlecenia.
    
    Warunki:
    - Zlecenie musi istnieć
    - Zlecenie musi być w statusie 'accepted' lub wyżej
    - Klient musi istnieć i mieć wypełnione dane
    
    Args:
        job_id: ID zlecenia
        
    Returns:
        bool: True jeśli można utworzyć umowę
        
    Raises:
        EnforcementError: jeśli warunki nie są spełnione
    """
    from app.jobs.models import Job
    from app.customers.models import Customer
    from app.extensions import db
    
    job = db.session.get(Job, job_id)
    if not job:
        raise EnforcementError(f"Zlecenie #{job_id} nie istnieje", 404)
    
    if job.status not in ['accepted', 'in_progress', 'completed']:
        raise EnforcementError(
            f"Umowa może być utworzona tylko dla zaakceptowanego zlecenia. Aktualny status: {job.status}"
        )
    
    customer = db.session.get(Customer, job.customer_id)
    if not customer:
        raise EnforcementError(
            f"Brak klienta dla zlecenia #{job_id}"
        )
    
    # Sprawdź czy klient ma wypełnione niezbędne dane
    if not customer.email or not customer.phone:
        raise EnforcementError(
            "Klient musi mieć wypełniony email i telefon"
        )
    
    if customer.customer_type == 'company' and not customer.nip:
        raise EnforcementError(
            "Firma musi mieć wypełniony NIP"
        )
    
    return True


def enforce_job_workflow(job, new_status):
    """
    Egzekwuje prawidłowy przepływ statusów zlecenia.
    
    Dozwolone przejścia:
    - draft -> quote_sent
    - quote_sent -> accepted / rejected
    - accepted -> in_progress
    - in_progress -> completed
    - * -> cancelled (zawsze możliwe)
    
    Args:
        job: obiekt Job
        new_status: nowy status
        
    Returns:
        bool: True jeśli przejście jest dozwolone
        
    Raises:
        EnforcementError: jeśli przejście jest niedozwolone
    """
    current_status = job.status
    
    # Anulowanie zawsze możliwe
    if new_status == 'cancelled':
        return True
    
    # Mapa dozwolonych przejść
    allowed_transitions = {
        'draft': ['quote_sent', 'cancelled'],
        'quote_sent': ['accepted', 'rejected', 'cancelled'],
        'accepted': ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'cancelled'],
        'completed': [],  # Stan końcowy
        'rejected': [],   # Stan końcowy
        'cancelled': []   # Stan końcowy
    }
    
    if new_status not in allowed_transitions.get(current_status, []):
        raise EnforcementError(
            f"Nieprawidłowe przejście statusu: {current_status} -> {new_status}"
        )
    
    return True

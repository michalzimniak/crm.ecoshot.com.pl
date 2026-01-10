"""
Invoices business logic.
Handles invoice generation, numbering, and payment tracking with enforcement.
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from sqlalchemy import func
from werkzeug.exceptions import BadRequest, NotFound
from flask import current_app
from app.extensions import db
from app.invoices.models import Invoice
from app.jobs.services import get_job_by_id
from app.core.enforcement import can_generate_invoice
from app.settings.services import get_setting


def _to_money(value) -> float:
    """Convert numeric/Decimal to 2dp float for JSON storage."""
    return float(Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _normalize_items(items):
    """Ensure invoice items are JSON-serializable (floats) and consistent."""
    normalized = []
    for item in items or []:
        quantity = _to_money(item.get('quantity', 0))
        unit_price = _to_money(item.get('unit_price', 0))
        total = _to_money(item.get('total', quantity * unit_price))
        normalized.append({
            'name': (item.get('name') or '').strip(),
            'quantity': quantity,
            'unit_price': unit_price,
            'total': total,
        })
    return normalized


def _default_items_from_job(job):
    """Generate default invoice items based on job base price and selected add-ons."""
    items = []

    base_price = _to_money(getattr(job, 'base_price', 0))
    offer_name = getattr(getattr(job, 'offer', None), 'name', None)
    base_name = f"Pakiet: {offer_name}" if offer_name else "Pakiet fotograficzny"
    if base_price > 0:
        items.append({
            'name': base_name,
            'quantity': 1,
            'unit_price': base_price,
            'total': base_price,
        })

    try:
        selected_addons = job.addons.filter_by(is_selected=True).all()
    except Exception:
        selected_addons = [a for a in getattr(job, 'addons', []) if getattr(a, 'is_selected', False)]

    for addon in selected_addons:
        price = _to_money(getattr(addon, 'price', 0))
        if price <= 0:
            continue
        items.append({
            'name': f"Dodatek: {getattr(addon, 'name', 'Dodatek')}",
            'quantity': 1,
            'unit_price': price,
            'total': price,
        })

    # Fallback: if base + addons are missing, invoice final price as one item
    if not items:
        final_price = _to_money(getattr(job, 'final_price', 0))
        if final_price > 0:
            items.append({
                'name': 'Usługa fotograficzna',
                'quantity': 1,
                'unit_price': final_price,
                'total': final_price,
            })

    # Voucher discount (negative line item)
    try:
        discount = _to_money(getattr(job, 'discount_amount', 0))
    except Exception:
        discount = 0.0

    if discount and discount > 0:
        subtotal = sum(float(it.get('total') or 0) for it in items)
        applied = min(float(discount), float(subtotal))
        if applied > 0:
            code = None
            try:
                code = getattr(getattr(job, 'voucher', None), 'code', None)
            except Exception:
                code = None
            label = f"Rabat (voucher {code})" if code else "Rabat (voucher)"
            items.append({
                'name': label,
                'quantity': 1,
                'unit_price': -applied,
                'total': -applied,
            })

    return items


def _invoice_prefix_for_type(invoice_type: str | None) -> str:
    t = (invoice_type or "final").strip().lower()
    if t == "deposit":
        return get_setting('INVOICE_DEPOSIT_PREFIX', 'FZV')
    if t == "correction":
        return get_setting('INVOICE_CORRECTION_PREFIX', 'FKV')
    # standard/final
    return get_setting('INVOICE_PREFIX', 'FV')


def generate_invoice_number(invoice_type: str | None = None):
    """Generuje numer faktury: PREFIX/YYYY/NNN (osobna sekwencja per prefix)."""
    prefix = _invoice_prefix_for_type(invoice_type)
    year_format = get_setting('INVOICE_YEAR_FORMAT', '%Y')
    try:
        year_part = datetime.utcnow().strftime(str(year_format or '%Y'))
    except Exception:
        year_part = str(datetime.utcnow().year)
    
    # Policz faktury w tym roku dla danego prefixu
    count = Invoice.query.filter(Invoice.invoice_number.like(f'{prefix}/{year_part}/%')).count()
    
    next_number = count + 1
    return f'{prefix}/{year_part}/{next_number:03d}'


def _get_contract_for_job(job_id: int):
    from app.contracts.models import Contract

    return Contract.query.filter_by(job_id=job_id).first()


def get_latest_job_invoice(job_id: int, invoice_type: str | None = None):
    q = Invoice.query.filter_by(job_id=job_id)
    if invoice_type:
        q = q.filter_by(invoice_type=invoice_type)
    q = q.order_by(Invoice.created_at.desc())
    return q.first()


def get_payable_invoice_for_job(job_id: int):
    """Return the invoice that should gate gallery payment rules.

    Prefer final invoices; fall back to legacy/standard ones.
    """
    return (
        Invoice.query.filter_by(job_id=job_id)
        .filter(Invoice.invoice_type.in_(["final", "standard"]))
        .order_by(Invoice.created_at.desc())
        .first()
    )


def create_deposit_invoice_for_job(job_id: int, *, issue_date=None, due_date=None):
    """Create (or return existing) deposit invoice for a job based on contract deposit settings."""
    can_generate_invoice(job_id)

    existing = (
        Invoice.query.filter_by(job_id=job_id, invoice_type="deposit")
        .filter(Invoice.status != "cancelled")
        .order_by(Invoice.created_at.desc())
        .first()
    )
    if existing:
        return existing

    job = get_job_by_id(job_id)
    customer = job.customer
    contract = _get_contract_for_job(job_id)
    if not contract or getattr(contract, "status", None) != "signed":
        raise BadRequest("Umowa musi być podpisana, aby wystawić fakturę zaliczkową")

    if issue_date is None:
        issue_date = datetime.utcnow().date()

    if due_date is None:
        due_date = issue_date + timedelta(days=14)

    # Deposit amount comes from contract (precomputed from job value).
    try:
        deposit_amount = Decimal(str(getattr(contract, "deposit_amount", None) or "0"))
    except Exception:
        deposit_amount = Decimal("0")

    if deposit_amount <= 0:
        raise BadRequest("Brak kwoty zaliczki w umowie")

    items = _normalize_items(
        [
            {
                "name": f"Zaliczka do umowy {getattr(contract, 'contract_number', '')}".strip(),
                "quantity": 1,
                "unit_price": _to_money(deposit_amount),
                "total": _to_money(deposit_amount),
            }
        ]
    )

    vat_exempt = str(get_setting("INVOICE_VAT_EXEMPT", "0") or "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    default_vat_rate = "0" if vat_exempt else str(get_setting("INVOICE_VAT_RATE", "23") or "23")
    try:
        tax_rate = Decimal(str(default_vat_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        tax_rate = Decimal("23.00")
    if vat_exempt:
        tax_rate = Decimal("0.00")

    invoice = Invoice(
        job_id=job_id,
        invoice_type="deposit",
        invoice_number=generate_invoice_number("deposit"),
        issue_date=issue_date,
        due_date=due_date,
        items=items,
        tax_rate=tax_rate,
        buyer_name=customer.full_name,
        buyer_address=(
            f"{customer.street}, {customer.postal_code} {customer.city}" if customer.street else None
        ),
        buyer_nip=customer.nip,
        buyer_email=customer.email,
        payment_method="transfer",
        bank_account=get_setting("COMPANY_ACCOUNT"),
        status="draft",
    )

    invoice.calculate_totals()
    db.session.add(invoice)
    db.session.commit()

    generate_invoice_pdf(invoice)
    return invoice


def _get_paid_deposit_amount_for_job(job_id: int) -> Decimal:
    """Best-effort deposit paid amount used for final invoice deduction."""
    contract = _get_contract_for_job(job_id)
    contract_paid = Decimal("0")
    if contract and getattr(contract, "deposit_status", None) == "paid":
        try:
            contract_paid = Decimal(str(getattr(contract, "deposit_paid_amount", None) or "0"))
        except Exception:
            contract_paid = Decimal("0")

    # Also consider invoice-linked payments for deposit invoices.
    from app.payments.models import Payment

    invoice_paid = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Invoice.job_id == job_id)
        .filter(Invoice.invoice_type == "deposit")
        .filter(Payment.status == "completed")
        .scalar()
    )
    try:
        invoice_paid = Decimal(str(invoice_paid or "0"))
    except Exception:
        invoice_paid = Decimal("0")

    return max(contract_paid, invoice_paid)


def create_final_invoice_for_job(job_id: int, *, issue_date=None, due_date=None):
    """Create (or return existing) final VAT invoice for a job, deducting paid deposits."""
    can_generate_invoice(job_id)

    existing = (
        Invoice.query.filter_by(job_id=job_id, invoice_type="final")
        .filter(Invoice.status != "cancelled")
        .order_by(Invoice.created_at.desc())
        .first()
    )
    if existing:
        return existing

    job = get_job_by_id(job_id)
    customer = job.customer
    contract = _get_contract_for_job(job_id)

    if issue_date is None:
        issue_date = datetime.utcnow().date()

    if due_date is None:
        due_date = issue_date + timedelta(days=14)

    items = _default_items_from_job(job)

    paid_deposit = _get_paid_deposit_amount_for_job(job_id)
    if paid_deposit > 0:
        label = "Rozliczenie zaliczki"
        if contract and getattr(contract, "contract_number", None):
            label = f"Rozliczenie zaliczki (umowa {contract.contract_number})"
        items.append(
            {
                "name": label,
                "quantity": 1,
                "unit_price": _to_money(-paid_deposit),
                "total": _to_money(-paid_deposit),
            }
        )

    items = _normalize_items(items)

    vat_exempt = str(get_setting("INVOICE_VAT_EXEMPT", "0") or "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    default_vat_rate = "0" if vat_exempt else str(get_setting("INVOICE_VAT_RATE", "23") or "23")
    try:
        tax_rate = Decimal(str(default_vat_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        tax_rate = Decimal("23.00")
    if vat_exempt:
        tax_rate = Decimal("0.00")

    invoice = Invoice(
        job_id=job_id,
        invoice_type="final",
        invoice_number=generate_invoice_number("final"),
        issue_date=issue_date,
        due_date=due_date,
        items=items,
        tax_rate=tax_rate,
        buyer_name=customer.full_name,
        buyer_address=(
            f"{customer.street}, {customer.postal_code} {customer.city}" if customer.street else None
        ),
        buyer_nip=customer.nip,
        buyer_email=customer.email,
        payment_method="transfer",
        bank_account=get_setting("COMPANY_ACCOUNT"),
        status="draft",
    )
    invoice.calculate_totals()

    if float(getattr(invoice, "total_amount", 0) or 0) <= 0:
        raise BadRequest("Faktura końcowa ma kwotę <= 0 (zaliczka pokrywa całość)")

    db.session.add(invoice)
    db.session.commit()

    generate_invoice_pdf(invoice)
    return invoice


def create_correction_invoice(original_invoice_id: int, data: dict):
    """Create a correction invoice linked to an existing invoice. Items represent deltas (+/-)."""
    original = get_invoice_by_id(original_invoice_id)

    if original.status == "cancelled":
        raise BadRequest("Nie można korygować anulowanej faktury")

    items = data.get("items")
    if not items:
        raise BadRequest("Korekta wymaga pozycji (różnic: + / -)")

    reason = (data.get("correction_reason") or data.get("reason") or "").strip() or None

    issue_date = data.get("issue_date") or datetime.utcnow().date()
    if isinstance(issue_date, str):
        issue_date = datetime.fromisoformat(issue_date).date()

    due_date = data.get("due_date")
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date).date()
    if not due_date:
        due_date = issue_date + timedelta(days=14)

    vat_exempt = str(get_setting("INVOICE_VAT_EXEMPT", "0") or "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    if vat_exempt:
        tax_rate = Decimal("0.00")
    else:
        tax_rate = getattr(original, "tax_rate", None)
        if tax_rate is None:
            try:
                tax_rate = Decimal(str(get_setting("INVOICE_VAT_RATE", "23") or "23")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except Exception:
                tax_rate = Decimal("23.00")

    invoice = Invoice(
        job_id=original.job_id,
        invoice_type="correction",
        original_invoice_id=original.id,
        correction_reason=reason,
        invoice_number=generate_invoice_number("correction"),
        issue_date=issue_date,
        due_date=due_date,
        items=_normalize_items(items),
        tax_rate=tax_rate,
        buyer_name=original.buyer_name,
        buyer_address=original.buyer_address,
        buyer_nip=original.buyer_nip,
        buyer_email=original.buyer_email,
        payment_method=getattr(original, "payment_method", None) or "transfer",
        bank_account=getattr(original, "bank_account", None) or get_setting("COMPANY_ACCOUNT"),
        status="draft",
    )

    invoice.calculate_totals()
    db.session.add(invoice)
    db.session.commit()

    generate_invoice_pdf(invoice)
    return invoice


def create_invoice(data):
    """Tworzy nową fakturę dla zlecenia.

    Obsługuje minimalny payload z UI (job_id + payment_term_days) i potrafi
    wygenerować pozycje faktury z danych zlecenia.
    """

    def _parse_date(value):
        if value is None or value == "":
            return None
        # Already a date
        try:
            from datetime import date as _date

            if isinstance(value, _date):
                return value
        except Exception:
            pass

        if isinstance(value, str):
            # Expect YYYY-MM-DD
            return datetime.fromisoformat(value).date()
        raise BadRequest("Nieprawidłowy format daty")

    def _to_float(value, default=None):
        if value is None or value == "":
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _build_items_from_job(job):
        items = []

        offer_name = getattr(getattr(job, "offer", None), "name", None)
        base_price = _to_float(getattr(job, "base_price", None), 0.0) or 0.0

        if offer_name or base_price:
            items.append(
                {
                    "name": f"Pakiet: {offer_name}" if offer_name else "Usługa fotograficzna",
                    "quantity": 1.0,
                    "unit_price": float(base_price),
                    "total": float(base_price),
                }
            )

        try:
            addons = job.addons.all() if hasattr(job.addons, "all") else list(job.addons)
        except Exception:
            addons = []

        for addon in addons:
            if not getattr(addon, "is_selected", False):
                continue
            price = _to_float(getattr(addon, "price", None), 0.0) or 0.0
            name = getattr(addon, "name", "Dodatek")
            items.append(
                {
                    "name": f"Dodatek: {name}",
                    "quantity": 1.0,
                    "unit_price": float(price),
                    "total": float(price),
                }
            )

        # If we couldn't infer anything, fall back to final_price
        if not items:
            final_price = _to_float(getattr(job, "final_price", None), None)
            if final_price is None:
                return []
            items = [
                {
                    "name": "Usługa fotograficzna",
                    "quantity": 1.0,
                    "unit_price": float(final_price),
                    "total": float(final_price),
                }
            ]

        # Drop zero-value rows if there are other rows
        if len(items) > 1:
            items = [it for it in items if abs(float(it.get("total") or 0)) > 1e-9]

        # Voucher discount (negative line item)
        try:
            discount = _to_float(getattr(job, 'discount_amount', None), 0.0) or 0.0
        except Exception:
            discount = 0.0

        if discount > 0 and items:
            subtotal = sum(float(it.get('total') or 0) for it in items)
            applied = min(float(discount), float(subtotal))
            if applied > 0:
                code = None
                try:
                    code = getattr(getattr(job, 'voucher', None), 'code', None)
                except Exception:
                    code = None
                label = f"Rabat (voucher {code})" if code else "Rabat (voucher)"
                items.append(
                    {
                        'name': label,
                        'quantity': 1.0,
                        'unit_price': -float(applied),
                        'total': -float(applied),
                    }
                )

        return items

    job_id = data["job_id"]

    # Enforcement - sprawdź czy można generować fakturę
    can_generate_invoice(job_id)

    job = get_job_by_id(job_id)
    customer = job.customer

    issue_date = _parse_date(data.get("issue_date")) or datetime.utcnow().date()

    due_date = _parse_date(data.get("due_date"))
    if not due_date:
        payment_term_days = data.get("payment_term_days")
        try:
            payment_term_days = int(payment_term_days) if payment_term_days is not None else 14
        except Exception:
            payment_term_days = 14
        due_date = issue_date + timedelta(days=payment_term_days)

    items = data.get("items")
    if not items:
        items = _build_items_from_job(job)

    if not items:
        raise BadRequest("Nie można wygenerować pozycji faktury dla tego zlecenia")

    # Normalize incoming items to numeric totals
    normalized_items = []
    for item in items:
        quantity = _to_float(item.get("quantity"), 1.0) or 1.0
        unit_price = _to_float(item.get("unit_price"), 0.0) or 0.0
        total = _to_float(item.get("total"), None)
        if total is None:
            total = quantity * unit_price
        normalized_items.append(
            {
                "name": item.get("name") or "Pozycja",
                "quantity": float(quantity),
                "unit_price": float(unit_price),
                "total": float(total),
            }
        )

    # Utwórz fakturę
    def _parse_tax_rate(value, default: str = "23"):
        raw = value
        if raw is None or raw == "":
            raw = default
        try:
            return Decimal(str(raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal("23.00")

    vat_exempt = str(get_setting("INVOICE_VAT_EXEMPT", "0") or "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    default_vat_rate = "0" if vat_exempt else str(get_setting("INVOICE_VAT_RATE", "23") or "23")
    tax_rate = _parse_tax_rate(data.get("tax_rate"), default=default_vat_rate)
    if vat_exempt:
        # When business is VAT-exempt, always force 0% VAT regardless of UI payload.
        tax_rate = Decimal("0.00")

    invoice_type = (data.get("invoice_type") or "final").strip().lower()
    if invoice_type not in {"standard", "deposit", "final"}:
        # correction invoices use a dedicated endpoint for linkage + reason.
        invoice_type = "final"

    invoice = Invoice(
        job_id=job_id,
        invoice_type=invoice_type,
        invoice_number=generate_invoice_number(invoice_type),
        issue_date=issue_date,
        due_date=due_date,
        items=normalized_items,
        tax_rate=tax_rate,
        buyer_name=customer.full_name,
        buyer_address=(
            f"{customer.street}, {customer.postal_code} {customer.city}" if customer.street else None
        ),
        buyer_nip=customer.nip,
        buyer_email=customer.email,
        payment_method=data.get("payment_method", "transfer"),
        bank_account=data.get("bank_account") or get_setting("COMPANY_ACCOUNT"),
        notes=data.get("notes"),
        internal_notes=data.get("internal_notes"),
        status="draft",
    )

    # Oblicz sumy
    invoice.calculate_totals()

    db.session.add(invoice)
    db.session.commit()

    # Generuj PDF
    generate_invoice_pdf(invoice)

    return invoice



def get_invoice_by_id(invoice_id):
    """Pobiera fakturę po ID."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise NotFound(f'Faktura #{invoice_id} nie istnieje')
    return invoice


def get_invoices_by_job(job_id):
    """Pobiera wszystkie faktury dla zlecenia."""
    return Invoice.query.filter_by(job_id=job_id).all()


def get_all_invoices(filters=None, page=1, per_page=50):
    """
    Pobiera wszystkie faktury z filtrami.
    
    Args:
        filters: dict (status, job_id, date_from, date_to)
        page: numer strony
        per_page: elementów na stronę
    
    Returns:
        dict: paginowane wyniki
    """
    query = Invoice.query
    
    if filters:
        if 'status' in filters:
            query = query.filter_by(status=filters['status'])
        if 'invoice_type' in filters:
            query = query.filter_by(invoice_type=filters['invoice_type'])
        if 'job_id' in filters:
            query = query.filter_by(job_id=filters['job_id'])
        if 'date_from' in filters:
            query = query.filter(Invoice.issue_date >= filters['date_from'])
        if 'date_to' in filters:
            query = query.filter(Invoice.issue_date <= filters['date_to'])
    
    query = query.order_by(Invoice.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    }


def update_invoice(invoice_id, data):
    """Aktualizuje fakturę."""
    invoice = get_invoice_by_id(invoice_id)

    # Business rule: invoices are immutable after issuing; use correction invoices.
    if invoice.status != 'draft':
        raise BadRequest('Nie można edytować faktury po wystawieniu. Użyj faktury korygującej.')
    
    allowed_fields = ['due_date', 'items', 'payment_method', 'notes', 'internal_notes']
    
    for field in allowed_fields:
        if field in data:
            setattr(invoice, field, data[field])
    
    # Przelicz sumy jeśli zmieniły się pozycje
    if 'items' in data:
        invoice.items = _normalize_items(invoice.items)
        invoice.calculate_totals()
    
    # Regeneruj PDF
    generate_invoice_pdf(invoice)
    
    db.session.commit()
    return invoice


def issue_invoice(invoice_id):
    """
    Wystawia fakturę (zmienia status na issued).
    
    Args:
        invoice_id: ID faktury
    
    Returns:
        Invoice: faktura
    """
    invoice = get_invoice_by_id(invoice_id)
    
    if invoice.status != 'draft':
        raise BadRequest('Można wystawić tylko wersję roboczą')
    
    if not invoice.pdf_path:
        raise BadRequest('Brak PDF - wygeneruj fakturę')
    
    invoice.status = 'issued'
    db.session.commit()
    
    # TODO: Wysłanie emaila z fakturą
    
    return invoice


def send_invoice(invoice_id):
    """Marks invoice as issued ("sent") and ensures PDF exists.

    The app currently doesn't implement email delivery; this endpoint is used
    by the UI to finalize/issue the invoice.
    """
    invoice = get_invoice_by_id(invoice_id)

    if not invoice.pdf_path:
        generate_invoice_pdf(invoice)

    # Make it idempotent: sending an already issued/paid invoice is a no-op.
    if invoice.status == 'draft':
        invoice = issue_invoice(invoice_id)

    return invoice


def cancel_invoice(invoice_id):
    """Anuluje fakturę."""
    invoice = get_invoice_by_id(invoice_id)
    
    if invoice.paid_amount > 0:
        raise BadRequest('Nie można anulować faktury z płatnościami')
    
    invoice.status = 'cancelled'
    db.session.commit()
    return invoice


def delete_invoice(invoice_id):
    """Back-compat for REST route: treat delete as cancel (draft-only, no payments)."""
    invoice = get_invoice_by_id(invoice_id)
    if invoice.status != "draft":
        raise BadRequest("Nie można usunąć/anulować faktury po wystawieniu")
    return cancel_invoice(invoice_id)


def generate_invoice_pdf(invoice):
    """
    Generuje PDF faktury.
    
    Args:
        invoice: obiekt Invoice
    
    Returns:
        str: ścieżka do pliku PDF
    """
    # If a valid PDF already exists, do not overwrite it.
    def _is_valid_pdf(path: str | None) -> bool:
        if not path:
            return False
        try:
            if not os.path.exists(path):
                return False
            with open(path, "rb") as f:
                return f.read(5) == b"%PDF-"
        except Exception:
            return False

    if _is_valid_pdf(getattr(invoice, "pdf_path", None)):
        return invoice.pdf_path

    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:
        raise BadRequest("Brak biblioteki WeasyPrint - nie można wygenerować PDF") from e

    invoices_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    invoices_folder = os.path.join(invoices_folder, 'invoices')
    os.makedirs(invoices_folder, exist_ok=True)

    filename = f"invoice_{invoice.invoice_number.replace('/', '_')}.pdf"
    pdf_path = os.path.join(invoices_folder, filename)

    company_name = get_setting("COMPANY_NAME", "")
    company_address = get_setting("COMPANY_ADDRESS", "")
    company_nip = get_setting("COMPANY_NIP", "")
    company_phone = get_setting("COMPANY_PHONE", "")
    company_email = get_setting("COMPANY_EMAIL", "")
    company_bank = get_setting("COMPANY_BANK", "")
    company_account = get_setting("COMPANY_ACCOUNT", "")

    buyer_name = getattr(invoice, "buyer_name", "") or ""
    buyer_address = getattr(invoice, "buyer_address", None)
    buyer_nip = getattr(invoice, "buyer_nip", None)
    buyer_email = getattr(invoice, "buyer_email", None)

    issue_date = getattr(invoice, "issue_date", None)
    due_date = getattr(invoice, "due_date", None)

    tax_rate = float(getattr(invoice, "tax_rate", 0) or 0)
    subtotal = float(getattr(invoice, "subtotal", 0) or 0)
    tax_amount = float(getattr(invoice, "tax_amount", 0) or 0)
    total_amount = float(getattr(invoice, "total_amount", 0) or 0)

    vat_exempt = str(get_setting("INVOICE_VAT_EXEMPT", "0") or "0").strip().lower() in {"1", "true", "yes", "y", "on"}
    if vat_exempt:
        # Render as VAT-exempt: VAT amount must be 0 and total equals subtotal.
        tax_rate = 0.0
        tax_amount = 0.0
        total_amount = subtotal
        vat_label = "ZW"
    else:
        vat_label = f"{tax_rate:.0f}%"

    vat_exempt_note = ""
    if vat_exempt:
        vat_exempt_note = (
            "<div class='row' style='color:#666'>"
            "<strong>Zwolnienie z VAT:</strong><br/>"
            "podmiotowego – art. 113 ust. 1 i 9,<br/>"
            "przedmiotowego – art. 43 ust. 1."
            "</div>"
        )

    def _fmt_date(d):
        try:
            return d.strftime("%Y-%m-%d") if d else "-"
        except Exception:
            return str(d)

    def _fmt_pln(value):
        try:
            return f"{float(value):.2f} PLN"
        except Exception:
            return "0.00 PLN"

    items = getattr(invoice, "items", None) or []
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(it.get('name') or 'Pozycja'))}</td>"
        f"<td class='right'>{escape(str(it.get('quantity') or ''))}</td>"
        f"<td class='right'>{escape(_fmt_pln(it.get('unit_price') or 0))}</td>"
        f"<td class='right'>{escape(_fmt_pln(it.get('total') or 0))}</td>"
        "</tr>"
        for it in items
    )
    if not rows:
        rows = "<tr><td colspan='4' style='color:#666'>Brak pozycji</td></tr>"

    invoice_type = (getattr(invoice, "invoice_type", None) or "final").strip().lower()
    title = "FAKTURA VAT"
    if invoice_type == "deposit":
        title = "FAKTURA VAT ZALICZKOWA"
    elif invoice_type == "correction":
        title = "FAKTURA KORYGUJĄCA"

    correction_meta = ""
    if invoice_type == "correction":
        orig_no = None
        try:
            orig_no = getattr(getattr(invoice, "original_invoice", None), "invoice_number", None)
        except Exception:
            orig_no = None
        reason = getattr(invoice, "correction_reason", None)
        parts = []
        if orig_no:
            parts.append(f"<div class='row'><span class='label'>Korygowana faktura:</span> <strong>{escape(str(orig_no))}</strong></div>")
        if reason:
            parts.append(f"<div class='row'><span class='label'>Powód korekty:</span> {escape(str(reason))}</div>")
        if parts:
            correction_meta = "<div class='box'>" + "".join(parts) + "</div>"

    html = f"""<!doctype html>
<html lang='pl'>
<head>
  <meta charset='utf-8'>
  <style>
    @page {{ size: A4; margin: 18mm; }}
    body {{ font-family: DejaVu Sans, Arial, sans-serif; font-size: 11pt; line-height: 1.35; }}
    h1 {{ font-size: 16pt; margin: 0 0 6mm 0; text-align: center; }}
    .meta {{ display: flex; justify-content: space-between; margin-bottom: 6mm; }}
    .box {{ border: 1px solid #ddd; padding: 5mm; margin-bottom: 5mm; }}
    .row {{ margin: 1.8mm 0; }}
    .label {{ color: #444; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #ddd; padding: 2.5mm; }}
    th {{ background: #f4f4f4; text-align: left; }}
    .right {{ text-align: right; }}
  </style>
</head>
<body>
    <h1>{escape(title)}</h1>

  <div class='meta'>
    <div><span class='label'>Numer:</span> <strong>{escape(str(invoice.invoice_number))}</strong></div>
    <div><span class='label'>Data wystawienia:</span> <strong>{escape(_fmt_date(issue_date))}</strong></div>
  </div>

  <div class='box'>
    <div class='row'><strong>Sprzedawca</strong></div>
    <div class='row'>{escape(company_name)}</div>
    <div class='row'>{escape(company_address)}</div>
    <div class='row'><span class='label'>NIP:</span> {escape(company_nip)} &nbsp;&nbsp; <span class='label'>Tel.:</span> {escape(company_phone)} &nbsp;&nbsp; <span class='label'>Email:</span> {escape(company_email)}</div>
    {f"<div class='row'><span class='label'>Bank:</span> {escape(company_bank)} &nbsp;&nbsp; <span class='label'>Nr konta:</span> {escape(company_account)}</div>" if (company_bank or company_account) else ""}
  </div>

  <div class='box'>
    <div class='row'><strong>Nabywca</strong></div>
    <div class='row'>{escape(buyer_name)}</div>
    {f"<div class='row'>{escape(buyer_address)}</div>" if buyer_address else ""}
    {f"<div class='row'><span class='label'>NIP:</span> {escape(buyer_nip)}</div>" if buyer_nip else ""}
    {f"<div class='row'><span class='label'>Email:</span> {escape(buyer_email)}</div>" if buyer_email else ""}
  </div>

  <div class='box'>
    <div class='row'><span class='label'>Termin płatności:</span> <strong>{escape(_fmt_date(due_date))}</strong></div>
    <div class='row'><span class='label'>Metoda płatności:</span> <strong>{escape(str(getattr(invoice, 'payment_method', '') or ''))}</strong></div>
  </div>

    {correction_meta}

  <table>
    <thead>
      <tr>
        <th>Nazwa</th>
        <th class='right'>Ilość</th>
        <th class='right'>Cena</th>
        <th class='right'>Wartość</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>

  <div class='box' style='margin-top:5mm'>
    <div class='row right'><span class='label'>Suma netto:</span> <strong>{escape(_fmt_pln(subtotal))}</strong></div>
    <div class='row right'><span class='label'>VAT ({escape(vat_label)}):</span> <strong>{escape(_fmt_pln(tax_amount))}</strong></div>
    <div class='row right'><span class='label'>Suma brutto:</span> <strong>{escape(_fmt_pln(total_amount))}</strong></div>
        {vat_exempt_note}
  </div>

</body>
</html>"""

    HTML(string=html).write_pdf(pdf_path)

    invoice.pdf_path = pdf_path
    db.session.commit()
    return pdf_path

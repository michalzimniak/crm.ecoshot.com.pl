"""Contracts business logic.

Handles contract generation, PDF creation, and digital signatures.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app
from markupsafe import escape
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.utils import secure_filename

from app.contracts.models import Contract
from app.core.enforcement import can_create_contract
from app.extensions import db
from app.jobs.services import get_job_by_id
from app.settings.services import get_setting


def get_all_contracts(filters: dict | None = None, search: str | None = None, page: int = 1, per_page: int = 50) -> dict:
    """Pobiera wszystkie umowy z filtrami i paginacją."""
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload

    from app.customers.models import Customer
    from app.jobs.models import Job

    query = Contract.query.options(
        joinedload(Contract.job).joinedload(Job.customer),
        joinedload(Contract.job).joinedload(Job.offer),
    )

    joined_job = False
    joined_customer = False

    if filters:
        status = filters.get("status")
        if status:
            query = query.filter(Contract.status == status)

        job_id = filters.get("job_id")
        if job_id:
            query = query.filter(Contract.job_id == int(job_id))

        customer_id = filters.get("customer_id")
        if customer_id:
            query = query.join(Contract.job)
            joined_job = True
            query = query.filter(Job.customer_id == int(customer_id))

    if search and search.strip():
        term = f"%{search.strip()}%"
        if not joined_job:
            query = query.join(Contract.job)
            joined_job = True
        if not joined_customer:
            query = query.join(Job.customer)
            joined_customer = True

        query = query.filter(
            or_(
                Contract.contract_number.ilike(term),
                Job.title.ilike(term),
                Customer.email.ilike(term),
                Customer.first_name.ilike(term),
                Customer.last_name.ilike(term),
                Customer.company_name.ilike(term),
            )
        )

    query = query.order_by(Contract.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "items": pagination.items,
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }


def generate_contract_number() -> str:
    """Generuje numer umowy: UMW/YYYY/NNN."""
    year = datetime.utcnow().year

    count = Contract.query.filter(Contract.contract_number.like(f"UMW/{year}/%"))
    next_number = count.count() + 1
    return f"UMW/{year}/{next_number:03d}"


def _format_date_pl(value: date | datetime | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d.%m.%Y")


def _format_currency_pl(value) -> str:
    if value is None:
        return ""
    try:
        amount = float(value) if not isinstance(value, Decimal) else float(value)
    except Exception:
        return str(value)
    return f"{amount:,.2f} zł".replace(",", " ").replace(".", ",")


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _nl2br(text: str) -> str:
    return str(escape(text)).replace("\n", "<br>")


def _get_selected_addons(job):
    addons = getattr(job, "addons", None)
    if addons is None:
        return []
    try:
        # relationship is lazy='dynamic'
        return addons.filter_by(is_selected=True).all()
    except Exception:
        return [a for a in addons if getattr(a, "is_selected", False)]


def create_contract(data: dict) -> Contract:
    """Tworzy nową umowę dla zlecenia."""
    job_id = data["job_id"]

    can_create_contract(job_id)

    existing = Contract.query.filter_by(job_id=job_id).first()
    if existing:
        raise BadRequest(f"Umowa dla zlecenia #{job_id} już istnieje")

    job = get_job_by_id(job_id)

    contract = Contract(
        job_id=job_id,
        contract_number=generate_contract_number(),
        valid_until=data.get("valid_until")
        or (datetime.utcnow().date() + timedelta(days=30)),
        terms_content=data.get("terms_content") or get_default_terms(),
        notes=data.get("notes"),
        status="draft",
    )

    # Precompute default deposit amount (10% of order value) so it can be tracked in CRM.
    total_price = _to_decimal(getattr(job, "final_price", None))
    deposit_percent = _to_decimal(getattr(contract, "deposit_percent", None) or Decimal("10"))
    if total_price > 0 and (contract.deposit_amount is None or _to_decimal(contract.deposit_amount) <= 0):
        contract.deposit_amount = (total_price * deposit_percent / Decimal("100")).quantize(Decimal("0.01"))

    db.session.add(contract)
    db.session.commit()

    generate_contract_pdf(contract)

    return contract


def get_contract_by_id(contract_id: int) -> Contract:
    """Pobiera umowę po ID."""
    contract = db.session.get(Contract, contract_id)
    if not contract:
        raise NotFound(f"Umowa #{contract_id} nie istnieje")
    return contract


def get_contract_by_job_id(job_id: int) -> Contract:
    """Pobiera umowę dla zlecenia."""
    contract = Contract.query.filter_by(job_id=job_id).first()
    if not contract:
        raise NotFound(f"Brak umowy dla zlecenia #{job_id}")
    return contract


def update_contract(contract_id: int, data: dict) -> Contract:
    """Aktualizuje umowę."""
    contract = get_contract_by_id(contract_id)

    if contract.status == "signed":
        raise BadRequest("Nie można edytować podpisanej umowy")

    allowed_fields = [
        "valid_until",
        "terms_content",
        "notes",
        "deposit_percent",
        "deposit_amount",
        "deposit_status",
        "deposit_paid_amount",
        "deposit_paid_at",
        "deposit_notes",
    ]

    pdf_needs_regen = False

    for field in allowed_fields:
        if field in data:
            setattr(contract, field, data[field])

            if field in {
                "terms_content",
                "deposit_percent",
                "deposit_amount",
                "deposit_status",
                "deposit_paid_amount",
                "deposit_paid_at",
                "deposit_notes",
            }:
                pdf_needs_regen = True

    # Convenience rules for deposit state
    if "deposit_status" in data:
        if contract.deposit_status == "paid":
            if not contract.deposit_paid_at:
                contract.deposit_paid_at = datetime.utcnow()
            if contract.deposit_paid_amount is None and contract.deposit_amount is not None:
                contract.deposit_paid_amount = contract.deposit_amount
        elif contract.deposit_status in {"unpaid", "waived"}:
            # Keep deposit_amount as a target, but clear actual payment info.
            contract.deposit_paid_amount = None
            contract.deposit_paid_at = None

    if pdf_needs_regen:
        generate_contract_pdf(contract)

    db.session.commit()
    return contract


def sign_contract(
    contract_id: int, signature_data: str, ip_address: str | None = None
) -> Contract:
    """Podpisuje umowę."""
    contract = get_contract_by_id(contract_id)

    if contract.status == "signed":
        raise BadRequest("Umowa jest już podpisana")

    if not contract.pdf_path or not os.path.exists(contract.pdf_path):
        raise BadRequest("Brak pliku PDF umowy")

    contract.signature_data = signature_data
    contract.signature_ip = ip_address
    contract.signed_at = datetime.utcnow()
    contract.status = "signed"

    db.session.commit()

    # After a contract is signed, create a deposit invoice (zaliczkowa).
    # Idempotent: if it already exists, services returns existing.
    try:
        from app.invoices.services import create_deposit_invoice_for_job

        create_deposit_invoice_for_job(contract.job_id)
    except Exception:
        # Don't block contract signing if invoice generation fails.
        pass
    return contract


def send_contract(contract_id: int) -> Contract:
    """Wysyła umowę do klienta."""
    contract = get_contract_by_id(contract_id)

    if not contract.pdf_path:
        raise BadRequest("Brak PDF - wygeneruj umowę")

    contract.status = "sent"
    contract.sent_at = datetime.utcnow()

    db.session.commit()

    # TODO: Wysłanie emaila z linkiem do podpisu

    return contract


def generate_contract_pdf(contract: Contract) -> str:
    """Generuje PDF umowy."""
    if contract.status == "signed":
        raise BadRequest("Nie można regenerować PDF podpisanej umowy")

    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:
        raise BadRequest("Brak biblioteki WeasyPrint - nie można wygenerować PDF") from e

    contracts_folder = current_app.config.get("CONTRACTS_FOLDER", "uploads/contracts")
    os.makedirs(contracts_folder, exist_ok=True)

    filename = f"contract_{contract.contract_number.replace('/', '_')}.pdf"
    pdf_path = os.path.join(contracts_folder, filename)

    job = contract.job or get_job_by_id(contract.job_id)
    customer = getattr(job, "customer", None)
    offer = getattr(job, "offer", None)
    selected_addons = _get_selected_addons(job)

    company_name = get_setting("COMPANY_NAME", "")
    company_address = get_setting("COMPANY_ADDRESS", "")
    company_nip = get_setting("COMPANY_NIP", "")
    company_phone = get_setting("COMPANY_PHONE", "")
    company_email = get_setting("COMPANY_EMAIL", "")
    company_bank = get_setting("COMPANY_BANK", "")
    company_account = get_setting("COMPANY_ACCOUNT", "")

    customer_name = (
        getattr(customer, "display_name", None)
        or getattr(customer, "full_name", None)
        or ""
    )
    customer_address_parts = [
        getattr(customer, "street", None),
        f"{getattr(customer, 'postal_code', '')} {getattr(customer, 'city', '')}".strip(),
        getattr(customer, "country", None),
    ]
    customer_address = ", ".join([p for p in customer_address_parts if p])

    customer_type = getattr(customer, "customer_type", None)
    customer_nip = getattr(customer, "nip", None) if customer_type == "company" else None

    # Full legal name display
    if customer_type == "company":
        customer_legal_name = getattr(customer, "company_name", None) or customer_name
        contact_person = (getattr(customer, "full_name", None) or "").strip()
        customer_label_line = (
            f"{escape(customer_legal_name)}"
            + (f" (osoba kontaktowa: {escape(contact_person)})" if contact_person else "")
        )
    else:
        customer_legal_name = customer_name
        customer_label_line = escape(customer_legal_name)

    today = datetime.utcnow().date()

    total_price = _to_decimal(getattr(job, "final_price", None))
    deposit_percent = _to_decimal(getattr(contract, "deposit_percent", None) or Decimal("10"))
    if deposit_percent <= 0:
        deposit_percent = Decimal("10")

    # If deposit amount is explicitly set, respect it; else compute 10% of order value.
    deposit_amount = _to_decimal(getattr(contract, "deposit_amount", None))
    if deposit_amount <= 0 and total_price > 0:
        deposit_amount = (total_price * deposit_percent / Decimal("100")).quantize(Decimal("0.01"))
    remaining_amount = (total_price - deposit_amount).quantize(Decimal("0.01")) if total_price else Decimal("0.00")

    if selected_addons:
        addons_rows = "".join(
            f"<tr><td>{escape(a.name)}</td><td style='text-align:right'>{_format_currency_pl(a.price)}</td></tr>"
            for a in selected_addons
        )
    else:
        addons_rows = "<tr><td colspan='2' style='color:#666'>Brak dodatków</td></tr>"

    terms_html = _nl2br(contract.terms_content or "")

    html = f"""<!doctype html>
<html lang='pl'>
<head>
  <meta charset='utf-8'>
  <style>
    @page {{ size: A4; margin: 20mm; }}
    body {{ font-family: DejaVu Sans, Arial, sans-serif; font-size: 11pt; line-height: 1.35; }}
    h1 {{ font-size: 16pt; margin: 0 0 8mm 0; text-align: center; }}
    .meta {{ display: flex; justify-content: space-between; margin-bottom: 6mm; }}
    .box {{ border: 1px solid #ddd; padding: 6mm; margin-bottom: 6mm; }}
    .row {{ margin: 2mm 0; }}
    .label {{ color: #444; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #ddd; padding: 2.5mm; }}
    th {{ background: #f4f4f4; text-align: left; }}
    .right {{ text-align: right; }}
    .signatures {{ margin-top: 12mm; display: flex; justify-content: space-between; gap: 10mm; }}
    .sig {{ width: 48%; }}
    .sigline {{ margin-top: 18mm; border-top: 1px solid #000; padding-top: 2mm; text-align: center; }}
  </style>
</head>
<body>
  <h1>UMOWA WYKONANIA USŁUG FOTOGRAFICZNYCH</h1>

  <div class='meta'>
    <div><span class='label'>Numer umowy:</span> <strong>{escape(contract.contract_number)}</strong></div>
    <div><span class='label'>Data:</span> <strong>{_format_date_pl(today)}</strong></div>
  </div>

  <div class='box'>
    <div class='row'><strong>Strony umowy</strong></div>
    <div class='row'><span class='label'>Wykonawca:</span> <strong>{escape(company_name)}</strong></div>
    <div class='row'>{escape(company_address)}</div>
    <div class='row'><span class='label'>NIP:</span> {escape(company_nip)} &nbsp;&nbsp; <span class='label'>Tel.:</span> {escape(company_phone)} &nbsp;&nbsp; <span class='label'>Email:</span> {escape(company_email)}</div>
        {f"<div class='row'><span class='label'>Bank:</span> {escape(company_bank)} &nbsp;&nbsp; <span class='label'>Nr konta:</span> {escape(company_account)}</div>" if (company_bank or company_account) else ""}
    <hr style='border:none;border-top:1px solid #eee;margin:5mm 0'>
        <div class='row'><span class='label'>Zamawiający:</span> <strong>{customer_label_line}</strong></div>
    <div class='row'>{escape(customer_address)}</div>
    <div class='row'><span class='label'>Email:</span> {escape(getattr(customer, 'email', '') or '')} &nbsp;&nbsp; <span class='label'>Tel.:</span> {escape(getattr(customer, 'phone', '') or '')}</div>
    {f"<div class='row'><span class='label'>NIP:</span> {escape(customer_nip)}</div>" if customer_nip else ""}
  </div>

  <div class='box'>
    <div class='row'><strong>Przedmiot umowy</strong></div>
    <div class='row'><span class='label'>Zlecenie:</span> #{job.id} — {escape(job.title or '')}</div>
    <div class='row'><span class='label'>Wydarzenie:</span> {_format_date_pl(getattr(job, 'event_date', None))} &nbsp;&nbsp; <span class='label'>Lokalizacja:</span> {escape(getattr(job, 'event_location', '') or '')}</div>
    <div class='row'><span class='label'>Pakiet:</span> {escape(getattr(offer, 'name', '') or '')} &nbsp;&nbsp; <span class='label'>Cena bazowa:</span> {_format_currency_pl(getattr(job, 'base_price', None))}</div>
  </div>

  <div class='box'>
    <div class='row'><strong>Dodatki</strong></div>
    <table>
      <thead>
        <tr><th>Nazwa</th><th class='right'>Cena</th></tr>
      </thead>
      <tbody>
        {addons_rows}
      </tbody>
    </table>
        <div class='row right' style='margin-top:4mm'>
            <span class='label'>Wartość zlecenia (brutto):</span> <strong>{_format_currency_pl(total_price)}</strong>
        </div>
        <div class='row right'>
            <span class='label'>Zaliczka ({deposit_percent.normalize()}%):</span> <strong>{_format_currency_pl(deposit_amount)}</strong>
        </div>
        <div class='row right'>
            <span class='label'>Pozostało do zapłaty:</span> <strong>{_format_currency_pl(remaining_amount)}</strong>
        </div>
  </div>

  <div class='box'>
    <div class='row'><strong>Warunki</strong></div>
    <div class='row'>{terms_html}</div>
  </div>

  <div class='signatures'>
    <div class='sig'>
      <div class='sigline'>Wykonawca</div>
    </div>
    <div class='sig'>
      <div class='sigline'>Zamawiający</div>
    </div>
  </div>

</body>
</html>"""

    HTML(string=html).write_pdf(pdf_path)

    contract.pdf_path = pdf_path
    contract.pdf_hash = contract.generate_hash(pdf_path)

    db.session.commit()
    return pdf_path


def upload_signed_scan(contract_id: int, file_storage) -> Contract:
    """Zapisuje skan/zdjęcie podpisanej umowy (archiwizacja)."""
    contract = get_contract_by_id(contract_id)

    if not file_storage or not getattr(file_storage, "filename", None):
        raise BadRequest("Brak pliku")

    original_name = str(file_storage.filename)
    filename = secure_filename(original_name)
    if not filename:
        raise BadRequest("Nieprawidłowa nazwa pliku")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"pdf", "png", "jpg", "jpeg"}
    if ext not in allowed:
        raise BadRequest("Nieobsługiwany format pliku (dozwolone: PDF/JPG/PNG)")

    contracts_folder = current_app.config.get("CONTRACTS_FOLDER", "uploads/contracts")
    scans_folder = os.path.join(contracts_folder, "signed_scans")
    os.makedirs(scans_folder, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    stored_name = f"contract_{contract.id}_signed_{timestamp}_{filename}"
    stored_path = os.path.join(scans_folder, stored_name)

    file_storage.save(stored_path)

    try:
        size = os.path.getsize(stored_path)
    except OSError:
        size = None

    contract.signed_scan_path = stored_path
    contract.signed_scan_original_filename = original_name
    contract.signed_scan_mime_type = getattr(file_storage, "mimetype", None)
    contract.signed_scan_size = size
    contract.signed_scan_uploaded_at = datetime.utcnow()

    # Auto: uploading a signed scan implies the contract is signed.
    if contract.status != "signed":
        contract.status = "signed"
        if not contract.signed_at:
            contract.signed_at = datetime.utcnow()

        # Auto: move the job to "Oczekujące" (UI label), which maps to status=draft.
        try:
            job = contract.job or get_job_by_id(contract.job_id)
            if job and job.status not in {"completed", "cancelled", "rejected"}:
                job.status = "draft"
        except Exception:
            # Do not fail upload if job update fails.
            pass

        # Auto: after signing, create a deposit invoice (idempotent).
        try:
            from app.invoices.services import create_deposit_invoice_for_job

            create_deposit_invoice_for_job(contract.job_id)
        except Exception:
            # Don't block upload if invoice generation fails.
            pass

    db.session.commit()
    return contract


def get_default_terms() -> str:
    """Zwraca domyślną treść warunków umowy."""
    return """WARUNKI UMOWY FOTOGRAFICZNEJ

1. Przedmiot umowy
2. Zakres usług
3. Wynagrodzenie
4. Prawa autorskie
5. Postanowienia końcowe
"""
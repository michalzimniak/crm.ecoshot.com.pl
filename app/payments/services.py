"""Payments business logic."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from werkzeug.exceptions import BadRequest, NotFound

from app.extensions import db
from app.invoices.services import get_invoice_by_id
from app.jobs.services import get_job_by_id
from app.payments.models import Payment
from app.payments.payu import PayUClient


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_payment_by_id(payment_id: int) -> Payment:
    payment = db.session.get(Payment, payment_id)
    if not payment:
        raise NotFound(f'Płatność #{payment_id} nie istnieje')
    return payment


def get_all_payments(filters=None, page: int = 1, per_page: int = 50) -> dict:
    query = Payment.query

    if filters:
        if filters.get('status'):
            query = query.filter(Payment.status == filters['status'])
        if filters.get('payment_method'):
            query = query.filter(Payment.payment_method == filters['payment_method'])
        if filters.get('source'):
            query = query.filter(Payment.source == filters['source'])
        if filters.get('kind'):
            query = query.filter(Payment.kind == filters['kind'])
        if filters.get('invoice_id'):
            query = query.filter(Payment.invoice_id == int(filters['invoice_id']))
        if filters.get('job_id'):
            query = query.filter(Payment.job_id == int(filters['job_id']))

    query = query.order_by(Payment.payment_date.desc(), Payment.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
    }


def _job_prepayments_total(job_id: int) -> Decimal:
    total = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.job_id == job_id)
        .filter(Payment.invoice_id.is_(None))
        .filter(Payment.status == 'completed')
        .scalar()
    )
    return _to_decimal(total)


def create_payment(data: dict) -> Payment:
    invoice_id = data.get('invoice_id')
    job_id = data.get('job_id')

    if not invoice_id and not job_id:
        raise BadRequest('Wymagane: invoice_id lub job_id')

    invoice = None
    job = None

    if invoice_id:
        invoice = get_invoice_by_id(int(invoice_id))
        if invoice.status == 'cancelled':
            raise BadRequest('Nie można dodawać płatności do anulowanej faktury')
        job_id = invoice.job_id

    if job_id:
        job = get_job_by_id(int(job_id))

    amount = _to_decimal(data['amount']).quantize(Decimal('0.01'))
    if amount <= 0:
        raise BadRequest('Kwota musi być większa od 0')

    kind = data.get('kind') or ('invoice' if invoice_id else 'prepayment')
    source = data.get('source') or 'manual'
    currency = (data.get('currency') or 'PLN').upper()
    payment_method = data.get('payment_method') or 'transfer'
    status = data.get('status') or 'pending'
    payment_date = data.get('payment_date') or datetime.utcnow()

    if invoice is not None:
        invoice.recalculate_paid_amount()
        remaining = _to_decimal(invoice.total_amount) - _to_decimal(invoice.paid_amount)
        if amount > remaining:
            raise BadRequest(f'Kwota płatności ({amount}) przekracza pozostałą do zapłaty ({remaining})')
    elif job is not None:
        job_total = _to_decimal(getattr(job, 'final_price', None))
        if job_total > 0:
            remaining = job_total - _job_prepayments_total(job.id)
            if amount > remaining:
                raise BadRequest(f'Kwota płatności ({amount}) przekracza pozostałą do zapłaty ({remaining})')

    payment = Payment(
        job_id=job_id,
        invoice_id=invoice_id,
        amount=amount,
        currency=currency,
        kind=kind,
        source=source,
        payment_method=payment_method,
        status=status,
        payment_date=payment_date,
        transaction_id=data.get('transaction_id'),
        reference=data.get('reference'),
        notes=data.get('notes'),
    )

    db.session.add(payment)

    if payment.status == 'completed' and invoice is not None:
        db.session.flush()
        payment.complete()

    db.session.commit()
    return payment


def complete_payment(payment_id: int, transaction_id: str | None = None) -> Payment:
    payment = get_payment_by_id(payment_id)

    if payment.status == 'completed':
        raise BadRequest('Płatność jest już potwierdzona')

    if transaction_id:
        payment.transaction_id = transaction_id

    payment.complete()
    db.session.commit()
    return payment


def refund_payment(payment_id: int, reason: str) -> Payment:
    payment = get_payment_by_id(payment_id)
    payment.notes = f"{payment.notes or ''}\n\nZWROT: {reason}".strip()
    payment.refund()
    db.session.commit()
    return payment


def delete_payment(payment_id: int) -> None:
    payment = get_payment_by_id(payment_id)
    if payment.status in {'completed', 'refunded'}:
        raise BadRequest('Nie można usunąć zrealizowanej lub zwróconej płatności')
    db.session.delete(payment)
    db.session.commit()


def payu_create_order_for_invoice(*, invoice_id: int, buyer_email: str | None = None) -> dict:
    invoice = get_invoice_by_id(invoice_id)

    invoice.recalculate_paid_amount()
    remaining = _to_decimal(invoice.total_amount) - _to_decimal(invoice.paid_amount)
    if remaining <= 0:
        raise BadRequest('Faktura jest już opłacona')

    client = PayUClient.from_flask_config()
    order = client.create_order_for_invoice(invoice, amount=remaining, buyer_email=buyer_email)

    ext_order_id = order.get('extOrderId')
    payu_order_id = order.get('orderId')
    redirect_url = order.get('redirectUri')

    payment = Payment.query.filter_by(provider_ext_order_id=ext_order_id).first()
    if not payment:
        payment = Payment(
            job_id=invoice.job_id,
            invoice_id=invoice.id,
            amount=remaining,
            currency='PLN',
            kind='invoice',
            source='payu',
            payment_method='other',
            status='pending',
            payment_date=datetime.utcnow(),
            provider_order_id=payu_order_id,
            provider_ext_order_id=ext_order_id,
            provider_status=order.get('status'),
            provider_payload=order,
            redirect_url=redirect_url,
            reference=f"PayU {invoice.invoice_number}",
        )
        db.session.add(payment)
    else:
        payment.provider_order_id = payu_order_id or payment.provider_order_id
        payment.redirect_url = redirect_url or payment.redirect_url
        payment.provider_status = order.get('status') or payment.provider_status
        payment.provider_payload = order

    db.session.commit()
    return {'redirect_url': redirect_url, 'ext_order_id': ext_order_id}


def payu_handle_notification(
    payload: dict,
    *,
    raw_body: bytes | None = None,
    signature_header: str | None = None,
) -> dict:
    client = PayUClient.from_flask_config()
    client.verify_notification(raw_body=raw_body, signature_header=signature_header)

    order = payload.get('order') or {}
    ext_order_id = order.get('extOrderId')
    payu_order_id = order.get('orderId')
    status = order.get('status')

    if not ext_order_id and not payu_order_id:
        raise BadRequest('Brak extOrderId/orderId')

    payment = None
    if ext_order_id:
        payment = Payment.query.filter_by(provider_ext_order_id=ext_order_id).first()
    if not payment and payu_order_id:
        payment = Payment.query.filter_by(provider_order_id=payu_order_id).first()

    if not payment:
        description = (order.get('description') or '').strip()
        payment = Payment(
            amount=Decimal('0.01'),
            currency='PLN',
            kind='invoice',
            source='payu',
            payment_method='other',
            status='pending',
            payment_date=datetime.utcnow(),
            provider_order_id=payu_order_id,
            provider_ext_order_id=ext_order_id,
            provider_status=status,
            provider_payload=payload,
            reference=f"PayU {description}" if description else 'PayU',
        )
        db.session.add(payment)

    payment.provider_order_id = payu_order_id or payment.provider_order_id
    payment.provider_status = status or payment.provider_status
    payment.provider_payload = payload

    if status == 'COMPLETED':
        if payment.status != 'completed':
            payment.complete()
    elif status in {'CANCELED', 'REJECTED', 'FAILED'}:
        if payment.status != 'completed':
            payment.status = 'failed'
    else:
        if payment.status != 'completed':
            payment.status = 'pending'

    db.session.commit()
    return {
        'payment_id': payment.id,
        'status': payment.status,
        'provider_status': payment.provider_status,
    }

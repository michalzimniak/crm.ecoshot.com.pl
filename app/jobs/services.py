"""
Jobs business logic.
Handles job workflow, add-ons, and pricing with enforcement.
"""

from datetime import date, datetime, time, timedelta
from werkzeug.exceptions import BadRequest, NotFound
from app.extensions import db
from app.jobs.models import Job, Offer, OfferAddon, JobAddon
from app.customers.services import get_customer_by_id
from app.core.enforcement import enforce_job_workflow


def _parse_iso_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except Exception:
            return None
    return None


def _parse_iso_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Accept datetime-local and ISO8601.
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            # Fallback: allow plain date.
            try:
                return datetime.combine(date.fromisoformat(raw), time.min)
            except Exception:
                return None
    return None


def _calculate_reservation_window(offer: Offer, event_start: datetime) -> tuple[datetime, datetime]:
    hours = getattr(offer, "hours_included", None)
    try:
        hours_int = int(hours) if hours is not None else 0
    except Exception:
        hours_int = 0

    duration_minutes = max(0, hours_int) * 60
    if duration_minutes <= 0:
        duration_minutes = 60  # sensible default when offer has no duration
    return event_start, event_start + timedelta(minutes=duration_minutes)


def _assert_no_reservation_conflict(event_start: datetime, event_end: datetime, exclude_job_id: int | None = None):
    if not event_start or not event_end:
        return
    if event_end <= event_start:
        raise BadRequest("Nieprawidłowy zakres czasu zlecenia")

    query = Job.query
    if exclude_job_id:
        query = query.filter(Job.id != exclude_job_id)

    query = query.filter(
        Job.status.notin_(["cancelled", "rejected"]),
        Job.event_start.isnot(None),
        Job.event_end.isnot(None),
        Job.event_start < event_end,
        Job.event_end > event_start,
    )

    conflict = query.order_by(Job.event_start.asc()).first()
    if conflict:
        raise BadRequest(f"Termin jest już zarezerwowany (konflikt ze zleceniem #{conflict.id})")


def create_job(data):
    """
    Tworzy nowe zlecenie.
    
    Args:
        data: dict z danymi zlecenia
    
    Returns:
        Job: nowe zlecenie
        
    Raises:
        BadRequest: jeśli dane są nieprawidłowe
    """
    # Walidacja customer
    customer = get_customer_by_id(data['customer_id'])
    
    selected_addon_ids = set(data.get('selected_addon_ids') or [])
    addon_quantities = data.get('addon_quantities') or {}

    # Walidacja offer
    offer = db.session.get(Offer, data['offer_id'])
    if not offer or not offer.is_active:
        raise BadRequest('Nieprawidłowa oferta')

    event_start = _parse_iso_datetime(data.get("event_start"))
    if not event_start:
        # Backward-compatibility: accept date-only.
        event_date = _parse_iso_date(data.get("event_date"))
        if event_date:
            event_start = datetime.combine(event_date, time.min)

    if not event_start:
        raise BadRequest("Wymagana jest data i godzina (event_start)")

    event_start, event_end = _calculate_reservation_window(offer, event_start)
    _assert_no_reservation_conflict(event_start, event_end)
    
    # Allow only one online album validity plan
    if selected_addon_ids:
        selected_online = [a.id for a in OfferAddon.query.filter(OfferAddon.id.in_(selected_addon_ids)).all() if a.category == 'online_album']
        if len(selected_online) > 1:
            raise BadRequest('Można wybrać tylko jeden wariant albumu online')

    # Utwórz zlecenie
    job = Job(
        customer_id=data['customer_id'],
        offer_id=data['offer_id'],
        title=data['title'],
        description=data.get('description'),
        event_date=event_start.date(),
        event_start=event_start,
        event_end=event_end,
        event_location=data.get('event_location'),
        base_price=data.get('base_price', offer.base_price),
        final_price=data.get('base_price', offer.base_price),
        notes=data.get('notes'),
        internal_notes=data.get('internal_notes'),
        status='draft'
    )
    
    db.session.add(job)
    db.session.flush()  # Aby mieć job.id
    
    # Dodaj dostępne dodatki z oferty
    for offer_addon in offer.addons.filter_by(is_available=True):
        initial_qty = 0 if offer_addon.pricing_model == 'per_unit' else 1
        job_addon = JobAddon(
            job_id=job.id,
            offer_addon_id=offer_addon.id,
            name=offer_addon.name,
            price=offer_addon.price,
            is_selected=False,
            quantity=initial_qty,
            pricing_model=offer_addon.pricing_model,
            category=offer_addon.category,
            duration_months=offer_addon.duration_months,
        )
        db.session.add(job_addon)

    # Apply initial selections / quantities from request
    if selected_addon_ids or addon_quantities:
        job_addons = JobAddon.query.filter_by(job_id=job.id).all()
        for ja in job_addons:
            if ja.pricing_model == 'per_unit':
                raw_qty = addon_quantities.get(str(ja.offer_addon_id))
                if raw_qty is None:
                    raw_qty = addon_quantities.get(ja.offer_addon_id)
                qty = int(raw_qty or 0)
                ja.quantity = max(0, qty)
                ja.is_selected = ja.quantity > 0
            else:
                ja.quantity = 1
                ja.is_selected = ja.offer_addon_id in selected_addon_ids

    # Przelicz finalną cenę
    job.update_final_price()

    # Optional voucher (scanned/typed)
    voucher_code = data.get("voucher_code")
    if voucher_code:
        from app.vouchers.services import apply_voucher_to_job

        apply_voucher_to_job(job, voucher_code)
    
    db.session.commit()
    return job


def get_job_by_id(job_id):
    """Pobiera zlecenie po ID."""
    job = db.session.get(Job, job_id)
    if not job:
        raise NotFound(f'Zlecenie #{job_id} nie istnieje')
    return job


def get_all_jobs(filters=None, page=1, per_page=50):
    """
    Pobiera wszystkie zlecenia z filtrami.
    
    Args:
        filters: dict (status, customer_id, offer_id)
        page: numer strony
        per_page: elementów na stronę
    
    Returns:
        dict: paginowane wyniki
    """
    query = Job.query
    
    if filters:
        if 'status' in filters:
            raw_status = filters['status']
            statuses = None
            if isinstance(raw_status, (list, tuple, set)):
                statuses = [str(s).strip() for s in raw_status if str(s).strip()]
            elif isinstance(raw_status, str):
                # Accept comma-separated list (frontend uses e.g. "confirmed,in_progress,completed")
                parts = [p.strip() for p in raw_status.split(',')]
                statuses = [p for p in parts if p]
            elif raw_status is not None:
                statuses = [str(raw_status).strip()]

            if statuses:
                if len(statuses) == 1:
                    query = query.filter_by(status=statuses[0])
                else:
                    query = query.filter(Job.status.in_(statuses))
        if 'customer_id' in filters:
            query = query.filter_by(customer_id=filters['customer_id'])
        if 'offer_id' in filters:
            query = query.filter_by(offer_id=filters['offer_id'])
        if 'date_from' in filters:
            df = _parse_iso_date(filters['date_from'])
            if df:
                query = query.filter((Job.event_date.isnot(None)) & (Job.event_date >= df))
        if 'date_to' in filters:
            dt_ = _parse_iso_date(filters['date_to'])
            if dt_:
                query = query.filter((Job.event_date.isnot(None)) & (Job.event_date <= dt_))
    
    query = query.order_by(Job.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    }


def update_job(job_id, data):
    """Aktualizuje zlecenie."""
    job = get_job_by_id(job_id)

    # Event start/end update with conflict checking
    if 'event_start' in data or 'event_date' in data:
        event_start = _parse_iso_datetime(data.get('event_start'))
        if not event_start:
            event_date = _parse_iso_date(data.get('event_date'))
            if event_date:
                event_start = datetime.combine(event_date, time.min)

        if event_start:
            offer = job.offer or db.session.get(Offer, job.offer_id)
            if not offer:
                raise BadRequest('Nieprawidłowa oferta')
            event_start, event_end = _calculate_reservation_window(offer, event_start)
            _assert_no_reservation_conflict(event_start, event_end, exclude_job_id=job.id)
            job.event_start = event_start
            job.event_end = event_end
            job.event_date = event_start.date()
    
    allowed_fields = [
        'title', 'description', 'event_date', 'event_start',
        'event_location', 'notes', 'internal_notes'
    ]
    
    for field in allowed_fields:
        if field in data:
            setattr(job, field, data[field])

    # Optional voucher apply (only if job doesn't have one yet)
    if "voucher_code" in data and data.get("voucher_code"):
        from app.vouchers.services import apply_voucher_to_job

        apply_voucher_to_job(job, data.get("voucher_code"))
    
    db.session.commit()
    return job


def get_calendar_reservations(range_start: datetime | None, range_end: datetime | None):
    """Returns jobs that reserve time in the given datetime range."""
    query = Job.query.filter(
        Job.status.notin_(["cancelled", "rejected"]),
        Job.event_start.isnot(None),
        Job.event_end.isnot(None),
    )

    if range_start:
        query = query.filter(Job.event_end > range_start)
    if range_end:
        query = query.filter(Job.event_start < range_end)

    return query.order_by(Job.event_start.asc()).all()


def update_job_status(job_id, new_status):
    """
    Aktualizuje status zlecenia z enforcement.
    
    Args:
        job_id: ID zlecenia
        new_status: nowy status
    
    Returns:
        Job: zaktualizowane zlecenie
        
    Raises:
        BadRequest: jeśli przejście jest niedozwolone
    """
    job = get_job_by_id(job_id)
    
    # Enforcement workflow
    enforce_job_workflow(job, new_status)
    
    # Aktualizuj status i daty
    job.status = new_status
    
    if new_status == 'quote_sent':
        job.quote_sent_at = datetime.utcnow()
    elif new_status == 'accepted':
        job.accepted_at = datetime.utcnow()
    elif new_status == 'completed':
        job.completed_at = datetime.utcnow()

        # Auto: when the job is completed, default final galleries to watermark off.
        # Safety: unpaid invoices still force watermark in public/photo endpoints.
        try:
            from app.galleries.models import Gallery

            (
                Gallery.query
                .filter(Gallery.job_id == job.id)
                .filter(Gallery.gallery_type == 'final')
                .update({'watermark_enabled': False}, synchronize_session=False)
            )
        except Exception:
            # If anything goes wrong, don't block status transition.
            pass
    
    db.session.commit()
    return job


def toggle_job_addon(job_id, addon_id, is_selected):
    """
    Przełącza wybór dodatku dla zlecenia.
    
    Args:
        job_id: ID zlecenia
        addon_id: ID JobAddon
        is_selected: True/False
    
    Returns:
        Job: zlecenie z zaktualizowaną ceną
    """
    job = get_job_by_id(job_id)
    
    # Znajdź addon
    addon = JobAddon.query.filter_by(id=addon_id, job_id=job_id).first()
    if not addon:
        raise NotFound(f'Dodatek #{addon_id} nie istnieje dla zlecenia #{job_id}')
    
    addon.is_selected = is_selected
    
    # Przelicz finalną cenę
    job.update_final_price()
    
    db.session.commit()
    return job


def delete_job(job_id):
    """
    Usuwa zlecenie (zmienia status na cancelled).
    
    Args:
        job_id: ID zlecenia
    
    Returns:
        Job: zlecenie
    """
    job = get_job_by_id(job_id)
    
    if job.status in ['completed', 'cancelled']:
        raise BadRequest('Nie można usunąć zakończonego lub anulowanego zlecenia')
    
    job.status = 'cancelled'
    db.session.commit()
    return job


# Offers management (seed data)

def create_offer(data):
    """Tworzy nową ofertę."""
    offer = Offer(**data)
    db.session.add(offer)
    db.session.commit()
    return offer


def get_all_offers(active_only=True):
    """Pobiera wszystkie oferty."""
    query = Offer.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Offer.display_order).all()


def create_offer_addon(data):
    """Tworzy dodatek do oferty."""
    addon = OfferAddon(**data)
    db.session.add(addon)
    db.session.commit()
    return addon


def get_offer_by_id(offer_id: int) -> Offer:
    offer = db.session.get(Offer, offer_id)
    if not offer:
        raise NotFound(f'Oferta #{offer_id} nie istnieje')
    return offer


def update_offer(offer_id: int, data: dict) -> Offer:
    offer = get_offer_by_id(offer_id)

    for field in [
        'name',
        'description',
        'base_price',
        'hours_included',
        'photos_count',
        'video_included',
        'is_active',
        'display_order',
    ]:
        if field in data:
            setattr(offer, field, data.get(field))

    db.session.commit()
    return offer


def deactivate_offer(offer_id: int) -> Offer:
    offer = get_offer_by_id(offer_id)
    offer.is_active = False
    db.session.commit()
    return offer


def get_offer_addon_by_id(addon_id: int) -> OfferAddon:
    addon = db.session.get(OfferAddon, addon_id)
    if not addon:
        raise NotFound(f'Dodatek #{addon_id} nie istnieje')
    return addon


def update_offer_addon(addon_id: int, data: dict) -> OfferAddon:
    addon = get_offer_addon_by_id(addon_id)

    if 'offer_id' in data:
        new_offer = db.session.get(Offer, data.get('offer_id'))
        if not new_offer:
            raise BadRequest('Nieprawidłowa oferta')
        addon.offer_id = data.get('offer_id')

    for field in [
        'name',
        'description',
        'price',
        'pricing_model',
        'category',
        'duration_months',
        'is_available',
        'display_order',
    ]:
        if field in data:
            setattr(addon, field, data.get(field))

    db.session.commit()
    return addon


def deactivate_offer_addon(addon_id: int) -> OfferAddon:
    addon = get_offer_addon_by_id(addon_id)
    addon.is_available = False
    db.session.commit()
    return addon

"""
Finance business logic.
Handles financial reports and statistics.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, extract
from app.extensions import db
from app.customers.models import Customer
from app.invoices.models import Invoice
from app.payments.models import Payment
from app.jobs.models import Job


def get_outstanding_invoices():
    return (
        Invoice.query.filter(Invoice.status.in_(['issued', 'partially_paid', 'overdue']))
        .order_by(Invoice.due_date.asc())
        .all()
    )


def get_overdue_invoices():
    today = datetime.utcnow().date()
    return (
        Invoice.query.filter(Invoice.status != 'cancelled')
        .filter(Invoice.paid_amount < Invoice.total_amount)
        .filter(Invoice.due_date < today)
        .order_by(Invoice.due_date.asc())
        .all()
    )


def get_revenue_by_offer(date_from=None, date_to=None):
    # Minimal implementation (endpoint exists); can be expanded later.
    query = (
        db.session.query(
            Job.offer_id.label('offer_id'),
            func.count(Job.id).label('job_count'),
            func.coalesce(func.sum(Job.final_price), 0).label('total_value'),
        )
        .filter(Job.status == 'completed')
    )

    if date_from:
        query = query.filter(Job.completed_at >= date_from)
    if date_to:
        query = query.filter(Job.completed_at <= date_to)

    rows = query.group_by(Job.offer_id).order_by(func.coalesce(func.sum(Job.final_price), 0).desc()).all()
    return [
        {
            'offer_id': int(r.offer_id) if r.offer_id is not None else None,
            'job_count': int(r.job_count or 0),
            'total_value': float(r.total_value or 0),
        }
        for r in rows
    ]


def get_top_customers(limit: int = 10):
    limit = max(1, min(int(limit or 10), 100))

    rows = (
        db.session.query(
            Customer.id.label('id'),
            Customer.first_name,
            Customer.last_name,
            Customer.company_name,
            Customer.customer_type,
            func.count(func.distinct(Job.id)).label('job_count'),
            func.coalesce(func.sum(Invoice.total_amount), 0).label('total_value'),
        )
        .join(Job, Job.customer_id == Customer.id)
        .join(Invoice, Invoice.job_id == Job.id)
        .filter(Invoice.status != 'cancelled')
        .group_by(Customer.id)
        .order_by(func.coalesce(func.sum(Invoice.total_amount), 0).desc())
        .limit(limit)
        .all()
    )

    def _display_name(row):
        if row.customer_type == 'company' and row.company_name:
            parts = [p for p in [row.first_name, row.last_name] if p]
            return f"{row.company_name} ({' '.join(parts)})" if parts else row.company_name
        parts = [p for p in [row.first_name, row.last_name] if p]
        return ' '.join(parts) if parts else ''

    return [
        {
            'id': int(r.id),
            'display_name': _display_name(r),
            'job_count': int(r.job_count or 0),
            'total_value': float(r.total_value or 0),
        }
        for r in rows
    ]


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    # Simple month arithmetic without external deps.
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def get_reports_stats():
    # Revenue (all-time): sum of issued invoices (net "revenue" in CRM sense).
    total_revenue = (
        db.session.query(func.coalesce(func.sum(Invoice.total_amount), 0))
        .filter(Invoice.status != 'cancelled')
        .scalar()
        or Decimal('0')
    )

    # Outstanding amount: total - paid for open invoices.
    outstanding = (
        db.session.query(func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0))
        .filter(Invoice.status.in_(['issued', 'partially_paid', 'overdue']))
        .scalar()
        or Decimal('0')
    )

    active_jobs = Job.query.filter(Job.status.in_(['accepted', 'in_progress'])).count()
    total_customers = Customer.query.filter(Customer.is_active.is_(True)).count()

    # Monthly summary: last 12 months including current.
    today = datetime.utcnow().date()
    start_month = _add_months(_month_start(today), -11)
    monthly_summary = []
    for i in range(12):
        m_start = _add_months(start_month, i)
        m_end = _add_months(m_start, 1)

        revenue = (
            db.session.query(func.coalesce(func.sum(Invoice.total_amount), 0))
            .filter(Invoice.status != 'cancelled')
            .filter(Invoice.issue_date >= m_start)
            .filter(Invoice.issue_date < m_end)
            .scalar()
            or Decimal('0')
        )

        paid = (
            db.session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.status == 'completed')
            .filter(Payment.payment_date >= datetime.combine(m_start, datetime.min.time()))
            .filter(Payment.payment_date < datetime.combine(m_end, datetime.min.time()))
            .scalar()
            or Decimal('0')
        )

        invoices_count = (
            Invoice.query.filter(Invoice.issue_date >= m_start)
            .filter(Invoice.issue_date < m_end)
            .filter(Invoice.status != 'cancelled')
            .count()
        )

        jobs_count = (
            Job.query.filter(Job.created_at >= datetime.combine(m_start, datetime.min.time()))
            .filter(Job.created_at < datetime.combine(m_end, datetime.min.time()))
            .filter(Job.status != 'cancelled')
            .count()
        )

        monthly_summary.append(
            {
                'month': f"{m_start.year:04d}-{m_start.month:02d}",
                'revenue': float(revenue or 0),
                'jobs': int(jobs_count or 0),
                'invoices': int(invoices_count or 0),
                'paid': float(paid or 0),
            }
        )

    return {
        'total_revenue': float(total_revenue or 0),
        'outstanding': float(outstanding or 0),
        'active_jobs': int(active_jobs or 0),
        'total_customers': int(total_customers or 0),
        'monthly_summary': monthly_summary,
        'top_customers': get_top_customers(10),
    }


def get_revenue_series(period: str):
    period = (period or 'month').strip().lower()
    now = datetime.utcnow()
    today = now.date()

    if period == 'week':
        start = today - timedelta(days=6)
        rows = (
            db.session.query(
                Invoice.issue_date.label('d'),
                func.coalesce(func.sum(Invoice.total_amount), 0).label('rev'),
            )
            .filter(Invoice.status != 'cancelled')
            .filter(Invoice.issue_date >= start)
            .filter(Invoice.issue_date <= today)
            .group_by(Invoice.issue_date)
            .order_by(Invoice.issue_date)
            .all()
        )
        by_day = {r.d: float(r.rev or 0) for r in rows}
        out = []
        for i in range(7):
            d = (start + timedelta(days=i))
            out.append({'label': d.isoformat(), 'revenue': by_day.get(d, 0.0)})
        return out

    if period == 'year':
        start_month = _add_months(_month_start(now.date()), -11)
        rows = (
            db.session.query(
                extract('year', Invoice.issue_date).label('y'),
                extract('month', Invoice.issue_date).label('m'),
                func.coalesce(func.sum(Invoice.total_amount), 0).label('rev'),
            )
            .filter(Invoice.status != 'cancelled')
            .filter(Invoice.issue_date >= start_month)
            .group_by('y', 'm')
            .order_by('y', 'm')
            .all()
        )
        by_month = {(int(r.y), int(r.m)): float(r.rev or 0) for r in rows}
        out = []
        for i in range(12):
            m = _add_months(start_month, i)
            out.append({'label': f"{m.year:04d}-{m.month:02d}", 'revenue': by_month.get((m.year, m.month), 0.0)})
        return out

    # Default: month = last 30 days
    start = today - timedelta(days=29)
    rows = (
        db.session.query(
            Invoice.issue_date.label('d'),
            func.coalesce(func.sum(Invoice.total_amount), 0).label('rev'),
        )
        .filter(Invoice.status != 'cancelled')
        .filter(Invoice.issue_date >= start)
        .filter(Invoice.issue_date <= today)
        .group_by(Invoice.issue_date)
        .order_by(Invoice.issue_date)
        .all()
    )
    by_day = {r.d: float(r.rev or 0) for r in rows}
    out = []
    for i in range(30):
        d = (start + timedelta(days=i))
        out.append({'label': d.isoformat(), 'revenue': by_day.get(d, 0.0)})
    return out


def get_revenue_summary(date_from=None, date_to=None):
    """
    Podsumowanie przychodów.
    
    Args:
        date_from: data od
        date_to: data do
    
    Returns:
        dict: podsumowanie finansowe
    """
    query = Invoice.query
    
    if date_from:
        query = query.filter(Invoice.issue_date >= date_from)
    if date_to:
        query = query.filter(Invoice.issue_date <= date_to)
    
    # Suma faktur
    total_invoiced = query.with_entities(
        func.sum(Invoice.total_amount)
    ).scalar() or Decimal('0')
    
    # Suma zapłacona
    total_paid = query.with_entities(
        func.sum(Invoice.paid_amount)
    ).scalar() or Decimal('0')
    
    # Liczba faktur
    invoice_count = query.count()
    
    # Faktury opłacone
    paid_count = query.filter(Invoice.status == 'paid').count()
    
    # Faktury przeterminowane
    overdue_count = query.filter(
        Invoice.status == 'overdue'
    ).count()
    
    return {
        'total_invoiced': float(total_invoiced),
        'total_paid': float(total_paid),
        'total_outstanding': float(total_invoiced - total_paid),
        'invoice_count': invoice_count,
        'paid_count': paid_count,
        'overdue_count': overdue_count
    }


def get_monthly_revenue(year=None):
    """
    Przychody miesięczne.
    
    Args:
        year: rok (domyślnie: bieżący)
    
    Returns:
        list: [{month, total_invoiced, total_paid}, ...]
    """
    if not year:
        year = datetime.utcnow().year
    
    results = db.session.query(
        extract('month', Invoice.issue_date).label('month'),
        func.sum(Invoice.total_amount).label('total_invoiced'),
        func.sum(Invoice.paid_amount).label('total_paid')
    ).filter(
        extract('year', Invoice.issue_date) == year
    ).group_by('month').order_by('month').all()
    
    monthly_data = []
    for row in results:
        monthly_data.append({
            'month': int(row.month),
            'total_invoiced': float(row.total_invoiced or 0),
            'total_paid': float(row.total_paid or 0)
        })
    
    return monthly_data


def get_payment_statistics(date_from=None, date_to=None):
    """
    Statystyki płatności.
    
    Args:
        date_from: data od
        date_to: data do
    
    Returns:
        dict: statystyki płatności
    """
    query = Payment.query
    
    if date_from:
        query = query.filter(Payment.payment_date >= date_from)
    if date_to:
        query = query.filter(Payment.payment_date <= date_to)
    
    # Suma płatności
    total = query.filter(
        Payment.status == 'completed'
    ).with_entities(
        func.sum(Payment.amount)
    ).scalar() or Decimal('0')
    
    # Rozkład według metody
    by_method = db.session.query(
        Payment.payment_method,
        func.sum(Payment.amount).label('total'),
        func.count(Payment.id).label('count')
    ).filter(
        Payment.status == 'completed'
    )
    
    if date_from:
        by_method = by_method.filter(Payment.payment_date >= date_from)
    if date_to:
        by_method = by_method.filter(Payment.payment_date <= date_to)
    
    by_method = by_method.group_by(Payment.payment_method).all()
    
    methods = []
    for row in by_method:
        methods.append({
            'method': row.payment_method,
            'total': float(row.total or 0),
            'count': row.count
        })
    
    return {
        'total_payments': float(total),
        'by_method': methods
    }


def get_job_statistics(date_from=None, date_to=None):
    """
    Statystyki zleceń.
    
    Args:
        date_from: data od
        date_to: data do
    
    Returns:
        dict: statystyki zleceń
    """
    query = Job.query
    
    if date_from:
        query = query.filter(Job.created_at >= date_from)
    if date_to:
        query = query.filter(Job.created_at <= date_to)
    
    # Rozkład według statusu
    by_status = db.session.query(
        Job.status,
        func.count(Job.id).label('count'),
        func.sum(Job.final_price).label('total_value')
    )
    
    if date_from:
        by_status = by_status.filter(Job.created_at >= date_from)
    if date_to:
        by_status = by_status.filter(Job.created_at <= date_to)
    
    by_status = by_status.group_by(Job.status).all()
    
    statuses = []
    for row in by_status:
        statuses.append({
            'status': row.status,
            'count': row.count,
            'total_value': float(row.total_value or 0)
        })
    
    # Konwersja
    completed = query.filter(Job.status == 'completed').count()
    accepted = query.filter(Job.status == 'accepted').count()
    total = query.count()
    
    conversion_rate = (accepted / total * 100) if total > 0 else 0
    completion_rate = (completed / accepted * 100) if accepted > 0 else 0
    
    return {
        'by_status': statuses,
        'total_jobs': total,
        'conversion_rate': round(conversion_rate, 2),
        'completion_rate': round(completion_rate, 2)
    }


def get_dashboard_stats():
    """
    Statystyki dla dashboardu.
    
    Returns:
        dict: kluczowe wskaźniki
    """
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    
    # Przychody tego miesiąca
    revenue_this_month = get_revenue_summary(date_from=month_start)
    
    # Aktywne zlecenia
    active_jobs = Job.query.filter(
        Job.status.in_(['accepted', 'in_progress'])
    ).count()
    
    # Oczekujące faktury
    pending_invoices = Invoice.query.filter(
        Invoice.status.in_(['issued', 'partially_paid'])
    ).count()
    
    # Przeterminowane faktury
    overdue_invoices = Invoice.query.filter(
        Invoice.status == 'overdue'
    ).count()
    
    return {
        'revenue_this_month': revenue_this_month,
        'active_jobs': active_jobs,
        'pending_invoices': pending_invoices,
        'overdue_invoices': overdue_invoices
    }

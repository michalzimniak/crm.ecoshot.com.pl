from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import and_, or_, func

from app.extensions import db
from app.jobs.models import Job, ReminderLog
from app.invoices.models import Invoice
from app.notifications.email import send_email


def _format_time(dt: datetime | None) -> str:
    if not dt:
        return "?"
    try:
        return dt.strftime("%H:%M")
    except Exception:
        return "?"


def send_tomorrow_schedule_email(now: datetime | None = None) -> int:
    """Send an internal email with jobs scheduled for tomorrow."""

    from flask import current_app

    if now is None:
        now = datetime.utcnow()

    if not current_app.config.get("REMINDERS_ENABLED", True):
        current_app.logger.info("Schedule reminder skipped (REMINDERS_ENABLED=false)")
        return 0

    target = (now.date() + timedelta(days=1))

    q = Job.query.filter(Job.status.in_(["accepted", "in_progress"]))
    q = q.filter(
        or_(
            Job.event_date == target,
            func.date(Job.event_start) == target,
        )
    )
    q = q.order_by(Job.event_start.asc().nullslast(), Job.event_date.asc().nullslast(), Job.id.asc())

    jobs = q.all()

    to_email = current_app.config.get("REMINDERS_SCHEDULE_TO")
    if not to_email:
        current_app.logger.warning("Schedule reminder skipped (REMINDERS_SCHEDULE_TO not set)")
        return 0

    subject = f"Plan na jutro ({target.isoformat()}) – {len(jobs)} zleceń"

    if not jobs:
        body = f"Brak zaplanowanych zleceń na jutro ({target.isoformat()}).\n"
    else:
        lines: list[str] = [
            f"Plan na jutro ({target.isoformat()}):",
            "",
        ]
        for job in jobs:
            customer_name = (job.customer.display_name if job.customer else "")
            if job.event_start or job.event_end:
                hours = f"{_format_time(job.event_start)}–{_format_time(job.event_end)}"
            else:
                hours = "(brak godzin)"

            location = (job.event_location or "").strip()
            location_part = f" | {location}" if location else ""
            customer_part = f" | {customer_name}" if customer_name else ""
            lines.append(f"- {hours} | #{job.id} {job.title}{customer_part}{location_part}")

        body = "\n".join(lines) + "\n"

    sent = send_email(to_email=to_email, subject=subject, body_text=body)
    return 1 if sent else 0


def send_unpaid_invoice_reminders(now: datetime | None = None, *, days_after_due: int = 7) -> int:
    """Send customer reminders for unpaid invoices N days after due_date.

    Idempotent via ReminderLog(kind='unpaid_7d', entity_type='invoice', entity_id=invoice.id).
    """

    from flask import current_app

    if now is None:
        now = datetime.utcnow()

    if not current_app.config.get("REMINDERS_ENABLED", True):
        current_app.logger.info("Unpaid reminders skipped (REMINDERS_ENABLED=false)")
        return 0

    cutoff = now.date() - timedelta(days=days_after_due)

    q = (
        Invoice.query.join(Job, Invoice.job_id == Job.id)
        .filter(Invoice.due_date <= cutoff)
        .filter(Invoice.status.in_(["issued", "overdue", "partially_paid"]))
        .filter(Invoice.paid_amount < Invoice.total_amount)
        .filter(Job.status.notin_(["cancelled", "rejected"]))
        .order_by(Invoice.due_date.asc(), Invoice.id.asc())
    )

    sent_count = 0

    for invoice in q.all():
        already = ReminderLog.query.filter_by(
            kind=f"unpaid_{days_after_due}d",
            entity_type="invoice",
            entity_id=invoice.id,
        ).first()
        if already:
            continue

        job = invoice.job
        customer = job.customer if job else None
        to_email = (customer.email if customer else None) or invoice.buyer_email
        if not to_email:
            continue

        remaining = float(invoice.total_amount) - float(invoice.paid_amount)
        subject = f"Przypomnienie o płatności – {invoice.invoice_number}"

        job_title = job.title if job else "(zlecenie)"
        due = invoice.due_date.isoformat() if invoice.due_date else ""
        body = (
            f"Dzień dobry,\n\n"
            f"To przypomnienie o płatności za zlecenie: {job_title}.\n"
            f"Faktura: {invoice.invoice_number}\n"
            f"Termin płatności: {due}\n"
            f"Do zapłaty pozostało: {remaining:.2f} PLN\n\n"
            f"W razie pytań prosimy o kontakt.\n"
        )

        if send_email(to_email=to_email, subject=subject, body_text=body):
            db.session.add(
                ReminderLog(
                    kind=f"unpaid_{days_after_due}d",
                    entity_type="invoice",
                    entity_id=invoice.id,
                    job_id=job.id if job else None,
                    to_email=to_email,
                    meta={"invoice_number": invoice.invoice_number, "due_date": due},
                )
            )
            db.session.commit()
            sent_count += 1

    return sent_count


def cancel_unpaid_jobs(now: datetime | None = None, *, days_after_due: int = 31, notify_customer: bool = True) -> int:
    """Cancel jobs that are still unpaid N days after invoice due_date.

    Idempotent via ReminderLog(kind='cancel_unpaid_31d', entity_type='invoice', entity_id=invoice.id).
    """

    from flask import current_app

    if now is None:
        now = datetime.utcnow()

    cutoff = now.date() - timedelta(days=days_after_due)

    q = (
        Invoice.query.join(Job, Invoice.job_id == Job.id)
        .filter(Invoice.due_date <= cutoff)
        .filter(Invoice.status.in_(["issued", "overdue", "partially_paid"]))
        .filter(Invoice.paid_amount < Invoice.total_amount)
        .filter(Job.status.in_(["draft", "quote_sent", "accepted", "in_progress"]))
        .order_by(Invoice.due_date.asc(), Invoice.id.asc())
    )

    cancelled = 0

    for invoice in q.all():
        already = ReminderLog.query.filter_by(
            kind=f"cancel_unpaid_{days_after_due}d",
            entity_type="invoice",
            entity_id=invoice.id,
        ).first()
        if already:
            continue

        job = invoice.job
        if not job:
            continue

        # Cancel
        job.status = "cancelled"
        job.internal_notes = (job.internal_notes or "").rstrip() + (
            "\n" if (job.internal_notes or "").strip() else ""
        ) + f"Auto-cancel: brak płatności {days_after_due} dni po terminie (invoice {invoice.invoice_number})."

        # Optionally cancel invoice too (keeps state consistent)
        invoice.status = "cancelled"

        to_email = None
        if notify_customer:
            customer = job.customer
            to_email = (customer.email if customer else None) or invoice.buyer_email

        db.session.add(
            ReminderLog(
                kind=f"cancel_unpaid_{days_after_due}d",
                entity_type="invoice",
                entity_id=invoice.id,
                job_id=job.id,
                to_email=to_email,
                meta={"invoice_number": invoice.invoice_number, "due_date": invoice.due_date.isoformat() if invoice.due_date else None},
            )
        )
        db.session.commit()
        cancelled += 1

        if notify_customer and to_email:
            subject = f"Anulowanie zlecenia – brak płatności ({invoice.invoice_number})"
            body = (
                f"Dzień dobry,\n\n"
                f"Ze względu na brak płatności za fakturę {invoice.invoice_number} "
                f"(termin: {invoice.due_date.isoformat() if invoice.due_date else ''}) "
                f"zlecenie \"{job.title}\" zostało anulowane.\n\n"
                f"Jeśli to pomyłka lub chcesz wrócić do realizacji, skontaktuj się z nami.\n"
            )
            send_email(to_email=to_email, subject=subject, body_text=body)

    return cancelled

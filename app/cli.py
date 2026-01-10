"""CLI commands for maintenance tasks."""

import click


def register_cli(app):
    @app.cli.command('expire-galleries')
    def expire_galleries_command():
        """Archive published galleries that are past expires_at."""
        from app.galleries.services import expire_published_galleries

        count = expire_published_galleries()
        click.echo(f'Archived {count} expired galleries')

    @app.cli.command('seed-offers')
    def seed_offers_command():
        """Seed default offers/add-ons into the database (idempotent)."""
        from app.jobs.seed import seed_offers_ecoshot

        offers, addons = seed_offers_ecoshot()
        click.echo(f'Seeded +{offers} offers, +{addons} add-ons')

    @app.cli.command('create-full-backup')
    def create_full_backup_command():
        """Create a persisted full backup (DB + uploads) on disk."""
        from app.settings.maintenance import create_persisted_full_backup

        info = create_persisted_full_backup(kind='manual')
        click.echo(f"Created full backup: {info.get('name')} ({info.get('size')} bytes)")

    @app.cli.command('daily-full-backup')
    def daily_full_backup_command():
        """Run daily auto full backup (creates at most one per UTC day, keeps 3 newest)."""
        from app.settings.maintenance import ensure_daily_auto_full_backup

        res = ensure_daily_auto_full_backup()
        if res.get('created'):
            info = (res.get('backup') or {})
            click.echo(f"Created daily full backup: {info.get('name')} ({info.get('size')} bytes)")
        else:
            click.echo(f"Skipped daily full backup: {res.get('reason', 'unknown')}")

    @app.cli.command('remind-schedule-tomorrow')
    def remind_schedule_tomorrow_command():
        """Send internal schedule email for tomorrow's jobs."""
        from app.jobs.reminders import send_tomorrow_schedule_email

        sent = send_tomorrow_schedule_email()
        click.echo(f"Schedule reminder sent={sent}")

    @app.cli.command('remind-unpaid')
    @click.option('--days-after-due', type=int, default=7, show_default=True)
    def remind_unpaid_command(days_after_due: int):
        """Send unpaid invoice reminders to customers."""
        from app.jobs.reminders import send_unpaid_invoice_reminders

        count = send_unpaid_invoice_reminders(days_after_due=days_after_due)
        click.echo(f"Sent {count} unpaid reminders (days_after_due={days_after_due})")

    @app.cli.command('cancel-unpaid')
    @click.option('--days-after-due', type=int, default=31, show_default=True)
    @click.option('--notify/--no-notify', default=True, show_default=True)
    def cancel_unpaid_command(days_after_due: int, notify: bool):
        """Auto-cancel unpaid jobs after N days past invoice due_date."""
        from app.jobs.reminders import cancel_unpaid_jobs

        count = cancel_unpaid_jobs(days_after_due=days_after_due, notify_customer=notify)
        click.echo(f"Cancelled {count} unpaid jobs (days_after_due={days_after_due}, notify={notify})")

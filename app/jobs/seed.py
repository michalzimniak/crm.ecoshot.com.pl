"""Seed data for photography offers and add-ons.

This module intentionally uses an upsert strategy so it can be run multiple times
without creating duplicates.

Currently seeds:
- SESJE RODZINNE (LIFESTYLE): BASIC / STANDARD / PREMIUM
- MINI SESJE TEMATYCZNE
- SESJE BIZNESOWE: LinkedIn + Personal Branding
- Common add-ons: dodatkowe zdjęcie, album premium, ekspresowa realizacja
"""

from app.extensions import db
from app.jobs.models import Offer, OfferAddon


def _upsert_offer(*, name, base_price, description=None, hours_included=None, photos_count=None, display_order=0, is_active=True):
    offer = Offer.query.filter_by(name=name).first()
    if not offer:
        offer = Offer(name=name, base_price=base_price)
        db.session.add(offer)

    offer.base_price = base_price
    offer.description = description
    offer.hours_included = hours_included
    offer.photos_count = photos_count
    offer.is_active = is_active
    offer.display_order = display_order
    return offer


def _upsert_addon(
    *,
    offer_id,
    name,
    price,
    description=None,
    pricing_model='fixed',
    category='addon',
    duration_months=None,
    display_order=0,
    is_available=True,
):
    addon = OfferAddon.query.filter_by(offer_id=offer_id, name=name).first()
    if not addon:
        addon = OfferAddon(offer_id=offer_id, name=name, price=price)
        db.session.add(addon)

    addon.price = price
    addon.description = description
    addon.pricing_model = pricing_model
    addon.category = category
    addon.duration_months = duration_months
    addon.display_order = display_order
    addon.is_available = is_available
    return addon


def seed_offers_ecoshot():
    """Seed packages and add-ons used by the New Job form."""

    offers_to_seed = [
        {
            'name': 'Sesje rodzinne (Lifestyle) – Pakiet BASIC',
            'base_price': 800.00,
            'hours_included': 1,
            'photos_count': 15,
            'display_order': 10,
            'description': (
                'Cena: 800 zł\n'
                '• 45–60 minut sesji (plener lub dom)\n'
                '• 15 zdjęć po autorskiej obróbce\n'
                '• galeria online'
            ),
        },
        {
            'name': 'Sesje rodzinne (Lifestyle) – Pakiet STANDARD',
            'base_price': 950.00,
            'hours_included': 2,
            'photos_count': 20,
            'display_order': 11,
            'description': (
                'Cena: 950–1000 zł\n'
                '• 60–90 minut sesji\n'
                '• 20 zdjęć po autorskiej obróbce\n'
                '• pomoc w doborze stylizacji\n'
                '• galeria online'
            ),
        },
        {
            'name': 'Sesje rodzinne (Lifestyle) – Pakiet PREMIUM',
            'base_price': 1200.00,
            'hours_included': 2,
            'photos_count': 30,
            'display_order': 12,
            'description': (
                'Cena: 1200–1400 zł\n'
                '• do 2 godzin sesji\n'
                '• 30 zdjęć po autorskiej obróbce\n'
                '• album lub odbitki'
            ),
        },
        {
            'name': 'Mini sesje tematyczne',
            'base_price': 450.00,
            'hours_included': 1,
            'photos_count': 7,
            'display_order': 20,
            'description': (
                'Cena: 450–600 zł\n'
                '• 25–30 minut\n'
                '• 5–7 zdjęć\n'
                '• sesje sezonowe'
            ),
        },
        {
            'name': 'Sesja biznesowa / LinkedIn',
            'base_price': 800.00,
            'hours_included': 1,
            'photos_count': 10,
            'display_order': 30,
            'description': (
                'Cena: 800–900 zł\n'
                '• ok. 60 minut\n'
                '• 10 zdjęć po obróbce\n'
                '• prawa do wykorzystania komercyjnego'
            ),
        },
        {
            'name': 'Sesja Personal Branding',
            'base_price': 1500.00,
            'hours_included': 2,
            'photos_count': 20,
            'display_order': 31,
            'description': (
                'Cena: 1500–1600 zł\n'
                '• przygotowanie koncepcji\n'
                '• 2 stylizacje\n'
                '• 20 zdjęć'
            ),
        },
    ]

    common_addons = [
        {
            'name': 'Dodatkowe zdjęcie',
            'price': 40.00,
            'display_order': 1,
            'description': 'Dodatkowe zdjęcie (40 zł / szt.)',
            'pricing_model': 'per_unit',
            'category': 'addon',
        },
        {
            'name': 'Album premium',
            'price': 300.00,
            'display_order': 2,
            'description': 'Album premium (od 300 zł)',
            'pricing_model': 'fixed',
            'category': 'addon',
        },
        {
            'name': 'Ekspresowa realizacja',
            'price': 150.00,
            'display_order': 3,
            'description': 'Ekspresowa realizacja',
            'pricing_model': 'fixed',
            'category': 'addon',
        },
    ]

    created_offers = 0
    created_addons = 0

    for spec in offers_to_seed:
        existed = Offer.query.filter_by(name=spec['name']).first() is not None
        offer = _upsert_offer(**spec)
        db.session.flush()
        if not existed:
            created_offers += 1

        for addon_spec in common_addons:
            addon_existed = OfferAddon.query.filter_by(offer_id=offer.id, name=addon_spec['name']).first() is not None
            _upsert_addon(offer_id=offer.id, **addon_spec)
            if not addon_existed:
                created_addons += 1

    db.session.commit()
    return created_offers, created_addons


if __name__ == '__main__':
    from app.app import create_app

    app = create_app()

    with app.app_context():
        offers, addons = seed_offers_ecoshot()
        print(f"✅ Seed completed: +{offers} offers, +{addons} add-ons")

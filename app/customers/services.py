"""
Customers business logic.
Handles CRUD operations for customers with validation.
"""

from werkzeug.exceptions import BadRequest, Conflict, NotFound
from app.extensions import db
from app.customers.models import Customer


def create_customer(data):
    """
    Tworzy nowego klienta.
    
    Args:
        data: dict z danymi klienta
    
    Returns:
        Customer: nowy klient
        
    Raises:
        Conflict: jeśli email lub NIP już istnieje
        BadRequest: jeśli dane są nieprawidłowe
    """
    # Sprawdź email
    if Customer.query.filter_by(email=data['email']).first():
        raise Conflict('Email już istnieje')
    
    # Sprawdź NIP jeśli firma
    if data.get('nip'):
        existing = Customer.query.filter_by(nip=data['nip']).first()
        if existing:
            raise Conflict('NIP już istnieje w systemie')
    
    # Walidacja pól wymaganych dla firmy
    if data.get('customer_type') == 'company':
        if not data.get('nip'):
            raise BadRequest('NIP jest wymagany dla firm')
        if not data.get('company_name'):
            raise BadRequest('Nazwa firmy jest wymagana')
    
    # Utwórz klienta
    customer = Customer(**data)
    
    db.session.add(customer)
    db.session.commit()
    
    return customer


def get_customer_by_id(customer_id):
    """
    Pobiera klienta po ID.
    
    Args:
        customer_id: ID klienta
    
    Returns:
        Customer: klient
        
    Raises:
        NotFound: jeśli klient nie istnieje
    """
    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise NotFound(f'Klient #{customer_id} nie istnieje')
    return customer


def get_all_customers(filters=None, search=None, page=1, per_page=50):
    """
    Pobiera wszystkich klientów z opcjonalnymi filtrami.
    
    Args:
        filters: dict z filtrami (customer_type, is_active)
        search: wyszukiwanie po nazwie/email
        page: numer strony
        per_page: elementów na stronę
    
    Returns:
        dict: {
            'items': list[Customer],
            'total': int,
            'page': int,
            'per_page': int,
            'pages': int
        }
    """
    query = Customer.query
    
    # Filtry
    if filters:
        if 'customer_type' in filters:
            query = query.filter_by(customer_type=filters['customer_type'])
        if 'is_active' in filters:
            query = query.filter_by(is_active=filters['is_active'])
    
    # Wyszukiwanie
    if search:
        search_filter = f'%{search}%'
        query = query.filter(
            db.or_(
                Customer.first_name.ilike(search_filter),
                Customer.last_name.ilike(search_filter),
                Customer.email.ilike(search_filter),
                Customer.company_name.ilike(search_filter)
            )
        )
    
    # Sortowanie
    query = query.order_by(Customer.created_at.desc())
    
    # Paginacja
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return {
        'items': pagination.items,
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    }


def update_customer(customer_id, data):
    """
    Aktualizuje dane klienta.
    
    Args:
        customer_id: ID klienta
        data: dict z danymi do aktualizacji
    
    Returns:
        Customer: zaktualizowany klient
        
    Raises:
        NotFound: jeśli klient nie istnieje
        Conflict: jeśli email lub NIP już istnieje
    """
    customer = get_customer_by_id(customer_id)
    
    # Sprawdź email jeśli jest zmieniany
    if 'email' in data and data['email'] != customer.email:
        existing = Customer.query.filter_by(email=data['email']).first()
        if existing:
            raise Conflict('Email już istnieje')
    
    # Sprawdź NIP jeśli jest zmieniany
    if 'nip' in data and data['nip'] and data['nip'] != customer.nip:
        existing = Customer.query.filter_by(nip=data['nip']).first()
        if existing:
            raise Conflict('NIP już istnieje w systemie')
    
    # Aktualizuj pola
    allowed_fields = [
        'first_name', 'last_name', 'email', 'phone',
        'street', 'city', 'postal_code', 'country',
        'company_name', 'nip', 'regon', 'notes', 'is_active'
    ]
    
    for field in allowed_fields:
        if field in data:
            setattr(customer, field, data[field])
    
    db.session.commit()
    return customer


def delete_customer(customer_id):
    """
    Usuwa klienta (soft delete - ustawia is_active=False).
    
    Args:
        customer_id: ID klienta
    
    Returns:
        Customer: klient
        
    Raises:
        BadRequest: jeśli klient ma aktywne zlecenia
    """
    customer = get_customer_by_id(customer_id)
    
    # Sprawdź czy ma aktywne zlecenia
    active_jobs = customer.jobs.filter(
        db.and_(
            db.not_(db.or_(
                db.text("status = 'cancelled'"),
                db.text("status = 'completed'"),
                db.text("status = 'rejected'")
            ))
        )
    ).count()
    
    if active_jobs > 0:
        raise BadRequest(
            f'Nie można usunąć klienta z aktywnymi zleceniami ({active_jobs})'
        )
    
    customer.is_active = False
    db.session.commit()
    return customer


def search_customers_by_email(email):
    """
    Wyszukuje klientów po emailu.
    
    Args:
        email: email do wyszukania
    
    Returns:
        list[Customer]: lista klientów
    """
    return Customer.query.filter(Customer.email.ilike(f'%{email}%')).all()


def search_customers_by_nip(nip):
    """
    Wyszukuje klientów po NIP.
    
    Args:
        nip: NIP do wyszukania
    
    Returns:
        Customer or None: klient lub None
    """
    return Customer.query.filter_by(nip=nip).first()

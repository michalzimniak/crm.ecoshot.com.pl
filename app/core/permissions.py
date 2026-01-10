"""
Permission system for role-based access control.
Defines roles and their permissions.
"""

from enum import Enum
from functools import wraps
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from werkzeug.exceptions import Forbidden


class Role(Enum):
    """User roles in the system."""
    ADMIN = 'admin'           # Full access
    PHOTOGRAPHER = 'photographer'  # Can manage jobs, galleries, contracts
    ACCOUNTANT = 'accountant'      # Can manage invoices, payments
    VIEWER = 'viewer'              # Read-only access


class Permission(Enum):
    """Granular permissions."""
    # Customers
    VIEW_CUSTOMERS = 'view_customers'
    CREATE_CUSTOMER = 'create_customer'
    EDIT_CUSTOMER = 'edit_customer'
    DELETE_CUSTOMER = 'delete_customer'
    
    # Jobs
    VIEW_JOBS = 'view_jobs'
    CREATE_JOB = 'create_job'
    EDIT_JOB = 'edit_job'
    DELETE_JOB = 'delete_job'
    CHANGE_JOB_STATUS = 'change_job_status'
    
    # Contracts
    VIEW_CONTRACTS = 'view_contracts'
    CREATE_CONTRACT = 'create_contract'
    SIGN_CONTRACT = 'sign_contract'
    DELETE_CONTRACT = 'delete_contract'
    
    # Invoices
    VIEW_INVOICES = 'view_invoices'
    CREATE_INVOICE = 'create_invoice'
    EDIT_INVOICE = 'edit_invoice'
    DELETE_INVOICE = 'delete_invoice'
    
    # Payments
    VIEW_PAYMENTS = 'view_payments'
    CREATE_PAYMENT = 'create_payment'
    EDIT_PAYMENT = 'edit_payment'
    DELETE_PAYMENT = 'delete_payment'
    
    # Galleries
    VIEW_GALLERIES = 'view_galleries'
    CREATE_GALLERY = 'create_gallery'
    EDIT_GALLERY = 'edit_gallery'
    DELETE_GALLERY = 'delete_gallery'
    PUBLISH_GALLERY = 'publish_gallery'
    
    # Photos
    UPLOAD_PHOTO = 'upload_photo'
    EDIT_PHOTO = 'edit_photo'
    DELETE_PHOTO = 'delete_photo'
    
    # Consents
    VIEW_CONSENTS = 'view_consents'
    MANAGE_CONSENTS = 'manage_consents'
    
    # Finance
    VIEW_FINANCE = 'view_finance'
    MANAGE_FINANCE = 'manage_finance'
    
    # System
    MANAGE_USERS = 'manage_users'
    VIEW_SETTINGS = 'view_settings'
    MANAGE_SETTINGS = 'manage_settings'


# Role -> Permissions mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: [p for p in Permission],  # Admin ma wszystkie uprawnienia
    
    Role.PHOTOGRAPHER: [
        Permission.VIEW_CUSTOMERS,
        Permission.CREATE_CUSTOMER,
        Permission.EDIT_CUSTOMER,
        Permission.VIEW_JOBS,
        Permission.CREATE_JOB,
        Permission.EDIT_JOB,
        Permission.CHANGE_JOB_STATUS,
        Permission.VIEW_CONTRACTS,
        Permission.CREATE_CONTRACT,
        Permission.SIGN_CONTRACT,
        Permission.VIEW_INVOICES,
        Permission.VIEW_GALLERIES,
        Permission.CREATE_GALLERY,
        Permission.EDIT_GALLERY,
        Permission.PUBLISH_GALLERY,
        Permission.UPLOAD_PHOTO,
        Permission.EDIT_PHOTO,
        Permission.DELETE_PHOTO,
        Permission.VIEW_CONSENTS,
        Permission.MANAGE_CONSENTS,
    ],
    
    Role.ACCOUNTANT: [
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_JOBS,
        Permission.VIEW_CONTRACTS,
        Permission.VIEW_INVOICES,
        Permission.CREATE_INVOICE,
        Permission.EDIT_INVOICE,
        Permission.VIEW_PAYMENTS,
        Permission.CREATE_PAYMENT,
        Permission.EDIT_PAYMENT,
        Permission.VIEW_FINANCE,
        Permission.MANAGE_FINANCE,
    ],
    
    Role.VIEWER: [
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_JOBS,
        Permission.VIEW_CONTRACTS,
        Permission.VIEW_INVOICES,
        Permission.VIEW_PAYMENTS,
        Permission.VIEW_GALLERIES,
        Permission.VIEW_CONSENTS,
        Permission.VIEW_FINANCE,
    ]
}


def get_user_role(user_id):
    """
    Pobiera rolę użytkownika z bazy danych.
    
    Args:
        user_id: ID użytkownika
        
    Returns:
        Role: rola użytkownika
    """
    from app.auth.models import User
    from app.extensions import db
    
    user = db.session.get(User, user_id)
    if not user:
        return None
    
    return Role(user.role)


def has_permission(user_id, permission):
    """
    Sprawdza czy użytkownik ma dane uprawnienie.
    
    Args:
        user_id: ID użytkownika
        permission: Permission enum
        
    Returns:
        bool: True jeśli użytkownik ma uprawnienie
    """
    role = get_user_role(user_id)
    if not role:
        return False
    
    return permission in ROLE_PERMISSIONS.get(role, [])


def require_permission(permission):
    """
    Dekorator sprawdzający uprawnienia użytkownika.
    
    Args:
        permission: Permission enum wymagane do wykonania akcji
        
    Raises:
        Forbidden: jeśli użytkownik nie ma uprawnień
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            
            if not has_permission(user_id, permission):
                raise Forbidden(
                    f"Brak uprawnień: {permission.value}"
                )
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role):
    """
    Dekorator sprawdzający rolę użytkownika.
    
    Args:
        role: Role enum wymagana do wykonania akcji
        
    Raises:
        Forbidden: jeśli użytkownik nie ma odpowiedniej roli
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user_role = get_user_role(user_id)
            
            if user_role != role and user_role != Role.ADMIN:
                raise Forbidden(
                    f"Wymagana rola: {role.value}"
                )
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

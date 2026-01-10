"""
Custom decorators for API endpoints.
Combines JWT authentication, permissions, and business rule enforcement.
"""

from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import Forbidden, BadRequest, NotFound, Unauthorized

from app.core.permissions import require_permission, require_role, Permission, Role
from app.core.enforcement import EnforcementError


def handle_errors(f):
    """
    Globalny handler błędów dla endpointów API.
    Konwertuje wyjątki na odpowiedzi JSON.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except EnforcementError as e:
            return jsonify({
                'success': False,
                'error': e.message,
                'code': 'ENFORCEMENT_ERROR'
            }), e.code
        except Forbidden as e:
            return jsonify({
                'success': False,
                'error': str(e.description) if e.description else 'Brak uprawnień',
                'code': 'FORBIDDEN'
            }), 403
        except Unauthorized as e:
            return jsonify({
                'success': False,
                'error': str(e.description) if e.description else 'Unauthorized',
                'code': 'UNAUTHORIZED'
            }), 401
        except BadRequest as e:
            return jsonify({
                'success': False,
                'error': str(e.description) if e.description else 'Nieprawidłowe żądanie',
                'code': 'BAD_REQUEST'
            }), 400
        except NotFound as e:
            return jsonify({
                'success': False,
                'error': str(e.description) if e.description else 'Nie znaleziono zasobu',
                'code': 'NOT_FOUND'
            }), 404
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'code': 'VALIDATION_ERROR'
            }), 400
        except Exception as e:
            # W produkcji nie ujawniamy szczegółów błędów
            return jsonify({
                'success': False,
                'error': 'Wystąpił błąd serwera',
                'code': 'INTERNAL_ERROR',
                'details': str(e)  # TODO: Usunąć w produkcji
            }), 500
    return wrapper


def api_endpoint(permission=None, role=None):
    """
    Kombinowany dekorator dla endpointów API.
    Łączy JWT auth, obsługę błędów i opcjonalnie sprawdzanie uprawnień.
    
    Args:
        permission: Permission enum (opcjonalne)
        role: Role enum (opcjonalne)
        
    Usage:
        @api_endpoint(permission=Permission.VIEW_CUSTOMERS)
        def get_customers():
            pass
    """
    def decorator(f):
        # Kolejność dekoratorów jestważna!
        decorated = f
        
        # 1. Handle errors (najbardziej zewnętrzny)
        decorated = handle_errors(decorated)
        
        # 2. Permission check
        if permission:
            decorated = require_permission(permission)(decorated)
        
        # 3. Role check
        if role:
            decorated = require_role(role)(decorated)
        
        # 4. JWT required (najbardziej wewnętrzny)
        decorated = jwt_required()(decorated)
        
        return decorated
    return decorator


def public_endpoint(f):
    """
    Dekorator dla publicznych endpointów (bez wymagania JWT).
    Nadal obsługuje błędy.
    """
    return handle_errors(f)


def enforce_business_rule(rule_func):
    """
    Dekorator egzekwujący regułę biznesową przed wykonaniem endpointu.
    
    Args:
        rule_func: funkcja sprawdzająca regułę biznesową (z enforcement.py)
        
    Usage:
        @enforce_business_rule(can_publish_gallery)
        def publish_gallery(job_id):
            # rule_func(job_id) zostanie wywołane automatycznie
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Próbujemy znaleźć job_id w argumentach
            job_id = kwargs.get('job_id') or kwargs.get('id')
            
            if not job_id and args:
                # Jeśli nie ma w kwargs, sprawdź args
                job_id = args[0] if len(args) > 0 else None
            
            if job_id:
                # Wywołaj regułę biznesową
                rule_func(job_id)
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def admin_only(f):
    """Skrót dla endpointów dostępnych tylko dla adminów."""
    return api_endpoint(role=Role.ADMIN)(f)


def photographer_only(f):
    """Skrót dla endpointów dostępnych dla fotografów i adminów."""
    return api_endpoint(role=Role.PHOTOGRAPHER)(f)


def accountant_only(f):
    """Skrót dla endpointów dostępnych dla księgowych i adminów."""
    return api_endpoint(role=Role.ACCOUNTANT)(f)


def authenticated(f):
    """
    Prosty dekorator wymagający autentykacji JWT bez sprawdzania uprawnień.
    """
    return api_endpoint()(f)

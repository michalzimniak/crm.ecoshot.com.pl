"""
Authentication business logic.
Handles user registration, login, JWT tokens.
"""

from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.exceptions import Unauthorized, BadRequest, Conflict
from app.extensions import db
from app.auth.models import User


def register_user(data):
    """
    Rejestruje nowego użytkownika.
    
    Args:
        data: dict z danymi użytkownika (username, email, password, etc.)
    
    Returns:
        User: nowy użytkownik
        
    Raises:
        Conflict: jeśli username lub email już istnieje
    """
    # Sprawdź czy username istnieje
    if User.query.filter_by(username=data['username']).first():
        raise Conflict('Username już istnieje')
    
    # Sprawdź czy email istnieje
    if User.query.filter_by(email=data['email']).first():
        raise Conflict('Email już istnieje')
    
    # Utwórz użytkownika
    user = User(
        username=data['username'],
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        phone=data.get('phone'),
        role=data.get('role', 'viewer'),
        is_active=data.get('is_active', True)
    )
    
    # Ustaw hasło (hashowane)
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return user


def login_user(username, password):
    """
    Loguje użytkownika.
    
    Args:
        username: nazwa użytkownika
        password: hasło
    
    Returns:
        dict: {
            'user': User object,
            'access_token': JWT access token,
            'refresh_token': JWT refresh token
        }
        
    Raises:
        Unauthorized: jeśli dane logowania są nieprawidłowe
    """
    # Znajdź użytkownika
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        raise Unauthorized('Nieprawidłowy username lub hasło')
    
    if not user.is_active:
        raise Unauthorized('Konto jest nieaktywne')
    
    # Aktualizuj last_login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generuj tokeny
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return {
        'user': user,
        'access_token': access_token,
        'refresh_token': refresh_token
    }


def get_user_by_id(user_id):
    """
    Pobiera użytkownika po ID.
    
    Args:
        user_id: ID użytkownika
    
    Returns:
        User: użytkownik
        
    Raises:
        BadRequest: jeśli użytkownik nie istnieje
    """
    user = db.session.get(User, user_id)
    if not user:
        raise BadRequest(f'Użytkownik #{user_id} nie istnieje')
    return user


def get_all_users(filters=None):
    """
    Pobiera wszystkich użytkowników z opcjonalnymi filtrami.
    
    Args:
        filters: dict z filtrami (role, is_active)
    
    Returns:
        list[User]: lista użytkowników
    """
    query = User.query
    
    if filters:
        if 'role' in filters:
            query = query.filter_by(role=filters['role'])
        if 'is_active' in filters:
            query = query.filter_by(is_active=filters['is_active'])
    
    return query.order_by(User.created_at.desc()).all()


def update_user(user_id, data):
    """
    Aktualizuje dane użytkownika.
    
    Args:
        user_id: ID użytkownika
        data: dict z danymi do aktualizacji
    
    Returns:
        User: zaktualizowany użytkownik
        
    Raises:
        BadRequest: jeśli użytkownik nie istnieje
        Conflict: jeśli email lub username już istnieje
    """
    user = get_user_by_id(user_id)

    # Sprawdź username jeśli jest zmieniany
    if 'username' in data and data['username'] != user.username:
        existing = User.query.filter_by(username=data['username']).first()
        if existing:
            raise Conflict('Username już istnieje')
    
    # Sprawdź email jeśli jest zmieniany
    if 'email' in data and data['email'] != user.email:
        existing = User.query.filter_by(email=data['email']).first()
        if existing:
            raise Conflict('Email już istnieje')
    
    # Aktualizuj pola
    for field in ['username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active']:
        if field in data:
            setattr(user, field, data[field])
    
    db.session.commit()
    return user


def change_password(user_id, old_password, new_password):
    """
    Zmienia hasło użytkownika.
    
    Args:
        user_id: ID użytkownika
        old_password: stare hasło
        new_password: nowe hasło
    
    Returns:
        User: użytkownik
        
    Raises:
        Unauthorized: jeśli stare hasło jest nieprawidłowe
    """
    user = get_user_by_id(user_id)
    
    if not user.check_password(old_password):
        raise Unauthorized('Nieprawidłowe hasło')
    
    user.set_password(new_password)
    db.session.commit()
    
    return user


def delete_user(user_id):
    """
    Usuwa użytkownika (soft delete - ustawia is_active=False).
    
    Args:
        user_id: ID użytkownika
    
    Returns:
        User: użytkownik
    """
    user = get_user_by_id(user_id)
    user.is_active = False
    db.session.commit()
    return user

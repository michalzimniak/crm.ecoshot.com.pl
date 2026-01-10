"""Authentication REST API endpoints."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app.auth import services
from app.auth.schemas import (
    login_schema,
    user_schema,
    users_schema,
    user_create_schema,
    user_update_schema,
    change_password_schema,
)
from app.core.decorators import api_endpoint, public_endpoint
from app.core.permissions import Permission


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@public_endpoint
def login():
    """Authenticate user and return JWT tokens."""
    data = request.get_json() or {}

    errors = login_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    result = services.login_user(data['username'], data['password'])

    return jsonify({
        'success': True,
        'data': {
            'user': user_schema.dump(result['user']),
            'access_token': result['access_token'],
            'refresh_token': result['refresh_token'],
        },
        'message': 'Zalogowano'
    })


@auth_bp.route('/me', methods=['GET'])
@api_endpoint()
def me():
    """Return current authenticated user."""
    user_id = int(get_jwt_identity())
    user = services.get_user_by_id(user_id)

    return jsonify({
        'success': True,
        'data': user_schema.dump(user)
    })


@auth_bp.route('/change-password', methods=['POST'])
@api_endpoint()
def change_password():
    """Change password for current user."""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}

    errors = change_password_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    services.change_password(user_id, data['old_password'], data['new_password'])

    return jsonify({'success': True, 'message': 'Hasło zmienione'})


@auth_bp.route('/users', methods=['GET'])
@api_endpoint(permission=Permission.MANAGE_USERS)
def list_users():
    """List users (admin-only). Optional filters: role, is_active."""
    role = request.args.get('role')
    is_active_raw = request.args.get('is_active')

    filters = {}
    if role:
        filters['role'] = role
    if is_active_raw is not None and is_active_raw != '':
        # Accept: true/false/1/0
        filters['is_active'] = str(is_active_raw).lower() in ('true', '1', 'yes')

    users = services.get_all_users(filters=filters or None)

    return jsonify({
        'success': True,
        'data': users_schema.dump(users)
    })


@auth_bp.route('/users', methods=['POST'])
@api_endpoint(permission=Permission.MANAGE_USERS)
def create_user():
    """Create a new user (admin-only)."""
    data = request.get_json() or {}
    errors = user_create_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    user = services.register_user(data)

    return jsonify({
        'success': True,
        'data': user_schema.dump(user),
        'message': 'Użytkownik utworzony'
    }), 201


@auth_bp.route('/users/<int:user_id>', methods=['GET'])
@api_endpoint(permission=Permission.MANAGE_USERS)
def get_user(user_id):
    """Get a user by id (admin-only)."""
    user = services.get_user_by_id(user_id)
    return jsonify({'success': True, 'data': user_schema.dump(user)})


@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@api_endpoint(permission=Permission.MANAGE_USERS)
def update_user(user_id):
    """Update user fields (admin-only)."""
    data = request.get_json() or {}
    errors = user_update_schema.validate(data)
    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    current_user_id = int(get_jwt_identity())
    if current_user_id == int(user_id) and 'is_active' in data and data.get('is_active') is False:
        return jsonify({
            'success': False,
            'message': 'Nie możesz dezaktywować aktualnie zalogowanego użytkownika'
        }), 400

    user = services.update_user(user_id, data)

    return jsonify({
        'success': True,
        'data': user_schema.dump(user),
        'message': 'Użytkownik zaktualizowany'
    })


@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@api_endpoint(permission=Permission.MANAGE_USERS)
def deactivate_user(user_id):
    """Deactivate (soft delete) user (admin-only)."""
    current_user_id = int(get_jwt_identity())
    if current_user_id == int(user_id):
        return jsonify({
            'success': False,
            'message': 'Nie możesz dezaktywować aktualnie zalogowanego użytkownika'
        }), 400
    user = services.delete_user(user_id)
    return jsonify({
        'success': True,
        'data': user_schema.dump(user),
        'message': 'Użytkownik dezaktywowany'
    })

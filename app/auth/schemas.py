"""
Marshmallow schemas for authentication.
Handles validation and serialization for User model.
"""

from marshmallow import Schema, fields, validate, validates, ValidationError, post_load
from app.extensions import ma
from app.auth.models import User


class UserSchema(ma.SQLAlchemyAutoSchema):
    """Schema for User model."""
    
    class Meta:
        model = User
        load_instance = True
        exclude = ('password_hash',)  # Nigdy nie zwracamy hasha hasła
        dump_only = ('id', 'created_at', 'updated_at', 'last_login')
    
    # Custom fields
    full_name = fields.String(dump_only=True)
    
    # Validation
    username = fields.String(
        required=True,
        validate=validate.Length(min=3, max=80)
    )
    email = fields.Email(required=True)
    role = fields.String(
        required=True,
        validate=validate.OneOf(['admin', 'photographer', 'accountant', 'viewer'])
    )
    first_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100)
    )
    last_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100)
    )


class UserCreateSchema(Schema):
    """Schema for creating new user."""
    
    username = fields.String(
        required=True,
        validate=validate.Length(min=3, max=80)
    )
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128)
    )
    first_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100)
    )
    last_name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=100)
    )
    phone = fields.String(validate=validate.Length(max=20))
    role = fields.String(
        required=True,
        validate=validate.OneOf(['admin', 'photographer', 'accountant', 'viewer'])
    )
    
    @validates('password')
    def validate_password(self, value):
        """Walidacja siły hasła."""
        if len(value) < 8:
            raise ValidationError('Hasło musi mieć minimum 8 znaków')
        if not any(c.isupper() for c in value):
            raise ValidationError('Hasło musi zawierać wielką literę')
        if not any(c.islower() for c in value):
            raise ValidationError('Hasło musi zawierać małą literę')
        if not any(c.isdigit() for c in value):
            raise ValidationError('Hasło musi zawierać cyfrę')


class UserUpdateSchema(Schema):
    """Schema for updating user."""
    
    username = fields.String(validate=validate.Length(min=3, max=80))
    email = fields.Email()
    first_name = fields.String(validate=validate.Length(min=1, max=100))
    last_name = fields.String(validate=validate.Length(min=1, max=100))
    phone = fields.String(validate=validate.Length(max=20))
    role = fields.String(
        validate=validate.OneOf(['admin', 'photographer', 'accountant', 'viewer'])
    )
    is_active = fields.Boolean()


class LoginSchema(Schema):
    """Schema for login request."""
    
    username = fields.String(required=True)
    password = fields.String(required=True, load_only=True)


class ChangePasswordSchema(Schema):
    """Schema for password change."""
    
    old_password = fields.String(required=True, load_only=True)
    new_password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, max=128)
    )
    
    @validates('new_password')
    def validate_new_password(self, value):
        """Walidacja siły nowego hasła."""
        if len(value) < 8:
            raise ValidationError('Hasło musi mieć minimum 8 znaków')
        if not any(c.isupper() for c in value):
            raise ValidationError('Hasło musi zawierać wielką literę')
        if not any(c.islower() for c in value):
            raise ValidationError('Hasło musi zawierać małą literę')
        if not any(c.isdigit() for c in value):
            raise ValidationError('Hasło musi zawierać cyfrę')


# Schema instances
user_schema = UserSchema()
users_schema = UserSchema(many=True)
user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()
login_schema = LoginSchema()
change_password_schema = ChangePasswordSchema()

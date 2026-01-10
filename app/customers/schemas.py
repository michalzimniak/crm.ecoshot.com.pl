"""Marshmallow schemas for customers.
Handles validation and serialization for Customer model.
"""

import re

from marshmallow import EXCLUDE, Schema, ValidationError, fields, pre_load, validate, validates, validates_schema

from app.customers.models import Customer
from app.extensions import ma


def validate_nip(nip):
    """Walidacja numeru NIP."""
    if not nip:
        return

    nip_digits = re.sub(r'[^0-9]', '', nip)

    if len(nip_digits) != 10:
        raise ValidationError('NIP musi składać się z 10 cyfr')

    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    check_sum = sum(int(nip_digits[i]) * weights[i] for i in range(9))
    check_digit = check_sum % 11

    if check_digit == 10:
        check_digit = 0

    if check_digit != int(nip_digits[9]):
        raise ValidationError('Nieprawidłowy numer NIP (błędna suma kontrolna)')


def validate_phone(phone):
    """Walidacja numeru telefonu."""
    if not phone:
        return

    pattern = r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$'
    if not re.match(pattern, phone):
        raise ValidationError('Nieprawidłowy format numeru telefonu')


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Customer model."""

    class Meta:
        model = Customer
        load_instance = True
        dump_only = ('id', 'created_at', 'updated_at')

    full_name = fields.String(dump_only=True)
    display_name = fields.String(dump_only=True)

    customer_type = fields.String(required=True, validate=validate.OneOf(['person', 'company']))
    email = fields.Email(required=True)
    phone = fields.String(required=True)
    nip = fields.String(allow_none=True)

    @validates('nip')
    def validate_nip_field(self, value):
        validate_nip(value)

    @validates('phone')
    def validate_phone_field(self, value):
        validate_phone(value)


class CustomerCreateSchema(Schema):
    """Schema for creating new customer."""

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def normalize_address(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        # Backward-compatible alias: frontend used to send `address`.
        if data.get('street') is None and data.get('address') is not None:
            data = dict(data)
            data['street'] = data.get('address')
        return data

    customer_type = fields.String(required=True, validate=validate.OneOf(['person', 'company']))

    # Person
    first_name = fields.String(allow_none=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(allow_none=True, validate=validate.Length(min=1, max=100))

    # Contact
    email = fields.Email(required=True)
    phone = fields.String(required=True)

    # Address
    street = fields.String(allow_none=True, validate=validate.Length(max=200))
    city = fields.String(allow_none=True, validate=validate.Length(max=100))
    postal_code = fields.String(allow_none=True, validate=validate.Length(max=10))
    country = fields.String(allow_none=True, validate=validate.Length(max=100))

    # Company
    company_name = fields.String(allow_none=True, validate=validate.Length(max=200))
    nip = fields.String(allow_none=True)
    regon = fields.String(allow_none=True, validate=validate.Length(max=20))

    # Other
    notes = fields.String(allow_none=True)
    is_active = fields.Boolean(allow_none=True)

    @validates('nip')
    def validate_nip_field(self, value):
        validate_nip(value)

    @validates('phone')
    def validate_phone_field(self, value):
        validate_phone(value)

    @validates_schema
    def validate_required_fields_by_type(self, data, **kwargs):
        customer_type = data.get('customer_type')

        if customer_type == 'person':
            if not data.get('first_name'):
                raise ValidationError('Imię jest wymagane', 'first_name')
            if not data.get('last_name'):
                raise ValidationError('Nazwisko jest wymagane', 'last_name')

        if customer_type == 'company':
            if not data.get('nip'):
                raise ValidationError('NIP jest wymagany dla firm', 'nip')
            if not data.get('company_name'):
                raise ValidationError('Nazwa firmy jest wymagana', 'company_name')


class CustomerUpdateSchema(Schema):
    """Schema for updating customer."""

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def normalize_address(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        if data.get('street') is None and data.get('address') is not None:
            data = dict(data)
            data['street'] = data.get('address')
        return data

    first_name = fields.String(allow_none=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(allow_none=True, validate=validate.Length(min=1, max=100))
    email = fields.Email()
    phone = fields.String()

    street = fields.String(allow_none=True, validate=validate.Length(max=200))
    city = fields.String(allow_none=True, validate=validate.Length(max=100))
    postal_code = fields.String(allow_none=True, validate=validate.Length(max=10))
    country = fields.String(allow_none=True, validate=validate.Length(max=100))

    company_name = fields.String(allow_none=True, validate=validate.Length(max=200))
    nip = fields.String(allow_none=True)
    regon = fields.String(allow_none=True, validate=validate.Length(max=20))

    notes = fields.String(allow_none=True)
    is_active = fields.Boolean(allow_none=True)

    @validates('nip')
    def validate_nip_field(self, value):
        validate_nip(value)

    @validates('phone')
    def validate_phone_field(self, value):
        validate_phone(value)


customer_schema = CustomerSchema()
customers_schema = CustomerSchema(many=True)
customer_create_schema = CustomerCreateSchema()
customer_update_schema = CustomerUpdateSchema()

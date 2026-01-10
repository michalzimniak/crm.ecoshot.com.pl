"""
Marshmallow schemas for invoices.
Handles validation and serialization for Invoice model.
"""

from decimal import Decimal

from app.settings.services import get_setting
from marshmallow import EXCLUDE, Schema, fields, validate, validates_schema, ValidationError
from app.extensions import ma
from app.invoices.models import Invoice


class InvoiceItemSchema(Schema):
    """Schema for invoice item (JSON field)."""
    
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    quantity = fields.Decimal(required=True, as_string=True)
    unit_price = fields.Decimal(required=True, as_string=True)
    total = fields.Decimal(required=True, as_string=True)
    
    @validates_schema
    def validate_total(self, data, **kwargs):
        """Walidacja poprawności sumy."""
        quantity = float(data.get('quantity', 0))
        unit_price = float(data.get('unit_price', 0))
        total = float(data.get('total', 0))
        
        expected_total = quantity * unit_price
        if abs(expected_total - total) > 0.01:  # Tolerancja zaokrągleń
            raise ValidationError(
                f'Nieprawidłowa suma. Oczekiwano: {expected_total:.2f}',
                'total'
            )


class InvoiceSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Invoice model."""
    
    class Meta:
        model = Invoice
        load_instance = True
        dump_only = ('id', 'created_at', 'updated_at', 'payment_date')
    
    # Custom fields
    remaining_amount = fields.Decimal(dump_only=True, as_string=True)
    is_paid = fields.Boolean(dump_only=True)
    is_overdue = fields.Boolean(dump_only=True)

    # Aliases expected by the frontend
    payment_deadline = fields.Method("get_payment_deadline", dump_only=True)
    payment_status = fields.Method("get_payment_status", dump_only=True)

    original_invoice_number = fields.Method("get_original_invoice_number", dump_only=True)

    seller_name = fields.Method("get_seller_name", dump_only=True)
    seller_address = fields.Method("get_seller_address", dump_only=True)
    seller_nip = fields.Method("get_seller_nip", dump_only=True)

    customer_name = fields.String(attribute="buyer_name", dump_only=True)
    customer_address = fields.String(attribute="buyer_address", dump_only=True)
    customer_nip = fields.String(attribute="buyer_nip", dump_only=True)

    total_net = fields.Method("get_total_net", dump_only=True)
    total_vat = fields.Method("get_total_vat", dump_only=True)
    total_gross = fields.Method("get_total_gross", dump_only=True)
    
    # Nested
    job = fields.Nested('JobSchema', dump_only=True)
    payments = fields.Nested('PaymentSchema', many=True, dump_only=True)
    # Items normalized for UI (the DB stores {name, quantity, unit_price, total} in NET values)
    items = fields.Method("get_items", dump_only=True)
    
    # Validation
    status = fields.String(
        validate=validate.OneOf([
            'draft', 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled'
        ])
    )

    invoice_type = fields.String(
        validate=validate.OneOf(['standard', 'deposit', 'final', 'correction'])
    )
    payment_method = fields.String(
        validate=validate.OneOf(['transfer', 'cash', 'card', 'paypal', 'other'])
    )

    def get_payment_deadline(self, obj):
        return obj.due_date.isoformat() if getattr(obj, "due_date", None) else None

    def get_original_invoice_number(self, obj):
        original = getattr(obj, "original_invoice", None)
        if not original:
            return None
        return getattr(original, "invoice_number", None)

    def get_payment_status(self, obj):
        try:
            paid = float(getattr(obj, "paid_amount", 0) or 0)
            total = float(getattr(obj, "total_amount", 0) or 0)
        except Exception:
            paid, total = 0.0, 0.0

        if total <= 0:
            return "unpaid"
        if paid <= 0:
            return "unpaid"
        if paid + 1e-9 < total:
            return "partial"
        if paid - 1e-9 > total:
            return "overpaid"
        return "paid"

    def get_seller_name(self, obj):
        return get_setting("COMPANY_NAME")

    def get_seller_address(self, obj):
        return get_setting("COMPANY_ADDRESS")

    def get_seller_nip(self, obj):
        return get_setting("COMPANY_NIP")

    def get_total_net(self, obj):
        value = getattr(obj, "subtotal", None)
        if value is None:
            return None
        try:
            return str(Decimal(value))
        except Exception:
            return value

    def get_total_vat(self, obj):
        value = getattr(obj, "tax_amount", None)
        if value is None:
            return None
        try:
            return str(Decimal(value))
        except Exception:
            return value

    def get_total_gross(self, obj):
        value = getattr(obj, "total_amount", None)
        if value is None:
            return None
        try:
            return str(Decimal(value))
        except Exception:
            return value

    def get_items(self, obj):
        items = getattr(obj, "items", None) or []
        try:
            vat_rate = float(getattr(obj, "tax_rate", 0) or 0)
        except Exception:
            vat_rate = 0.0

        multiplier = 1.0 + (vat_rate / 100.0)
        out = []
        for it in items:
            try:
                qty = float(it.get("quantity") or 0)
            except Exception:
                qty = 0.0
            try:
                unit_net = float(it.get("unit_price") or 0)
            except Exception:
                unit_net = 0.0
            try:
                total_net = float(it.get("total") or (qty * unit_net))
            except Exception:
                total_net = qty * unit_net

            out.append(
                {
                    "description": it.get("name"),
                    "quantity": qty,
                    "unit_price_net": unit_net,
                    "vat_rate": vat_rate,
                    "total_gross": total_net * multiplier,
                }
            )

        return out



class InvoiceCreateSchema(Schema):
    """Schema for creating new invoice."""

    class Meta:
        unknown = EXCLUDE
    
    job_id = fields.Integer(required=True)

    # Optional: if provided and due_date is missing, API will compute it.
    payment_term_days = fields.Integer(
        load_only=True,
        validate=validate.Range(min=0, max=365),
    )
    
    issue_date = fields.Date()
    due_date = fields.Date()
    
    items = fields.List(
        fields.Nested(InvoiceItemSchema),
        validate=validate.Length(min=1)
    )
    
    tax_rate = fields.Decimal(as_string=True)
    payment_method = fields.String(
        validate=validate.OneOf(['transfer', 'cash', 'card', 'paypal', 'other'])
    )
    bank_account = fields.String(validate=validate.Length(max=50))
    
    notes = fields.String()
    internal_notes = fields.String()
    
    @validates_schema
    def validate_dates(self, data, **kwargs):
        """Walidacja dat."""
        issue_date = data.get('issue_date')
        due_date = data.get('due_date')
        
        if issue_date and due_date and due_date < issue_date:
            raise ValidationError(
                'Data płatności nie może być wcześniejsza niż data wystawienia',
                'due_date'
            )


class InvoiceUpdateSchema(Schema):
    """Schema for updating invoice."""

    class Meta:
        unknown = EXCLUDE
    
    due_date = fields.Date()
    items = fields.List(fields.Nested(InvoiceItemSchema))
    payment_method = fields.String(
        validate=validate.OneOf(['transfer', 'cash', 'card', 'paypal', 'other'])
    )
    notes = fields.String()
    internal_notes = fields.String()


class InvoiceStatusUpdateSchema(Schema):
    """Schema for updating invoice status."""
    
    status = fields.String(
        required=True,
        validate=validate.OneOf([
            'draft', 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled'
        ])
    )


# Schema instances
invoice_schema = InvoiceSchema()
invoices_schema = InvoiceSchema(many=True)
invoice_create_schema = InvoiceCreateSchema()
invoice_update_schema = InvoiceUpdateSchema()
invoice_status_update_schema = InvoiceStatusUpdateSchema()
invoice_item_schema = InvoiceItemSchema()

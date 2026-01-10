"""
Przykładowe testy jednostkowe dla modułu Customer
"""

import pytest
from app.app import create_app
from app.extensions import db
from app.customers.models import Customer


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_create_customer_person(app):
    """Test creating person customer."""
    with app.app_context():
        customer = Customer(
            customer_type='person',
            first_name='Jan',
            last_name='Kowalski',
            email='jan@example.com',
            phone='123456789'
        )
        db.session.add(customer)
        db.session.commit()
        
        assert customer.id is not None
        assert customer.display_name == 'Jan Kowalski'


def test_create_customer_company(app):
    """Test creating company customer."""
    with app.app_context():
        customer = Customer(
            customer_type='company',
            company_name='Test Sp. z o.o.',
            nip='1234567890',
            email='kontakt@test.pl',
            phone='987654321'
        )
        db.session.add(customer)
        db.session.commit()
        
        assert customer.id is not None
        assert customer.display_name == 'Test Sp. z o.o.'


def test_customer_api_list(client, app):
    """Test GET /api/customers endpoint."""
    # This test requires JWT authentication
    # For now, just test that endpoint exists
    response = client.get('/api/customers')
    
    # Should return 401 (unauthorized) without JWT
    assert response.status_code == 401


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

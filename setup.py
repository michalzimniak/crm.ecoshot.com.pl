#!/usr/bin/env python
"""
Setup script dla EcoShot CRM
Inicjalizuje bazę danych, tworzy pierwszego użytkownika i ładuje dane seed.
"""

import os
import sys
from getpass import getpass

from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env for local setup runs
load_dotenv()

from app.app import create_app
from app.extensions import db
from app.auth.models import User
from flask_migrate import upgrade as migrate_upgrade


def setup_database():
    """Initialize database and run migrations."""
    print("🔧 Inicjalizacja bazy danych...")
    
    app = create_app()
    with app.app_context():
        # Create tables (baseline) and then apply migrations for incremental schema changes.
        # Note: this project historically used create_all for initial schema creation.
        db.create_all()
        try:
            migrate_upgrade()
            print("✅ Migracje zastosowane")
        except Exception as e:
            # If migrations cannot be applied (e.g. missing alembic_version), keep going
            # but warn clearly.
            print(f"⚠️  Nie udało się zastosować migracji: {e}")
        print("✅ Tabele gotowe")
        
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print("⚠️  Użytkownik 'admin' już istnieje")
            return
        
        # Create admin user
        print("\n👤 Tworzenie użytkownika administratora")
        username = input("Username [admin]: ").strip() or 'admin'
        email = input("Email [admin@ecoshot.pl]: ").strip() or 'admin@ecoshot.pl'
        first_name = input("Imię [Admin]: ").strip() or 'Admin'
        last_name = input("Nazwisko [User]: ").strip() or 'User'
        phone = input("Telefon (opcjonalnie): ").strip() or None
        
        while True:
            password = getpass("Hasło: ")
            password_confirm = getpass("Potwierdź hasło: ")
            
            if password != password_confirm:
                print("❌ Hasła nie są identyczne. Spróbuj ponownie.")
                continue
            
            if len(password) < 6:
                print("❌ Hasło musi mieć co najmniej 6 znaków.")
                continue
            
            break
        
        admin = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role='admin',
            is_active=True
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"✅ Użytkownik '{username}' utworzony")


def load_seed_data():
    """Load seed data (photography offers)."""
    print("\n📦 Ładowanie danych seed...")
    
    try:
        from app.jobs import seed
        seed.seed_offers()
        print("✅ Dane seed załadowane")
    except Exception as e:
        print(f"⚠️  Błąd ładowania seed: {e}")


def main():
    """Main setup function."""
    print("=" * 60)
    print("🎨 EcoShot CRM - Setup")
    print("=" * 60)
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("\n⚠️  Brak pliku .env!")
        print("Skopiuj .env.example do .env i skonfiguruj:")
        print("  cp .env.example .env")
        print("\nNastępnie edytuj .env i ustaw:")
        print("  - DATABASE_URL (connection string)")
        print("  - SECRET_KEY (random string)")
        print("  - JWT_SECRET_KEY (random string)")
        sys.exit(1)
    
    try:
        setup_database()
        load_seed_data()
        
        print("\n" + "=" * 60)
        print("✅ Setup zakończony pomyślnie!")
        print("=" * 60)
        print("\n🚀 Uruchom aplikację:")
        print("  flask run --debug")
        print("\n🌐 Otwórz w przeglądarce:")
        print("  http://localhost:5000")
        print("\n👤 Zaloguj się używając utworzonych danych")
        
    except Exception as e:
        print(f"\n❌ Błąd podczas setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

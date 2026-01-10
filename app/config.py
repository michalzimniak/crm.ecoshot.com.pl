"""
Flask application configuration.
Production-ready settings for CRM system.
"""

import os
from datetime import timedelta


class Config:
    """Base configuration."""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:2work4fun!@localhost/crm_ecoshot_com_pl'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # File uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'zip'}
    
    # Photos & Galleries
    PHOTOS_FOLDER = os.path.join(UPLOAD_FOLDER, 'photos')
    CONTRACTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'contracts')
    CONSENTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'consents')
    GALLERIES_FOLDER = os.path.join(UPLOAD_FOLDER, 'galleries')
    WATERMARK_PATH = os.path.join('assets', 'watermark.png')
    
    # Invoice settings
    INVOICE_PREFIX = 'FV'
    INVOICE_DEPOSIT_PREFIX = 'FZV'
    INVOICE_CORRECTION_PREFIX = 'FKV'
    INVOICE_YEAR_FORMAT = '%Y'
    
    # Company data (for invoices & contracts)
    COMPANY_NAME = os.environ.get('COMPANY_NAME') or 'EcoShot Photography'
    COMPANY_ADDRESS = os.environ.get('COMPANY_ADDRESS') or 'ul. Przykładowa 1, 00-000 Warszawa'
    COMPANY_NIP = os.environ.get('COMPANY_NIP') or '1234567890'
    COMPANY_PHONE = os.environ.get('COMPANY_PHONE') or '+48 123 456 789'
    COMPANY_EMAIL = os.environ.get('COMPANY_EMAIL') or 'kontakt@ecoshot.com.pl'
    COMPANY_BANK = os.environ.get('COMPANY_BANK') or 'Bank Przykładowy'
    COMPANY_ACCOUNT = os.environ.get('COMPANY_ACCOUNT') or '12 3456 7890 1234 5678 9012 3456'
    
    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # Google Maps / Places
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
    GOOGLE_MAPS_BROWSER_API_KEY = os.environ.get('GOOGLE_MAPS_BROWSER_API_KEY')
    GOOGLE_MAPS_MAP_ID = os.environ.get('GOOGLE_MAPS_MAP_ID')

    # PayU
    PAYU_ENV = os.environ.get('PAYU_ENV', 'sandbox')  # sandbox|production
    PAYU_POS_ID = os.environ.get('PAYU_POS_ID')
    PAYU_CLIENT_ID = os.environ.get('PAYU_CLIENT_ID')
    PAYU_CLIENT_SECRET = os.environ.get('PAYU_CLIENT_SECRET')
    PAYU_SECOND_KEY = os.environ.get('PAYU_SECOND_KEY')
    PAYU_NOTIFY_URL = os.environ.get('PAYU_NOTIFY_URL')

    # SMTP / Email (reminders)
    SMTP_HOST = os.environ.get('SMTP_HOST')
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_USE_TLS = (os.environ.get('SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes', 'on'))
    SMTP_FROM = os.environ.get('SMTP_FROM') or COMPANY_EMAIL

    REMINDERS_ENABLED = (os.environ.get('REMINDERS_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on'))
    REMINDERS_SCHEDULE_TO = os.environ.get('REMINDERS_SCHEDULE_TO') or COMPANY_EMAIL


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    # In production, these MUST be set via environment variables
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    

# Config dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

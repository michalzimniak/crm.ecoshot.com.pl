"""
Flask application factory.
Creates and configures the Flask application.
"""

import os
from flask import Flask, jsonify, send_from_directory, redirect, abort
from app.config import config
from app.extensions import init_extensions, db, jwt


def create_app(config_name=None):
    """
    Application factory pattern.
    
    Args:
        config_name: 'development', 'production', 'testing'
    
    Returns:
        Flask app instance
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    frontend_dir = os.path.join(app.root_path, 'frontend')
    
    # Initialize extensions
    init_extensions(app)

    # CLI commands
    from app.cli import register_cli
    register_cli(app)

    # Ensure all models are imported before schemas/blueprints.
    # This prevents mapper resolution issues for relationship() targets.
    load_models()
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status': 'ok',
            'message': 'CRM EcoShot API is running'
        })
    
    # Frontend routes
    @app.route('/')
    def index():
        return send_from_directory(frontend_dir, 'index.html')

    # Public gallery URL: /g/<public_hash> (GALLERYPROMPT.md)
    @app.route('/g/<string:public_hash>')
    def public_gallery_redirect(public_hash: str):
        return redirect(f"/#/g/{public_hash}", code=302)
    
    @app.route('/<path:path>')
    def serve_frontend(path):
        # Do not swallow unknown API routes; let the JSON 404 handler respond.
        if path.startswith('api/'):
            abort(404)

        # Ensure proper content-type for PWA manifest
        if path == 'manifest.webmanifest':
            return send_from_directory(frontend_dir, path, mimetype='application/manifest+json')

        # Serve frontend files (JS, CSS, images, etc.)
        abs_path = os.path.join(frontend_dir, path)
        if os.path.isfile(abs_path):
            return send_from_directory(frontend_dir, path)

        # If file not found, return index.html for SPA routing
        return send_from_directory(frontend_dir, 'index.html')

    return app


def load_models():
    """Import all model modules to register them with SQLAlchemy."""
    from app.auth import models as _auth_models  # noqa: F401
    from app.customers import models as _customers_models  # noqa: F401
    from app.jobs import models as _jobs_models  # noqa: F401
    from app.contracts import models as _contracts_models  # noqa: F401
    from app.consents import models as _consents_models  # noqa: F401
    from app.invoices import models as _invoices_models  # noqa: F401
    from app.payments import models as _payments_models  # noqa: F401
    from app.galleries import models as _galleries_models  # noqa: F401
    from app.photos import models as _photos_models  # noqa: F401
    from app.settings import models as _settings_models  # noqa: F401
    from app.promotions import models as _promotions_models  # noqa: F401
    from app.vouchers import models as _vouchers_models  # noqa: F401


def register_blueprints(app):
    """Register all Flask blueprints."""
    from app.auth.routes import auth_bp
    from app.customers.routes import customers_bp
    from app.jobs.routes import jobs_bp
    from app.contracts.routes import contracts_bp
    from app.consents.routes import consents_bp
    from app.invoices.routes import invoices_bp
    from app.payments.routes import payments_bp
    from app.galleries.routes import galleries_bp
    from app.galleries.public_routes import public_gallery_bp
    from app.photos.routes import photos_bp
    from app.finance.routes import finance_bp
    from app.geo.routes import geo_bp
    from app.settings.routes import settings_bp
    from app.promotions.routes import promotions_bp
    from app.vouchers.routes import vouchers_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(customers_bp, url_prefix='/api/customers')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(contracts_bp, url_prefix='/api/contracts')
    app.register_blueprint(consents_bp, url_prefix='/api/consents')
    app.register_blueprint(invoices_bp, url_prefix='/api/invoices')
    app.register_blueprint(payments_bp, url_prefix='/api/payments')
    app.register_blueprint(galleries_bp, url_prefix='/api/galleries')
    app.register_blueprint(public_gallery_bp, url_prefix='/api/gallery')
    app.register_blueprint(photos_bp, url_prefix='/api/photos')
    app.register_blueprint(finance_bp, url_prefix='/api/finance')
    app.register_blueprint(geo_bp, url_prefix='/api/geo')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(promotions_bp, url_prefix='/api/promotions')
    app.register_blueprint(vouchers_bp, url_prefix='/api/vouchers')


def register_error_handlers(app):
    """Register global error handlers."""

    # JWT error handlers: return consistent JSON + 401.
    @jwt.unauthorized_loader
    def _jwt_missing_token(reason):
        return jsonify({'success': False, 'error': reason or 'Unauthorized', 'code': 'UNAUTHORIZED'}), 401

    @jwt.invalid_token_loader
    def _jwt_invalid_token(reason):
        return jsonify({'success': False, 'error': reason or 'Invalid token', 'code': 'UNAUTHORIZED'}), 401

    @jwt.expired_token_loader
    def _jwt_expired_token(jwt_header, jwt_payload):
        return jsonify({'success': False, 'error': 'Token wygasł', 'code': 'UNAUTHORIZED'}), 401

    @jwt.needs_fresh_token_loader
    def _jwt_needs_fresh(jwt_header, jwt_payload):
        return jsonify({'success': False, 'error': 'Wymagany świeży token', 'code': 'UNAUTHORIZED'}), 401

    @jwt.revoked_token_loader
    def _jwt_revoked(jwt_header, jwt_payload):
        return jsonify({'success': False, 'error': 'Token odwołany', 'code': 'UNAUTHORIZED'}), 401
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Resource not found',
            'code': 'NOT_FOUND'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad request',
            'code': 'BAD_REQUEST'
        }), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'success': False,
            'error': 'Forbidden',
            'code': 'FORBIDDEN'
        }), 403
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'code': 'UNAUTHORIZED'
        }), 401


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)

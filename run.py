"""EcoShot CRM - Main entry point."""

from app.app import create_app

# Utwórz aplikację
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

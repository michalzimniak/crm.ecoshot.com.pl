"""
Finance REST API endpoints.
Handles financial reports and statistics.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from app.core.decorators import api_endpoint
from app.core.permissions import Permission
from app.finance import services

finance_bp = Blueprint('finance', __name__)


@finance_bp.route('/stats', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_reports_stats():
    """Get aggregated stats for the Reports view."""
    stats = services.get_reports_stats()
    return jsonify({'success': True, 'data': stats})


@finance_bp.route('/revenue', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_revenue_series():
    """Get revenue time series for the Reports view."""
    period = (request.args.get('period') or 'month').strip().lower()
    series = services.get_revenue_series(period)
    return jsonify({'success': True, 'data': series})


@finance_bp.route('/revenue/summary', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_revenue_summary():
    """Get revenue summary for date range."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({
            'success': False,
            'error': 'start_date i end_date wymagane'
        }), 400
    
    try:
        start_date = datetime.fromisoformat(start_date)
        end_date = datetime.fromisoformat(end_date)
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Nieprawidłowy format daty (ISO 8601)'
        }), 400
    
    summary = services.get_revenue_summary(start_date, end_date)
    
    return jsonify({
        'success': True,
        'data': summary
    })


@finance_bp.route('/revenue/monthly', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_monthly_revenue():
    """Get monthly revenue for year."""
    year = request.args.get('year')
    
    if not year:
        year = datetime.now().year
    else:
        year = int(year)
    
    monthly_data = services.get_monthly_revenue(year)
    
    return jsonify({
        'success': True,
        'data': monthly_data
    })


@finance_bp.route('/revenue/by-offer', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_revenue_by_offer():
    """Get revenue breakdown by offer type."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        try:
            start_date = datetime.fromisoformat(start_date)
            end_date = datetime.fromisoformat(end_date)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Nieprawidłowy format daty'
            }), 400
    else:
        start_date = None
        end_date = None
    
    revenue = services.get_revenue_by_offer(start_date, end_date)
    
    return jsonify({
        'success': True,
        'data': revenue
    })


@finance_bp.route('/outstanding', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_INVOICES)
def get_outstanding_invoices():
    """Get outstanding invoices (unpaid or partially paid)."""
    invoices = services.get_outstanding_invoices()
    
    from app.invoices.schemas import invoices_schema
    
    return jsonify({
        'success': True,
        'data': invoices_schema.dump(invoices)
    })


@finance_bp.route('/overdue', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_INVOICES)
def get_overdue_invoices():
    """Get overdue invoices (past payment deadline)."""
    invoices = services.get_overdue_invoices()
    
    from app.invoices.schemas import invoices_schema
    
    return jsonify({
        'success': True,
        'data': invoices_schema.dump(invoices)
    })


@finance_bp.route('/dashboard', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_dashboard_stats():
    """Get dashboard statistics."""
    stats = services.get_dashboard_stats()
    
    return jsonify({
        'success': True,
        'data': stats
    })


@finance_bp.route('/top-customers', methods=['GET'])
@api_endpoint(permission=Permission.VIEW_FINANCE)
def get_top_customers():
    """Get top customers by revenue."""
    limit = int(request.args.get('limit', 10))
    
    customers = services.get_top_customers(limit)
    
    return jsonify({
        'success': True,
        'data': customers
    })

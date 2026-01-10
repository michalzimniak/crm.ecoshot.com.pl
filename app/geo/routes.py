"""Geo helper endpoints.

These endpoints proxy Google Places requests so the API key is not exposed
in the frontend.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest

from app.core.decorators import authenticated

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


geo_bp = Blueprint('geo', __name__)


BYDGOSZCZ = {
    'lat': 53.1235,
    'lng': 18.0084,
}
DEFAULT_RADIUS_METERS = 30000


def _get_google_key() -> str:
    api_key = current_app.config.get('GOOGLE_MAPS_API_KEY')
    if not api_key:
        raise BadRequest('Brak konfiguracji GOOGLE_MAPS_API_KEY')
    if requests is None:
        raise BadRequest('Brak zależności: requests')
    return api_key


def _get_browser_key() -> str:
    api_key = current_app.config.get('GOOGLE_MAPS_BROWSER_API_KEY')
    if not api_key:
        raise BadRequest('Brak konfiguracji GOOGLE_MAPS_BROWSER_API_KEY')
    return api_key


@geo_bp.route('/maps/browser-key', methods=['GET'])
@authenticated
def maps_browser_key():
    """Return Google Maps browser key for JS API.

    Note: this key will be visible in the browser. Restrict it in Google Cloud
    Console by HTTP referrer (domain) and limit enabled APIs.
    """
    return jsonify(
        {
            'success': True,
            'data': {
                'key': _get_browser_key(),
                'default_center': BYDGOSZCZ,
                'map_id': current_app.config.get('GOOGLE_MAPS_MAP_ID') or None,
            },
        }
    )


@geo_bp.route('/places/search', methods=['POST'])
@authenticated
def places_search():
    """Search for places near Bydgoszcz using Google Places Text Search."""
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    if not query:
        raise BadRequest('Brak parametru: query')

    api_key = _get_google_key()

    radius = int(data.get('radius_meters') or DEFAULT_RADIUS_METERS)
    radius = max(1000, min(radius, 100000))

    url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {
        'query': query,
        'language': 'pl',
        'region': 'pl',
        'location': f"{BYDGOSZCZ['lat']},{BYDGOSZCZ['lng']}",
        'radius': radius,
        'key': api_key,
    }

    resp = requests.get(url, params=params, timeout=10)
    payload = resp.json()

    status = payload.get('status')
    if status not in (None, 'OK', 'ZERO_RESULTS'):
        # Keep message user-friendly; do not leak key.
        raise BadRequest(payload.get('error_message') or f'Google Places błąd: {status}')

    results = payload.get('results') or []
    items = []
    for r in results[:10]:
        items.append(
            {
                'place_id': r.get('place_id'),
                'name': r.get('name'),
                'formatted_address': r.get('formatted_address'),
            }
        )

    return jsonify({'success': True, 'data': items})


@geo_bp.route('/places/details/<place_id>', methods=['GET'])
@authenticated
def places_details(place_id: str):
    """Fetch place details and return parsed address fields."""
    if not place_id:
        raise BadRequest('Brak place_id')

    api_key = _get_google_key()

    url = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'place_id': place_id,
        'fields': 'address_component,formatted_address,name,geometry',
        'language': 'pl',
        'region': 'pl',
        'key': api_key,
    }

    resp = requests.get(url, params=params, timeout=10)
    payload = resp.json()

    status = payload.get('status')
    if status != 'OK':
        raise BadRequest(payload.get('error_message') or f'Google Places błąd: {status}')

    result = payload.get('result') or {}
    components = result.get('address_components') or []

    def find_component(type_name: str):
        for c in components:
            if type_name in (c.get('types') or []):
                return c.get('long_name')
        return None

    street = find_component('route')
    street_number = find_component('street_number')
    city = (
        find_component('locality')
        or find_component('postal_town')
        or find_component('administrative_area_level_2')
    )
    postal_code = find_component('postal_code')

    street_full = None
    if street and street_number:
        street_full = f'{street} {street_number}'
    elif street:
        street_full = street

    geometry = result.get('geometry') or {}
    loc = geometry.get('location') or {}

    return jsonify(
        {
            'success': True,
            'data': {
                'place_id': place_id,
                'name': result.get('name'),
                'formatted_address': result.get('formatted_address'),
                'street': street_full,
                'city': city,
                'postal_code': postal_code,
                'lat': loc.get('lat'),
                'lng': loc.get('lng'),
            },
        }
    )


@geo_bp.route('/geocode/reverse', methods=['GET'])
@authenticated
def reverse_geocode():
    """Reverse geocode lat/lng -> address fields."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    if lat is None or lng is None:
        raise BadRequest('Brak parametrów: lat, lng')

    api_key = _get_google_key()

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {
        'latlng': f'{lat},{lng}',
        'language': 'pl',
        'region': 'pl',
        'key': api_key,
    }

    resp = requests.get(url, params=params, timeout=10)
    payload = resp.json()

    status = payload.get('status')
    if status != 'OK':
        raise BadRequest(payload.get('error_message') or f'Google Geocode błąd: {status}')

    results = payload.get('results') or []
    first = results[0] if results else {}
    components = first.get('address_components') or []

    def find_component(type_name: str):
        for c in components:
            if type_name in (c.get('types') or []):
                return c.get('long_name')
        return None

    street = find_component('route')
    street_number = find_component('street_number')
    city = (
        find_component('locality')
        or find_component('postal_town')
        or find_component('administrative_area_level_2')
    )
    postal_code = find_component('postal_code')

    street_full = None
    if street and street_number:
        street_full = f'{street} {street_number}'
    elif street:
        street_full = street

    return jsonify(
        {
            'success': True,
            'data': {
                'formatted_address': first.get('formatted_address'),
                'street': street_full,
                'city': city,
                'postal_code': postal_code,
                'lat': lat,
                'lng': lng,
            },
        }
    )

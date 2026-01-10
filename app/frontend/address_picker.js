/**
 * Address Picker (Google Places via backend proxy)
 *
 * Usage:
 *   import { openAddressPicker } from '../address_picker.js';
 *   openAddressPicker({
 *     title: 'Wybierz adres',
 *     onSelect: (details) => { ... }
 *   })
 */

import { api } from './api.js';
import { showToast } from './toasts.js';

let modalInstance = null;
let currentOnSelect = null;
let selectedDetails = null;
let mapsLoadingPromise = null;
let mapsState = null;
let mapModeEnabled = false;

function ensureModal() {
    if (document.getElementById('addressPickerModal')) {
        return;
    }

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
        <div class="modal fade" id="addressPickerModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="addressPickerTitle">Wyszukaj adres</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="input-group mb-3">
                            <input type="text" class="form-control" id="addressPickerQuery" placeholder="Wpisz adres (np. ul. Gdańska 1)">
                            <button class="btn btn-outline-secondary" type="button" id="addressPickerSearchBtn">
                                <i class="bi bi-search"></i>
                            </button>
                        </div>
                        <div class="small text-muted mb-3">Wyniki są wyszukiwane w pobliżu Bydgoszczy.</div>
                        <div class="row g-3">
                            <div class="col-lg-6">
                                <div id="addressPickerResults" class="list-group"></div>
                            </div>
                            <div class="col-lg-6">
                                <div class="border rounded overflow-hidden position-relative" style="height: 320px; background: #f8f9fa;">
                                    <iframe id="addressPickerMap" title="Mapa" style="border:0; width: 100%; height: 100%;" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                                    <div id="addressPickerInteractiveMap" style="display:none; width: 100%; height: 100%;"></div>
                                </div>
                                <div class="d-flex justify-content-between align-items-center mt-2">
                                    <div class="small text-muted" id="addressPickerSelectedLabel">Wybierz wynik, aby zobaczyć mapę.</div>
                                    <div class="d-flex gap-3 align-items-center">
                                        <button type="button" class="btn btn-sm btn-outline-primary" id="addressPickerToggleMapModeBtn">Wybierz na mapie</button>
                                        <a class="small" id="addressPickerOpenInMaps" href="#" target="_blank" rel="noopener" style="display:none;">Otwórz w Google Maps</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-success" id="addressPickerConfirmBtn" disabled>
                            <i class="bi bi-check-lg"></i> Wybierz adres
                        </button>
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(wrapper.firstElementChild);

    const modalEl = document.getElementById('addressPickerModal');
    // Bootstrap is loaded globally
    modalInstance = new window.bootstrap.Modal(modalEl);

    const queryEl = document.getElementById('addressPickerQuery');
    const searchBtn = document.getElementById('addressPickerSearchBtn');
    const confirmBtn = document.getElementById('addressPickerConfirmBtn');
    const toggleMapModeBtn = document.getElementById('addressPickerToggleMapModeBtn');

    toggleMapModeBtn.addEventListener('click', async () => {
        mapModeEnabled = !mapModeEnabled;
        toggleMapModeBtn.textContent = mapModeEnabled ? 'Podgląd mapy' : 'Wybierz na mapie';

        const iframe = document.getElementById('addressPickerMap');
        const mapDiv = document.getElementById('addressPickerInteractiveMap');

        if (mapModeEnabled) {
            iframe.style.display = 'none';
            mapDiv.style.display = '';
            await ensureInteractiveMap();
        } else {
            mapDiv.style.display = 'none';
            iframe.style.display = '';
        }
    });

    confirmBtn.addEventListener('click', () => {
        if (!selectedDetails) {
            showToast('Najpierw wybierz wynik z listy', 'warning');
            return;
        }

        if (typeof currentOnSelect === 'function') {
            currentOnSelect(selectedDetails);
        }
        modalInstance?.hide();
    });

    const runSearch = async () => {
        const query = (queryEl.value || '').trim();
        if (!query) {
            showToast('Wpisz frazę do wyszukania', 'warning');
            return;
        }

        const resultsEl = document.getElementById('addressPickerResults');
        resultsEl.innerHTML = `
            <div class="text-center py-3">
                <div class="spinner-border text-success" role="status"></div>
            </div>
        `;

        try {
            const resp = await api.post('/geo/places/search', { query }, { showErrors: true });
            const items = resp?.data || [];

            if (!items.length) {
                resultsEl.innerHTML = `<div class="text-muted px-2 py-2">Brak wyników</div>`;
                return;
            }

            resultsEl.innerHTML = items
                .map((i) => {
                    const name = i.name ? `<div class="fw-semibold">${escapeHtml(i.name)}</div>` : '';
                    const addr = i.formatted_address ? `<div class="text-muted small">${escapeHtml(i.formatted_address)}</div>` : '';
                    return `
                        <button type="button" class="list-group-item list-group-item-action" data-place-id="${escapeAttr(i.place_id)}">
                            ${name}
                            ${addr}
                        </button>
                    `;
                })
                .join('');

            resultsEl.querySelectorAll('[data-place-id]')
                .forEach((btn) => {
                    btn.addEventListener('click', async () => {
                        const placeId = btn.getAttribute('data-place-id');
                        await selectPlace(placeId);
                    });
                });

        } catch (e) {
            resultsEl.innerHTML = `<div class="text-danger px-2 py-2">Błąd wyszukiwania</div>`;
        }
    };

    searchBtn.addEventListener('click', runSearch);
    queryEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            runSearch();
        }
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
        currentOnSelect = null;
        selectedDetails = null;
        mapModeEnabled = false;
        document.getElementById('addressPickerToggleMapModeBtn').textContent = 'Wybierz na mapie';
        document.getElementById('addressPickerResults').innerHTML = '';
        document.getElementById('addressPickerQuery').value = '';
        document.getElementById('addressPickerConfirmBtn').disabled = true;
        document.getElementById('addressPickerSelectedLabel').textContent = 'Wybierz wynik, aby zobaczyć mapę.';
        document.getElementById('addressPickerOpenInMaps').style.display = 'none';
        document.getElementById('addressPickerOpenInMaps').setAttribute('href', '#');
        document.getElementById('addressPickerMap').setAttribute('src', '');

        // Reset interactive map visibility (keep instance cached)
        const iframe = document.getElementById('addressPickerMap');
        const mapDiv = document.getElementById('addressPickerInteractiveMap');
        iframe.style.display = '';
        mapDiv.style.display = 'none';
    });
}

async function selectPlace(placeId) {
    if (!placeId) return;

    const labelEl = document.getElementById('addressPickerSelectedLabel');
    labelEl.textContent = 'Ładowanie szczegółów...';

    try {
        const resp = await api.get(`/geo/places/details/${encodeURIComponent(placeId)}`);
        const details = resp?.data;
        if (!details) {
            showToast('Nie udało się pobrać szczegółów adresu', 'danger');
            return;
        }

        selectedDetails = details;
        document.getElementById('addressPickerConfirmBtn').disabled = false;

        const title = details.formatted_address || details.name || 'Wybrany adres';
        labelEl.textContent = title;

        const mapIframe = document.getElementById('addressPickerMap');
        const openInMaps = document.getElementById('addressPickerOpenInMaps');

        const mapUrl = buildMapEmbedUrl(details);
        const mapsLink = buildMapsLink(details);
        mapIframe.setAttribute('src', mapUrl);
        openInMaps.setAttribute('href', mapsLink);
        openInMaps.style.display = '';

        // If interactive map already initialized, move marker.
        if (mapsState?.marker && details?.lat != null && details?.lng != null) {
            const pos = { lat: details.lat, lng: details.lng };
            setMarkerPosition(mapsState.marker, pos);
            mapsState.map.setCenter(pos);
            mapsState.map.setZoom(16);
        }

    } catch (e) {
        showToast('Nie udało się pobrać szczegółów adresu', 'danger');
    }
}

export function openAddressPicker({ title, initialQuery, onSelect }) {
    ensureModal();

    currentOnSelect = onSelect;

    if (title) {
        document.getElementById('addressPickerTitle').textContent = title;
    }
    if (initialQuery) {
        document.getElementById('addressPickerQuery').value = initialQuery;
    }

    // Reset state (useful when reopening modal)
    selectedDetails = null;
    mapModeEnabled = false;
    document.getElementById('addressPickerToggleMapModeBtn').textContent = 'Wybierz na mapie';
    document.getElementById('addressPickerConfirmBtn').disabled = true;
    document.getElementById('addressPickerSelectedLabel').textContent = 'Wybierz wynik, aby zobaczyć mapę.';
    document.getElementById('addressPickerOpenInMaps').style.display = 'none';
    document.getElementById('addressPickerOpenInMaps').setAttribute('href', '#');
    document.getElementById('addressPickerMap').setAttribute('src', '');

    const iframe = document.getElementById('addressPickerMap');
    const mapDiv = document.getElementById('addressPickerInteractiveMap');
    iframe.style.display = '';
    mapDiv.style.display = 'none';

    modalInstance?.show();
}

async function ensureInteractiveMap() {
    await loadGoogleMaps();

    const mapDiv = document.getElementById('addressPickerInteractiveMap');
    if (!mapDiv) return;

    if (mapsState?.map) {
        // Map exists; ensure it has proper size after being shown.
        window.google.maps.event.trigger(mapsState.map, 'resize');
        return;
    }

    const cfg = await api.get('/geo/maps/browser-key');
    const center = cfg?.data?.default_center || { lat: 53.1235, lng: 18.0084 };
    const mapId = cfg?.data?.map_id || null;

    const initial = selectedDetails?.lat != null && selectedDetails?.lng != null
        ? { lat: selectedDetails.lat, lng: selectedDetails.lng }
        : center;

    const map = new window.google.maps.Map(mapDiv, {
        center: initial,
        zoom: selectedDetails ? 16 : 12,
        streetViewControl: false,
        mapTypeControl: false,
        fullscreenControl: false,
        ...(mapId ? { mapId } : {}),
    });

    const marker = createDraggableMarker(map, initial);
    if (!marker) {
        // Avoid deprecated legacy markers. If Advanced Markers are unavailable, we can still
        // let the user pick by clicking the map.
        showToast(
            mapId
                ? 'Nie udało się zainicjować zaawansowanego znacznika na mapie.'
                : 'Mapa działa bez znacznika. Aby włączyć zaawansowane znaczniki, ustaw GOOGLE_MAPS_MAP_ID.',
            'warning'
        );
    }

    const applyPosition = async (pos) => {
        setMarkerPosition(marker, pos);
        map.panTo(pos);

        const labelEl = document.getElementById('addressPickerSelectedLabel');
        labelEl.textContent = 'Pobieranie adresu...';

        try {
            const resp = await api.get(`/geo/geocode/reverse?${new URLSearchParams({ lat: String(pos.lat), lng: String(pos.lng) })}`);
            const data = resp?.data;
            if (!data) {
                showToast('Nie udało się pobrać adresu z mapy', 'danger');
                labelEl.textContent = 'Nie udało się pobrać adresu.';
                return;
            }

            selectedDetails = {
                ...(selectedDetails || {}),
                ...data,
                lat: pos.lat,
                lng: pos.lng,
            };

            document.getElementById('addressPickerConfirmBtn').disabled = false;
            labelEl.textContent = data.formatted_address || `${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)}`;

            const openInMaps = document.getElementById('addressPickerOpenInMaps');
            openInMaps.setAttribute('href', buildMapsLink(selectedDetails));
            openInMaps.style.display = '';

        } catch (e) {
            labelEl.textContent = 'Nie udało się pobrać adresu.';
        }
    };

    map.addListener('click', (e) => {
        if (!e?.latLng) return;
        applyPosition({ lat: e.latLng.lat(), lng: e.latLng.lng() });
    });

    if (marker?.addListener) {
        marker.addListener('dragend', (e) => {
            if (!e?.latLng) return;
            applyPosition({ lat: e.latLng.lat(), lng: e.latLng.lng() });
        });
    }

    mapsState = { map, marker };
}

async function loadGoogleMaps() {
    if (window.google?.maps) return;
    if (mapsLoadingPromise) return mapsLoadingPromise;

    mapsLoadingPromise = (async () => {
        const cfg = await api.get('/geo/maps/browser-key');
        const key = cfg?.data?.key;
        if (!key) {
            showToast('Brak konfiguracji GOOGLE_MAPS_BROWSER_API_KEY', 'danger');
            throw new Error('Missing GOOGLE_MAPS_BROWSER_API_KEY');
        }

        await new Promise((resolve, reject) => {
            const callbackName = `__ecoshotMapsInit_${Date.now()}`;
            let timeoutId = null;

            const previousAuthFailure = window.gm_authFailure;
            window.gm_authFailure = () => {
                if (timeoutId) clearTimeout(timeoutId);
                delete window[callbackName];
                window.gm_authFailure = previousAuthFailure;
                showToast('Błąd Google Maps: nieprawidłowy klucz lub ograniczenia domeny.', 'danger');
                reject(new Error('Google Maps auth failure'));
            };

            window[callbackName] = () => {
                if (timeoutId) clearTimeout(timeoutId);
                delete window[callbackName];
                window.gm_authFailure = previousAuthFailure;
                resolve();
            };

            const script = document.createElement('script');
            // Include the 'marker' library for google.maps.marker.AdvancedMarkerElement.
            script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&callback=${encodeURIComponent(callbackName)}&libraries=marker&loading=async&v=weekly`;
            script.async = true;
            script.defer = true;
            script.onerror = () => {
                if (timeoutId) clearTimeout(timeoutId);
                delete window[callbackName];
                window.gm_authFailure = previousAuthFailure;
                reject(new Error('Failed to load Google Maps JS'));
            };

            timeoutId = window.setTimeout(() => {
                delete window[callbackName];
                window.gm_authFailure = previousAuthFailure;
                reject(new Error('Timed out while loading Google Maps JS'));
            }, 15000);

            document.head.appendChild(script);
        });

        // In newer Maps JS versions, this can help ensure the marker library is ready.
        // Safe no-op on older versions.
        if (window.google?.maps?.importLibrary) {
            try {
                await window.google.maps.importLibrary('marker');
            } catch {
                // ignore; we'll fall back to legacy marker if needed
            }
        }
    })();

    return mapsLoadingPromise;
}

function createDraggableMarker(map, position) {
    const adv = window.google?.maps?.marker?.AdvancedMarkerElement;
    if (typeof adv !== 'function') {
        return null;
    }

    return new adv({
        map,
        position,
        gmpDraggable: true,
    });
}

function setMarkerPosition(marker, position) {
    if (!marker) return;

    // AdvancedMarkerElement uses a 'position' property instead of setPosition().
    if ('position' in marker && typeof marker.setPosition !== 'function') {
        marker.position = position;
        return;
    }

    if (typeof marker.setPosition === 'function') {
        marker.setPosition(position);
    }
}

function buildMapsLink(details) {
    if (details?.lat != null && details?.lng != null) {
        return `https://www.google.com/maps?q=${encodeURIComponent(`${details.lat},${details.lng}`)}`;
    }
    if (details?.formatted_address) {
        return `https://www.google.com/maps?q=${encodeURIComponent(details.formatted_address)}`;
    }
    if (details?.name) {
        return `https://www.google.com/maps?q=${encodeURIComponent(details.name)}`;
    }
    return 'https://www.google.com/maps';
}

function buildMapEmbedUrl(details) {
    if (details?.lat != null && details?.lng != null) {
        return `https://www.google.com/maps?q=${encodeURIComponent(`${details.lat},${details.lng}`)}&z=16&output=embed`;
    }

    const query = details?.formatted_address || details?.name || '';
    if (query) {
        return `https://www.google.com/maps?q=${encodeURIComponent(query)}&z=16&output=embed`;
    }

    return '';
}

function escapeHtml(str) {
    return String(str)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function escapeAttr(str) {
    return escapeHtml(str).replaceAll('`', '');
}

/**
 * Public Gallery Access View (client)
 * Legacy route: #/gallery-access/<token>
 * New route:    #/g/<public_hash>
 */

import { apiRequest, apiDownload } from '../api.js';
import { showToast } from '../toasts.js';
import { applyBranding } from '../branding.js';

function consentTypeLabel(consentType) {
    const t = String(consentType || '').trim();
    if (t === 'image_publication') return 'Zgoda na publikację wizerunku';
    if (t === 'data_processing') return 'Zgoda na przetwarzanie danych';
    if (t === 'marketing') return 'Zgoda marketingowa';
    return t || 'Zgoda';
}

let currentToken = null;
let currentGallery = null;

let currentPublicHash = null;
let currentGallerySessionToken = null;

const GALLERY_SESSION_TTL_MS = 30 * 60 * 1000;

function gallerySessionTokenKey(publicHash) {
    return `ecoshot_gallery_session_token:${publicHash}`;
}

function gallerySessionExpiryKey(publicHash) {
    return `ecoshot_gallery_session_expires_at:${publicHash}`;
}

function clearStoredGallerySession(publicHash) {
    if (!publicHash) return;
    try {
        localStorage.removeItem(gallerySessionTokenKey(publicHash));
        localStorage.removeItem(gallerySessionExpiryKey(publicHash));
    } catch (_) {
        // ignore
    }
}

function getStoredGallerySessionToken(publicHash) {
    if (!publicHash) return null;
    try {
        const token = localStorage.getItem(gallerySessionTokenKey(publicHash));
        const expiresAtRaw = localStorage.getItem(gallerySessionExpiryKey(publicHash));
        const expiresAt = expiresAtRaw ? Number(expiresAtRaw) : 0;

        if (!token || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
            clearStoredGallerySession(publicHash);
            return null;
        }

        return token;
    } catch (_) {
        return null;
    }
}

function storeGallerySessionToken(publicHash, token) {
    if (!publicHash || !token) return;
    try {
        localStorage.setItem(gallerySessionTokenKey(publicHash), token);
        localStorage.setItem(gallerySessionExpiryKey(publicHash), String(Date.now() + GALLERY_SESSION_TTL_MS));
    } catch (_) {
        // ignore
    }
}

function getVisibleContainer() {
    const appContainer = document.getElementById('appContainer');
    const isAppVisible = appContainer && !appContainer.classList.contains('d-none');
    return isAppVisible ? document.getElementById('viewContainer') : document.getElementById('loginContainer');
}

function parseQuery() {
    const query = window.location.hash.split('?')[1] || '';
    return new URLSearchParams(query);
}

async function fetchGallery(token, password = null) {
    const qs = new URLSearchParams();
    if (password) qs.set('password', password);

    const endpoint = `/galleries/access/${encodeURIComponent(token)}${qs.toString() ? `?${qs}` : ''}`;

    // Public endpoint: do not force auth redirect/clear.
    return apiRequest(endpoint, { skipAuth: true, showErrors: false });
}

async function fetchPublicGallery(publicHash, sessionToken = null) {
    const headers = {};
    if (sessionToken) {
        headers['Authorization'] = `Bearer ${sessionToken}`;
    }

    return apiRequest(`/gallery/${encodeURIComponent(publicHash)}`, {
        skipAuth: true,
        showErrors: false,
        headers,
    });
}

async function verifyPublicPin(publicHash, pin) {
    return apiRequest(`/gallery/${encodeURIComponent(publicHash)}/pin`, {
        method: 'POST',
        body: { pin },
        skipAuth: true,
        showErrors: false,
    });
}

function renderLoading(container) {
    container.innerHTML = `
        <div class="min-vh-100 bg-light">
            <div class="container py-4">
                <div class="d-flex align-items-center justify-content-center mb-4" style="gap: .75rem;">
                    <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 34px; width: auto;" />
                    <i id="loginBrandIcon" class="bi bi-camera-fill fs-3 text-success"></i>
                    <span id="loginBrandText" class="fw-semibold"></span>
                </div>
                <div class="card">
                    <div class="card-body text-center py-5">
                        <div class="spinner-border text-success" role="status"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderPasswordPrompt(container, message) {
    container.innerHTML = `
        <div class="min-vh-100 bg-light">
            <div class="container py-4" style="max-width: 720px;">
                <div class="d-flex align-items-center justify-content-center mb-4" style="gap: .75rem;">
                    <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 34px; width: auto;" />
                    <i id="loginBrandIcon" class="bi bi-camera-fill fs-3 text-success"></i>
                    <span id="loginBrandText" class="fw-semibold"></span>
                </div>
                <div class="card">
                    <div class="card-body">
                        <h5 class="mb-3"><i class="bi bi-lock"></i> Ta galeria jest zabezpieczona</h5>
                        <p class="mb-3">${message || 'Ta galeria wymaga hasła.'}</p>
                        <form id="galleryAccessPasswordForm" class="row g-2" novalidate>
                            <div class="col-12 col-md-7">
                                <input type="password" class="form-control" id="galleryAccessPassword" placeholder="Hasło" autocomplete="current-password" required>
                            </div>
                            <div class="col-12 col-md-auto">
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-unlock"></i> Otwórz galerię
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;

    const form = document.getElementById('galleryAccessPasswordForm');
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = document.getElementById('galleryAccessPassword')?.value || '';
        if (!password.trim()) {
            showToast('Wpisz hasło', 'warning');
            return;
        }
        await loadAndRender(currentToken, password);
    });
}

function renderPinPrompt(container, message) {
    container.innerHTML = `
        <div class="min-vh-100 bg-light d-flex align-items-center">
            <div class="container py-4 w-100" style="max-width: 720px;">
                <div class="d-flex align-items-center justify-content-center mb-4" style="gap: .75rem;">
                    <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 34px; width: auto;" />
                    <i id="loginBrandIcon" class="bi bi-camera-fill fs-3 text-success"></i>
                    <span id="loginBrandText" class="fw-semibold"></span>
                </div>
                <div class="card">
                    <div class="card-body">
                        <h5 class="mb-3"><i class="bi bi-shield-lock"></i> Podaj PIN</h5>
                        <p class="mb-3">${message || 'Ta galeria jest zabezpieczona kodem PIN.'}</p>
                        <form id="galleryAccessPinForm" class="row g-2" novalidate>
                            <div class="col-12 col-md-5">
                                <input type="text" inputmode="numeric" pattern="[0-9]*" class="form-control" id="galleryAccessPin" placeholder="PIN (4–6 cyfr)" autocomplete="one-time-code" required>
                            </div>
                            <div class="col-12 col-md-auto">
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-unlock"></i> Otwórz galerię
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;

    const form = document.getElementById('galleryAccessPinForm');
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pin = (document.getElementById('galleryAccessPin')?.value || '').trim();
        if (!pin) {
            showToast('Wpisz PIN', 'warning');
            return;
        }
        await loadAndRenderPublic(currentPublicHash, pin);
    });
}

function renderError(container, message) {
    container.innerHTML = `
        <div class="min-vh-100 bg-light">
            <div class="container py-4" style="max-width: 720px;">
                <div class="d-flex align-items-center justify-content-center mb-4" style="gap: .75rem;">
                    <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 34px; width: auto;" />
                    <i id="loginBrandIcon" class="bi bi-camera-fill fs-3 text-success"></i>
                    <span id="loginBrandText" class="fw-semibold"></span>
                </div>
                <div class="card">
                    <div class="card-body">
                        <h5 class="mb-3"><i class="bi bi-exclamation-triangle"></i> Galeria</h5>
                        <p class="mb-0">${message || 'Nie udało się załadować galerii.'}</p>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderGallery(container, gallery) {
    const photos = Array.isArray(gallery?.photos) ? gallery.photos : [];
    const isSelectionGallery = gallery?.gallery_type === 'selection';
    const canSelect = Boolean(gallery?.allow_selection) && isSelectionGallery;
    const maxSelections = gallery?.max_selections;
    const selectedCount = Number.isFinite(gallery?.selected_count) ? gallery.selected_count : null;
    const atMaxSelections = canSelect && Number.isFinite(maxSelections) && selectedCount !== null && selectedCount >= maxSelections;
    const selectionInfo = canSelect
        ? `<span class="badge bg-light text-dark">Wybrane: ${selectedCount ?? '-'}${maxSelections ? ` / ${maxSelections}` : ''}</span>`
        : '';

    const job = gallery?.job || null;
    const offer = job?.offer || null;
    const selectedAddonsRaw = Array.isArray(job?.selected_addons) ? job.selected_addons : (Array.isArray(job?.addons) ? job.addons : []);
    const selectedAddons = selectedAddonsRaw.filter(a => a && a.is_selected !== false);
    const documents = gallery?.documents || null;
    const contractDoc = documents?.contract || null;
    const consentDocs = Array.isArray(documents?.consents) ? documents.consents : [];

    // UX per GALLERYPROMPT.md: show Download button for FINAL + paid.
    // Backend still enforces stricter requirements (completed, watermark disabled, allow_download).
    const showDownloadBtn = gallery?.gallery_type === 'final' && gallery?.invoice_paid === true;

    container.innerHTML = `
        <div class="min-vh-100 bg-light">
            <div class="container py-4">
                <div class="d-flex align-items-center justify-content-between mb-3" style="gap: 1rem; flex-wrap: wrap;">
                    <div class="d-flex align-items-center" style="gap: .75rem;">
                        <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 34px; width: auto;" />
                        <i id="loginBrandIcon" class="bi bi-camera-fill fs-3 text-success"></i>
                        <span id="loginBrandText" class="fw-semibold"></span>
                    </div>
                    <div class="d-flex align-items-center" style="gap: .5rem; flex-wrap: wrap; justify-content-end;">
                        <span class="badge bg-${gallery?.gallery_type === 'final' ? 'primary' : (gallery?.gallery_type === 'selection' ? 'success' : (gallery?.gallery_type === 'archive' ? 'secondary' : 'info'))}">
                            ${gallery?.gallery_type === 'final' ? 'FINAL' : (gallery?.gallery_type === 'selection' ? 'SELECTION' : (gallery?.gallery_type === 'archive' ? 'ARCHIVE' : 'PROOF'))}
                        </span>
                        ${gallery?.invoice_paid === true ? '<span class="badge bg-success">OPŁACONE</span>' : (gallery?.invoice_paid === false ? '<span class="badge bg-warning text-dark">NIEOPŁACONE</span>' : '')}
                        ${gallery?.watermark_required ? '<span class="badge bg-secondary">WATERMARK</span>' : ''}
                    </div>
                </div>

                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex align-items-start justify-content-between" style="gap: 1rem; flex-wrap: wrap;">
                            <div>
                                <h4 class="mb-1">${gallery?.name || gallery?.title || 'Galeria'}</h4>
                                ${gallery?.description ? `<p class="text-muted mb-2">${gallery.description}</p>` : ''}
                                <div class="d-flex align-items-center" style="gap: .5rem; flex-wrap: wrap;">
                                    <span class="badge bg-light text-dark">${photos.length} zdjęć</span>
                                    ${selectionInfo}
                                    ${canSelect && atMaxSelections ? `<span class="badge bg-warning text-dark">Osiągnięto limit wyboru</span>` : ''}
                                </div>
                            </div>
                            ${showDownloadBtn ? `
                                <button class="btn btn-primary" id="publicGalleryDownloadBtn">
                                    <i class="bi bi-download"></i> Download ZIP
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>

                ${(offer || selectedAddons.length || (contractDoc?.available || consentDocs.length)) ? `
                    <div class="card mb-3">
                        <div class="card-body">
                            <h5 class="mb-2"><i class="bi bi-briefcase"></i> Zlecenie</h5>
                            ${offer ? `
                                <div class="mb-2">
                                    <div class="fw-semibold">Plan: ${offer.name || '—'}</div>
                                    ${offer.description ? `<div class="text-muted">${offer.description}</div>` : ''}
                                    <div class="d-flex flex-wrap mt-2" style="gap: .5rem;">
                                        ${Number.isFinite(offer.hours_included) ? `<span class="badge bg-light text-dark">Godziny: ${offer.hours_included}</span>` : ''}
                                        ${Number.isFinite(offer.photos_count) ? `<span class="badge bg-light text-dark">Zdjecia: ${offer.photos_count}</span>` : ''}
                                        ${offer.video_included ? `<span class="badge bg-light text-dark">Video</span>` : ''}
                                    </div>
                                </div>
                            ` : ''}

                            <div class="mb-2">
                                <div class="fw-semibold">Dodatki</div>
                                ${selectedAddons.length ? `
                                    <ul class="mb-0">
                                        ${selectedAddons.map(a => `
                                            <li>${a.name || 'Dodatek'}${(a.pricing_model === 'per_unit' && a.quantity) ? ` (x${a.quantity})` : ''}</li>
                                        `).join('')}
                                    </ul>
                                ` : `<div class="text-muted">Brak wybranych dodatkow</div>`}
                            </div>

                            ${(contractDoc?.available || consentDocs.length) ? `
                                <div class="mt-3">
                                    <div class="fw-semibold mb-2">Dokumenty</div>
                                    <div class="d-flex flex-wrap" style="gap: .5rem;">
                                        ${contractDoc?.available ? `
                                            <button class="btn btn-outline-secondary btn-sm" id="publicDownloadContractBtn">
                                                <i class="bi bi-file-earmark-text"></i> Pobierz skan umowy
                                            </button>
                                        ` : ''}
                                        ${consentDocs.map(c => `
                                            <button class="btn btn-outline-secondary btn-sm" data-consent-id="${c.id}" data-consent-url="${c.download_url || ''}">
                                                <i class="bi bi-file-earmark-check"></i> ${consentTypeLabel(c.consent_type)}
                                            </button>
                                        `).join('')}
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}

                ${photos.length === 0 ? `
                    <div class="card">
                        <div class="card-body text-center py-5">
                            <i class="bi bi-images display-1 text-muted"></i>
                            <p class="text-muted mt-3 mb-0">Brak zdjęć</p>
                        </div>
                    </div>
                ` : `
                    <div class="row g-3">
                        ${photos.map(photo => {
                            const selected = Boolean(photo.is_selected);
                            const badge = selected ? `<span class="badge bg-success">Wybrane</span>` : '';

                            const disableSelect = canSelect && !selected && atMaxSelections;
                            const selectBtn = canSelect ? `
                                <button class="btn btn-sm ${selected ? 'btn-outline-success' : (disableSelect ? 'btn-outline-secondary' : 'btn-success')}"
                                        ${disableSelect ? 'disabled' : ''}
                                        onclick="window.__togglePublicSelection(${photo.id}, ${selected ? 'false' : 'true'})">
                                    <i class="bi ${selected ? 'bi-check2' : 'bi-hand-index'}"></i> ${selected ? 'Odznacz' : 'Wybierz'}
                                </button>
                            ` : '';

                            return `
                                <div class="col-6 col-md-3 col-lg-2">
                                    <div class="card">
                                        <div class="position-relative">
                                            <img src="/api/photos/${photo.id}/download?version=thumbnail"
                                                 class="card-img-top"
                                                 alt="${photo.filename || 'Zdjęcie'}"
                                                 onclick="window.__openPublicPhoto(${photo.id})"
                                                 style="cursor: pointer; aspect-ratio: 1; object-fit: cover;">
                                            <div class="position-absolute top-0 end-0 p-2">${badge}</div>
                                        </div>
                                        <div class="card-body p-2 d-flex align-items-center justify-content-between" style="gap: .5rem;">
                                            <small class="text-muted text-truncate" title="${photo.filename || ''}">${photo.filename || `#${photo.id}`}</small>
                                            ${selectBtn}
                                        </div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `}

                <div class="modal fade" id="publicPhotoModal" tabindex="-1">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="publicPhotoModalTitle">Zdjęcie</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body text-center" id="publicPhotoModalBody"></div>
                            <div class="modal-footer" id="publicPhotoModalFooter">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Zamknij</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Expose minimal handlers.
    window.__openPublicPhoto = (photoId) => {
        const filename = currentGallery?.photos?.find?.(p => p.id === photoId)?.filename || '';
        const title = document.getElementById('publicPhotoModalTitle');
        const body = document.getElementById('publicPhotoModalBody');
        const footer = document.getElementById('publicPhotoModalFooter');
        if (title) title.textContent = filename || `Zdjęcie #${photoId}`;
        if (body) {
            body.innerHTML = `
                <img src="/api/photos/${photoId}/download?version=watermarked" class="img-fluid" alt="${filename || ''}">
            `;
        }

        const canDownloadOriginal = Boolean(currentGallery?.download_available);
        if (footer) {
            footer.innerHTML = `
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Zamknij</button>
                ${canDownloadOriginal ? `
                    <button type="button" class="btn btn-primary" id="publicPhotoModalDownloadBtn">
                        <i class="bi bi-download"></i> Pobierz
                    </button>
                ` : ''}
            `;

            const downloadBtn = document.getElementById('publicPhotoModalDownloadBtn');
            downloadBtn?.addEventListener('click', async () => {
                try {
                    const headers = {};
                    if (currentGallerySessionToken) {
                        headers['Authorization'] = `Bearer ${currentGallerySessionToken}`;
                    }

                    const result = await apiDownload(`/photos/${photoId}/download?version=original`, {
                        skipAuth: true,
                        headers,
                        showLoading: true,
                    });
                    if (!result?.blob) return;
                    const url = URL.createObjectURL(result.blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = result.filename || filename || `photo_${photoId}`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                } catch (e) {
                    console.error('Photo download failed:', e);
                    showToast(e?.message || 'Nie udało się pobrać zdjęcia', 'danger');
                }
            });
        }

        const modalEl = document.getElementById('publicPhotoModal');
        if (modalEl && window.bootstrap?.Modal) {
            const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        }
    };

    window.__togglePublicSelection = async (photoId, isSelected) => {
        try {
            if (canSelect && !isSelected && Number.isFinite(maxSelections) && selectedCount !== null && selectedCount >= maxSelections) {
                showToast('Osiągnięto limit wyboru zdjęć', 'warning');
                return;
            }
            const headers = {};
            if (currentGallerySessionToken) {
                headers['Authorization'] = `Bearer ${currentGallerySessionToken}`;
            }

            await apiRequest(`/photos/${photoId}/toggle-selection`, {
                method: 'POST',
                body: { is_selected: isSelected },
                skipAuth: true,
                showErrors: false,
                headers,
            });
            if (currentPublicHash) {
                await loadAndRenderPublic(currentPublicHash);
            } else {
                await loadAndRender(currentToken);
            }
        } catch (e) {
            console.error('Selection toggle failed:', e);
            const status = e?.status;
            if (status === 401 && currentPublicHash) {
                currentGallerySessionToken = null;
                clearStoredGallerySession(currentPublicHash);
                renderPinPrompt(getVisibleContainer(), 'Sesja wygasła. Podaj PIN ponownie.');
                try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
                return;
            }
            showToast(e?.message || 'Nie udało się zaktualizować wyboru', 'danger');
        }
    };

    const downloadEl = document.getElementById('publicGalleryDownloadBtn');
    downloadEl?.addEventListener('click', async () => {
        try {
            if (!currentPublicHash || !currentGallerySessionToken) {
                showToast('Brak sesji galerii', 'warning');
                return;
            }
            const result = await apiDownload(`/gallery/${encodeURIComponent(currentPublicHash)}/download`, {
                skipAuth: true,
                headers: { Authorization: `Bearer ${currentGallerySessionToken}` },
                showLoading: true,
            });
            if (!result?.blob) return;
            const url = URL.createObjectURL(result.blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = result.filename || 'gallery.zip';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('ZIP download failed:', e);
            showToast(e?.message || 'Nie udało się pobrać ZIP', 'danger');
        }
    });

    // Documents downloads (public hash flow only)
    const contractBtn = document.getElementById('publicDownloadContractBtn');
    contractBtn?.addEventListener('click', async () => {
        try {
            if (!currentPublicHash || !currentGallerySessionToken) {
                showToast('Brak sesji galerii', 'warning');
                return;
            }
            const result = await apiDownload(`/gallery/${encodeURIComponent(currentPublicHash)}/contract-scan`, {
                skipAuth: true,
                headers: { Authorization: `Bearer ${currentGallerySessionToken}` },
                showLoading: true,
            });
            if (!result?.blob) return;
            const url = URL.createObjectURL(result.blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = result.filename || 'contract_scan';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('Contract scan download failed:', e);
            showToast(e?.message || 'Nie udało się pobrać skanu umowy', 'danger');
        }
    });

    container.querySelectorAll('button[data-consent-id]')?.forEach((btn) => {
        btn.addEventListener('click', async () => {
            try {
                if (!currentPublicHash || !currentGallerySessionToken) {
                    showToast('Brak sesji galerii', 'warning');
                    return;
                }
                const url = btn.getAttribute('data-consent-url') || '';
                if (!url) {
                    showToast('Brak linku do pliku', 'warning');
                    return;
                }
                const apiPath = url.startsWith('/api') ? url.replace('/api', '') : url;
                const result = await apiDownload(apiPath, {
                    skipAuth: true,
                    headers: { Authorization: `Bearer ${currentGallerySessionToken}` },
                    showLoading: true,
                });
                if (!result?.blob) return;
                const blobUrl = URL.createObjectURL(result.blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = result.filename || 'consent_scan';
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(blobUrl);
            } catch (e) {
                console.error('Consent scan download failed:', e);
                showToast(e?.message || 'Nie udało się pobrać skanu zgody', 'danger');
            }
        });
    });
}

async function loadAndRender(token, password = null) {
    currentToken = token;
    const container = getVisibleContainer();

    renderLoading(container);

    // Apply branding for public view (uses login* IDs we render).
    try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }

    try {
        const response = await fetchGallery(token, password);
        currentGallery = response?.data;

        if (!currentGallery) {
            renderError(container, 'Nie udało się załadować galerii');
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }

        renderGallery(container, currentGallery);

        try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }

    } catch (e) {
        const status = e?.status;
        const message = e?.message || 'Błąd ładowania galerii';

        // If password required/invalid, show password form.
        if (status === 401) {
            renderPasswordPrompt(container, message);
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }

        renderError(container, message);
        try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
        console.error('Public gallery load failed:', e);
    }
}

async function loadAndRenderPublic(publicHash, pin = null) {
    currentPublicHash = publicHash;
    const container = getVisibleContainer();

    renderLoading(container);

    try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }

    if (pin) {
        try {
            const resp = await verifyPublicPin(publicHash, pin);
            const token = resp?.data?.access_token;
            if (!token) {
                renderPinPrompt(container, 'Nie udało się utworzyć sesji galerii.');
                try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
                return;
            }
            currentGallerySessionToken = token;
            storeGallerySessionToken(publicHash, token);
        } catch (e) {
            const status = e?.status;
            if (status === 429) {
                renderPinPrompt(container, e?.message || 'Zbyt wiele prób. Spróbuj później.');
                try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
                return;
            }
            renderPinPrompt(container, e?.message || 'Nieprawidłowy PIN.');
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }
    } else {
        // Try to reuse a recent session (30 min) without asking for PIN.
        currentGallerySessionToken = getStoredGallerySessionToken(publicHash);
    }

    try {
        const resp = await fetchPublicGallery(publicHash, currentGallerySessionToken);
        const data = resp?.data;
        if (!data) {
            renderError(container, 'Nie udało się załadować galerii');
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }

        if (data.requires_pin) {
            currentGallerySessionToken = null;
            clearStoredGallerySession(publicHash);
            renderPinPrompt(container);
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }

        currentGallery = data;
        renderGallery(container, currentGallery);

        try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
    } catch (e) {
        const status = e?.status;
        if (status === 401) {
            currentGallerySessionToken = null;
            clearStoredGallerySession(publicHash);
            renderPinPrompt(container, 'Sesja wygasła. Podaj PIN ponownie.');
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }
        renderError(container, e?.message || 'Błąd ładowania galerii');
        try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
        console.error('Public hash gallery load failed:', e);
    }
}


export async function renderPublicGallery(params = []) {
    const publicHash = params?.[0];
    const container = getVisibleContainer();

    currentPublicHash = publicHash || null;
    currentGallerySessionToken = null;
    currentGallery = null;

    if (!publicHash) {
        renderError(container, 'Brak identyfikatora galerii');
        return;
    }

    await loadAndRenderPublic(publicHash);
}

export async function renderGalleryAccess(params = []) {
    const tokenFromPath = params?.[0];
    const query = parseQuery();
    const tokenFromQuery = query.get('token');

    const token = tokenFromPath || tokenFromQuery;

    const container = getVisibleContainer();

    if (!token) {
        renderError(container, 'Brak tokenu dostępu');
        return;
    }

    currentPublicHash = null;
    currentGallerySessionToken = null;

    await loadAndRender(token);
}

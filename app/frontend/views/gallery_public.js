/**
 * Public Gallery View (hash + PIN)
 * Route: /g/<public_hash> (server redirects to #/g/<public_hash>)
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

function tokenStorageKey(publicHash) {
    return `ecoshot_gallery_token:${publicHash}`;
}

function getStoredGalleryToken(publicHash) {
    try {
        return sessionStorage.getItem(tokenStorageKey(publicHash));
    } catch (_) {
        return null;
    }
}

function storeGalleryToken(publicHash, token) {
    try {
        sessionStorage.setItem(tokenStorageKey(publicHash), token);
    } catch (_) {
        // ignore
    }
}

function clearGalleryToken(publicHash) {
    try {
        sessionStorage.removeItem(tokenStorageKey(publicHash));
    } catch (_) {
        // ignore
    }
}

function getVisibleContainer() {
    const appContainer = document.getElementById('appContainer');
    const isAppVisible = appContainer && !appContainer.classList.contains('d-none');
    return isAppVisible ? document.getElementById('viewContainer') : document.getElementById('loginContainer');
}

async function fetchPublicGallery(publicHash, token = null) {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    return apiRequest(`/gallery/${encodeURIComponent(publicHash)}`, {
        skipAuth: true,
        showErrors: false,
        headers,
    });
}

async function verifyPin(publicHash, pin) {
    return apiRequest(`/gallery/${encodeURIComponent(publicHash)}/pin`, {
        method: 'POST',
        skipAuth: true,
        showErrors: false,
        body: { pin },
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

function renderPinPrompt(container, galleryMeta, publicHash, message) {
    const title = galleryMeta?.name || galleryMeta?.title || 'Galeria';

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
                        <h5 class="mb-1"><i class="bi bi-lock"></i> ${title}</h5>
                        ${galleryMeta?.description ? `<p class="text-muted mb-3">${galleryMeta.description}</p>` : '<div class="mb-3"></div>'}
                        <p class="mb-3">${message || 'Podaj PIN, aby otworzyć galerię.'}</p>
                        <form id="galleryPinForm" class="row g-2" novalidate>
                            <div class="col-12 col-md-7">
                                <input type="text" inputmode="numeric" pattern="[0-9]*" class="form-control" id="galleryPin" placeholder="PIN (4–6 cyfr)" autocomplete="one-time-code" required>
                            </div>
                            <div class="col-12 col-md-auto">
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-unlock"></i> Otwórz
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;

    const form = document.getElementById('galleryPinForm');
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pin = (document.getElementById('galleryPin')?.value || '').trim();
        if (!pin) {
            showToast('Wpisz PIN', 'warning');
            return;
        }
        await loadAndRender(publicHash, { pin });
    });
}

function galleryBadges(gallery) {
    const badges = [];
    const type = gallery?.gallery_type;

    if (type === 'proof') badges.push('<span class="badge bg-info">PROOF</span>');
    if (type === 'selection') badges.push('<span class="badge bg-warning text-dark">SELECTION</span>');
    if (type === 'final') badges.push('<span class="badge bg-primary">FINAL</span>');
    if (type === 'archive') badges.push('<span class="badge bg-secondary">ARCHIVE</span>');

    if (gallery?.watermark_required) badges.push('<span class="badge bg-dark">WATERMARK</span>');
    if (gallery?.invoice_paid) badges.push('<span class="badge bg-success">PAID</span>');

    return badges.join(' ');
}

function renderGallery(container, gallery, publicHash, token) {
    const photos = Array.isArray(gallery?.photos) ? gallery.photos : [];
    const canSelect = Boolean(gallery?.allow_selection) && gallery?.gallery_type === 'selection';
    const maxSelections = gallery?.max_selections;
    const selectedCount = Number.isFinite(gallery?.selected_count) ? gallery.selected_count : null;
    const atMaxSelections = canSelect && Number.isFinite(maxSelections) && selectedCount !== null && selectedCount >= maxSelections;

    // UX per GALLERYPROMPT.md: show Download button for FINAL + paid.
    // Backend still enforces stricter requirements (completed, watermark disabled, allow_download).
    const downloadVisible = gallery?.gallery_type === 'final' && gallery?.invoice_paid === true;

    const job = gallery?.job || null;
    const offer = job?.offer || null;
    const selectedAddonsRaw = Array.isArray(job?.selected_addons) ? job.selected_addons : (Array.isArray(job?.addons) ? job.addons : []);
    const selectedAddons = selectedAddonsRaw.filter(a => a && a.is_selected !== false);
    const documents = gallery?.documents || null;
    const contractDoc = documents?.contract || null;
    const consentDocs = Array.isArray(documents?.consents) ? documents.consents : [];

    container.innerHTML = `
        <div class="min-vh-100 bg-light">
            <div class="container py-4">
                <div class="d-flex align-items-center justify-content-between mb-3" style="gap: 1rem; flex-wrap: wrap;">
                    <div class="d-flex align-items-center" style="gap: .75rem;">
                        <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 34px; width: auto;" />
                        <i id="loginBrandIcon" class="bi bi-camera-fill fs-3 text-success"></i>
                        <span id="loginBrandText" class="fw-semibold"></span>
                    </div>
                    <div class="d-flex align-items-center" style="gap: .5rem; flex-wrap: wrap;">
                        ${galleryBadges(gallery)}
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
                                    ${canSelect ? `<span class="badge bg-light text-dark">Wybrane: ${selectedCount ?? '-'}${maxSelections ? ` / ${maxSelections}` : ''}</span>` : ''}
                                    ${canSelect && atMaxSelections ? `<span class="badge bg-warning text-dark">Osiągnięto limit wyboru</span>` : ''}
                                    <span class="badge bg-light text-dark">Status płatności: ${gallery?.invoice_paid ? 'opłacone' : 'nieopłacone'}</span>
                                </div>
                            </div>
                            <div class="d-flex" style="gap: .5rem;">
                                ${downloadVisible ? `<button class="btn btn-primary" id="galleryDownloadBtn"><i class="bi bi-download"></i> Download</button>` : ''}
                                <button class="btn btn-outline-secondary" id="galleryLogoutBtn"><i class="bi bi-lock"></i> Zmień PIN</button>
                            </div>
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
                                        data-photo-id="${photo.id}" data-next-selected="${selected ? 'false' : 'true'}">
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
                                                 data-open-photo-id="${photo.id}"
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

    // Branding
    (async () => { try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ } })();

    // Download ZIP
    const downloadBtn = document.getElementById('galleryDownloadBtn');
    downloadBtn?.addEventListener('click', async () => {
        try {
            const res = await apiDownload(`/gallery/${encodeURIComponent(publicHash)}/download`, {
                skipAuth: true,
                headers: { Authorization: `Bearer ${token}` },
                showErrors: true,
            });
            if (!res) return;

            const url = window.URL.createObjectURL(res.blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = res.filename || `gallery_${publicHash}.zip`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            console.error(e);
        }
    });

    // Documents downloads
    const contractBtn = document.getElementById('publicDownloadContractBtn');
    contractBtn?.addEventListener('click', async () => {
        try {
            const res = await apiDownload(`/gallery/${encodeURIComponent(publicHash)}/contract-scan`, {
                skipAuth: true,
                headers: { Authorization: `Bearer ${token}` },
                showErrors: true,
            });
            if (!res?.blob) return;
            const url = URL.createObjectURL(res.blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = res.filename || 'contract_scan';
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
                const url = btn.getAttribute('data-consent-url') || '';
                if (!url) {
                    showToast('Brak linku do pliku', 'warning');
                    return;
                }
                const apiPath = url.startsWith('/api') ? url.replace('/api', '') : url;
                const res = await apiDownload(apiPath, {
                    skipAuth: true,
                    headers: { Authorization: `Bearer ${token}` },
                    showErrors: true,
                });
                if (!res?.blob) return;
                const blobUrl = URL.createObjectURL(res.blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = res.filename || 'consent_scan';
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

    // Logout / change PIN
    document.getElementById('galleryLogoutBtn')?.addEventListener('click', async () => {
        clearGalleryToken(publicHash);
        await loadAndRender(publicHash);
    });

    // Open photo modal
    container.querySelectorAll('[data-open-photo-id]')?.forEach(el => {
        el.addEventListener('click', () => openPhotoModal(Number(el.getAttribute('data-open-photo-id'))));
    });

    function openPhotoModal(photoId) {
        const filename = gallery?.photos?.find?.(p => p.id === photoId)?.filename || '';
        const titleEl = document.getElementById('publicPhotoModalTitle');
        const bodyEl = document.getElementById('publicPhotoModalBody');
        const footerEl = document.getElementById('publicPhotoModalFooter');
        if (titleEl) titleEl.textContent = filename || `Zdjęcie #${photoId}`;
        if (bodyEl) {
            bodyEl.innerHTML = `<img src="/api/photos/${photoId}/download?version=watermarked" class="img-fluid" alt="${filename || ''}">`;
        }

        const canDownloadOriginal = Boolean(gallery?.download_available);
        if (footerEl) {
            footerEl.innerHTML = `
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
                    const res = await apiDownload(`/photos/${photoId}/download?version=original`, {
                        skipAuth: true,
                        headers: { Authorization: `Bearer ${token}` },
                        showErrors: true,
                    });
                    if (!res?.blob) return;
                    const blobUrl = URL.createObjectURL(res.blob);
                    const a = document.createElement('a');
                    a.href = blobUrl;
                    a.download = res.filename || filename || `photo_${photoId}`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(blobUrl);
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
    }

    // Selection buttons
    container.querySelectorAll('button[data-photo-id]')?.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const photoId = Number(btn.getAttribute('data-photo-id'));
            const nextSelected = btn.getAttribute('data-next-selected') === 'true';

            try {
                await apiRequest(`/photos/${photoId}/toggle-selection`, {
                    method: 'POST',
                    skipAuth: true,
                    showErrors: true,
                    headers: { Authorization: `Bearer ${token}` },
                    body: { is_selected: nextSelected },
                });
                await loadAndRender(publicHash);
            } catch (err) {
                console.error(err);
            }
        });
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

async function loadAndRender(publicHash, opts = {}) {
    const container = getVisibleContainer();
    renderLoading(container);

    // Apply branding (uses login* IDs in rendered templates)
    try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }

    let token = getStoredGalleryToken(publicHash);

    // If user submitted PIN, verify it first.
    if (opts?.pin) {
        try {
            const resp = await verifyPin(publicHash, opts.pin);
            const accessToken = resp?.data?.access_token;
            if (!accessToken) throw new Error('Brak tokenu');
            storeGalleryToken(publicHash, accessToken);
            token = accessToken;
        } catch (e) {
            const msg = e?.message || 'Nieprawidłowy PIN';
            // Load minimal meta for the prompt.
            const metaResp = await fetchPublicGallery(publicHash, null).catch(() => null);
            const meta = metaResp?.data || {};
            renderPinPrompt(container, meta, publicHash, msg);
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }
    }

    // Load gallery.
    try {
        const resp = await fetchPublicGallery(publicHash, token);
        const data = resp?.data;

        if (!data) {
            renderError(container, 'Nie udało się załadować galerii');
            return;
        }

        if (data.requires_pin) {
            renderPinPrompt(container, data, publicHash);
            try { await applyBranding({ context: 'gallery' }); } catch (_) { /* ignore */ }
            return;
        }

        renderGallery(container, data, publicHash, token);
    } catch (e) {
        console.error(e);
        clearGalleryToken(publicHash);
        renderError(container, e?.message || 'Nie udało się załadować galerii');
    }
}

export async function renderGalleryPublic(params) {
    const publicHash = params?.[0];
    if (!publicHash) {
        showToast('Brak identyfikatora galerii', 'warning');
        return;
    }

    await loadAndRender(publicHash);
}

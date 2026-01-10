/**
 * Galleries View - Zarządzanie galeriami zdjęć
 */

import { galleriesAPI, jobsAPI } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { validateRequiredFields, wireClearOnInput } from '../forms.js';
import { confirmDialog } from '../confirm.js';

let currentPage = 1;
let currentFilters = {};

export async function renderGalleries(params) {
    const container = document.getElementById('viewContainer');
    
    // Check if viewing gallery for specific job
    if (params && params[0] === 'job' && params[1]) {
        return renderGalleryForJob(parseInt(params[1]));
    }
    
    if (params && params[0] === 'new') {
        return renderGalleryForm(null);
    }

    // Edit route: #/galleries/<id>/edit
    if (params && params[0] && params[1] === 'edit') {
        return renderGalleryForm(parseInt(params[0]));
    }
    
    if (params && params[0]) {
        return renderGalleryDetails(parseInt(params[0]));
    }
    
    // Show loading
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-images"></i> Galerie</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await galleriesAPI.getAll(currentFilters, currentPage, 25);
        const galleries = response.data || [];
        const pagination = response.pagination || { page: 1, pages: 1, total: galleries.length || 0 };
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-images"></i> Galerie</h1>
                    <p class="text-muted mb-0">Zarządzanie galeriami zdjęć</p>
                </div>
                <div>
                    <button class="btn btn-success" onclick="window.location.hash='#/galleries/new'">
                        <i class="bi bi-plus-lg"></i> Nowa galeria
                    </button>
                </div>
            </div>
            
            <!-- Filters -->
            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <select class="form-select" id="typeFilter">
                                <option value="">Wszystkie typy</option>
                                <option value="proof" ${currentFilters.gallery_type === 'proof' ? 'selected' : ''}>Proof</option>
                                <option value="selection" ${currentFilters.gallery_type === 'selection' ? 'selected' : ''}>Selection</option>
                                <option value="final" ${currentFilters.gallery_type === 'final' ? 'selected' : ''}>Final</option>
                                <option value="archive" ${currentFilters.gallery_type === 'archive' ? 'selected' : ''}>Archive</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="statusFilter">
                                <option value="">Wszystkie statusy</option>
                                <option value="draft" ${currentFilters.status === 'draft' ? 'selected' : ''}>Szkic</option>
                                <option value="published" ${currentFilters.status === 'published' ? 'selected' : ''}>Opublikowane</option>
                                <option value="archived" ${currentFilters.status === 'archived' ? 'selected' : ''}>Zarchiwizowane</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <button class="btn btn-outline-secondary w-100" id="resetFiltersBtn">
                                <i class="bi bi-x-circle"></i> Wyczyść filtry
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Galleries Table -->
            <div class="card">
                <div class="card-body p-0">
                    ${galleries.length === 0 ? `
                        <div class="text-center py-5">
                            <i class="bi bi-inbox display-1 text-muted"></i>
                            <p class="text-muted mt-3">Brak galerii</p>
                            <button class="btn btn-success" onclick="window.location.hash='#/galleries/new'">
                                <i class="bi bi-plus-lg"></i> Utwórz pierwszą galerię
                            </button>
                        </div>
                    ` : `
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Nazwa</th>
                                        <th>Typ</th>
                                        <th>Status</th>
                                        <th>Klient</th>
                                        <th>Zdjęcia</th>
                                        <th>Wyświetlenia</th>
                                        <th>Watermark</th>
                                        <th>Utworzono</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${galleries.map(gallery => {
                                        const customerName = gallery.job?.customer?.display_name || gallery.job?.customer?.full_name || '-';
                                        const title = gallery.name || gallery.title || '(bez nazwy)';
                                        return `
                                            <tr style="cursor: pointer;" onclick="window.location.hash='#/galleries/${gallery.id}'">
                                                <td>#${gallery.id}</td>
                                                <td><strong>${title}</strong></td>
                                                <td>
                                                    <span class="badge bg-${getGalleryTypeColor(gallery.gallery_type)}">${getGalleryTypeLabel(gallery.gallery_type)}</span>
                                                </td>
                                                <td>
                                                    <span class="badge bg-${getGalleryStatusColor(gallery.status)}">${getGalleryStatusLabel(gallery.status)}</span>
                                                </td>
                                                <td>${customerName}</td>
                                                <td>${gallery.photo_count || 0}</td>
                                                <td>${gallery.view_count || 0}</td>
                                                <td>${gallery.watermark_enabled ? 'Tak' : 'Nie'}</td>
                                                <td>${formatDateShort(gallery.created_at)}</td>
                                            </tr>
                                        `;
                                    }).join('')}
                                </tbody>
                            </table>
                        </div>

                        <!-- Pagination (footer always visible) -->
                        <div class="card-footer">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="text-muted">
                                    Strona ${pagination.page} z ${pagination.pages} (${pagination.total} galerii)
                                </div>
                                ${pagination.pages > 1 ? `
                                    <nav>
                                        <ul class="pagination mb-0">
                                            <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                                <a class="page-link" href="#" onclick="goToPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                            </li>
                                            ${Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                                                const pageNum = i + 1;
                                                return `
                                                    <li class="page-item ${pageNum === pagination.page ? 'active' : ''}">
                                                        <a class="page-link" href="#" onclick="goToPage(${pageNum}); return false;">${pageNum}</a>
                                                    </li>
                                                `;
                                            }).join('')}
                                            <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                                <a class="page-link" href="#" onclick="goToPage(${pagination.page + 1}); return false;">Następna</a>
                                            </li>
                                        </ul>
                                    </nav>
                                ` : ''}
                            </div>
                        </div>
                    `}
                </div>
            </div>
        `;
        
        setupGalleriesListeners();
        
    } catch (error) {
        console.error('Failed to load galleries:', error);
        showToast('Błąd ładowania galerii', 'danger');
    }
}

function setupGalleriesListeners() {
    document.getElementById('typeFilter')?.addEventListener('change', (e) => {
        currentFilters.gallery_type = e.target.value;
        currentPage = 1;
        renderGalleries();
    });
    
    document.getElementById('statusFilter')?.addEventListener('change', (e) => {
        currentFilters.status = e.target.value;
        currentPage = 1;
        renderGalleries();
    });
    
    document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
        currentFilters = {};
        currentPage = 1;
        renderGalleries();
    });
}

async function renderGalleryForJob(jobId) {
    const container = document.getElementById('viewContainer');
    
    try {
        // Check if galleries exist for this job
        const galleriesResponse = await galleriesAPI.getAll({ job_id: jobId }, 1, 1000);
        const existingGalleries = galleriesResponse.data || [];
        
        if (existingGalleries.length > 0) {
            // Show list of galleries for this job
            container.innerHTML = `
                <div class="page-header">
                    <div>
                        <h1><i class="bi bi-images"></i> Galerie zlecenia</h1>
                    </div>
                    <div>
                        <button class="btn btn-success" onclick="createGalleryForJob(${jobId})">
                            <i class="bi bi-plus-lg"></i> Nowa galeria
                        </button>
                        <button class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs/${jobId}'">
                            <i class="bi bi-arrow-left"></i> Zlecenie
                        </button>
                    </div>
                </div>
                
                <div class="row">
                    ${existingGalleries.map(gallery => `
                        <div class="col-md-6 col-lg-4 mb-4">
                            <div class="card" onclick="window.location.hash='#/galleries/${gallery.id}'">
                                <div class="card-header">
                                    <span class="badge bg-${getGalleryTypeColor(gallery.gallery_type)}">${getGalleryTypeLabel(gallery.gallery_type)}</span>
                                </div>
                                <div class="card-body">
                                    <h5>${gallery.name}</h5>
                                    <p><i class="bi bi-images"></i> ${gallery.photo_count || 0} zdjęć</p>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            return;
        }
        
        // No galleries - show creation form
        navigate(`/galleries/new?job=${jobId}`);
        
    } catch (error) {
        console.error('Failed to load galleries for job:', error);
        showToast('Błąd ładowania galerii', 'danger');
        navigate('/jobs');
    }
}

// Global function for inline pagination handlers
window.goToPage = (page) => {
    currentPage = page;
    renderGalleries();
};

window.createGalleryForJob = (jobId) => {
    navigate(`/galleries/new?job=${jobId}`);
};

async function renderGalleryForm(galleryId) {
    const container = document.getElementById('viewContainer');
    const isEdit = galleryId !== null;
    
    // Get job_id from URL if present
    const urlParams = new URLSearchParams(window.location.hash.split('?')[1]);
    const jobId = urlParams.get('job');
    
    let gallery = null;
    let jobs = [];
    
    try {
        // Load jobs for selection
        const jobsResponse = await jobsAPI.getAll({ status: 'confirmed,in_progress,completed', per_page: 1000 });
        jobs = jobsResponse.data || [];
        
        if (isEdit) {
            const response = await galleriesAPI.getById(galleryId);
            gallery = response.data;
        }
        
    } catch (error) {
        showToast('Błąd ładowania danych', 'danger');
        navigate('/galleries');
        return;
    }

    const isTypeLocked = Boolean(
        isEdit && gallery && (
            gallery.status !== 'draft' ||
            (gallery.photo_count || 0) > 0 ||
            (gallery.selected_count || 0) > 0
        )
    );
    
    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-${isEdit ? 'pencil' : 'plus-lg'}"></i> ${isEdit ? 'Edytuj galerię' : 'Nowa galeria'}</h1>
            </div>
            <div>
                <button class="btn btn-outline-secondary" onclick="window.location.hash='#/galleries'">
                    <i class="bi bi-arrow-left"></i> Powrót
                </button>
            </div>
        </div>
        
        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-body">
                        <form id="galleryForm" novalidate>
                            <div class="mb-3">
                                <label for="jobId" class="form-label">Zlecenie *</label>
                                <select class="form-select" id="jobId" name="job_id" required ${isEdit ? 'disabled' : ''}>
                                    <option value="">-- Wybierz --</option>
                                    ${jobs.map(job => `
                                        <option value="${job.id}" 
                                                ${(gallery?.job_id === job.id || parseInt(jobId) === job.id) ? 'selected' : ''}>
                                            #${job.id} - ${job.customer?.display_name} (${formatDateShort(job.event_date)})
                                        </option>
                                    `).join('')}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label for="name" class="form-label">Nazwa galerii *</label>
                                <input type="text" class="form-control" id="name" name="name" 
                                       value="${gallery?.name || ''}" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="galleryType" class="form-label">Typ galerii *</label>
                                <select class="form-select" id="galleryType" name="gallery_type" required ${isTypeLocked ? 'disabled' : ''}>
                                    <option value="proof" ${!gallery || gallery.gallery_type === 'proof' ? 'selected' : ''}>
                                        Proof - przeglądowa
                                    </option>
                                    <option value="selection" ${gallery?.gallery_type === 'selection' ? 'selected' : ''}>
                                        Selection - do wyboru przez klienta
                                    </option>
                                    <option value="final" ${gallery?.gallery_type === 'final' ? 'selected' : ''}>
                                        Final - ostateczne zdjęcia
                                    </option>
                                    <option value="archive" ${gallery?.gallery_type === 'archive' ? 'selected' : ''}>
                                        Archive - archiwum
                                    </option>
                                </select>
                                ${isTypeLocked ? '<div class="form-text">Typ można zmienić tylko dla szkicu bez zdjęć i bez wyborów klienta.</div>' : ''}
                            </div>
                            
                            <div class="mb-3">
                                <label for="description" class="form-label">Opis</label>
                                <textarea class="form-control" id="description" name="description" rows="3">${gallery?.description || ''}</textarea>
                            </div>
                            
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label for="expiresAt" class="form-label">Data wygaśnięcia</label>
                                    <input type="date" class="form-control" id="expiresAt" name="expires_at"
                                           value="${gallery?.expires_at ? new Date(gallery.expires_at).toISOString().split('T')[0] : ''}">
                                </div>
                                <div class="col-md-6">
                                    <label for="maxSelections" class="form-label">Max wybór zdjęć</label>
                                    <input type="number" class="form-control" id="maxSelections" name="max_selections"
                                           value="${gallery?.max_selections || ''}" min="0">
                                </div>
                            </div>
                            
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="checkbox" id="watermarkEnabled" name="watermark_enabled"
                                       ${!gallery || gallery.watermark_enabled ? 'checked' : ''}>
                                <label class="form-check-label" for="watermarkEnabled">
                                    Włącz watermark
                                </label>
                            </div>
                            
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="checkbox" id="allowDownload" name="allow_download"
                                       ${gallery?.allow_download ? 'checked' : ''}>
                                <label class="form-check-label" for="allowDownload">
                                    Zezwól na pobieranie
                                </label>
                            </div>
                            
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-check-lg"></i> ${isEdit ? 'Zapisz zmiany' : 'Utwórz galerię'}
                                </button>
                                <button type="button" class="btn btn-outline-secondary" onclick="window.location.hash='#/galleries'">
                                    Anuluj
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-info-circle"></i> Typy galerii</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Proof:</strong> Galeria przeglądowa dla klienta z watermarkami.</p>
                        <p><strong>Selection:</strong> Klient wybiera swoje ulubione zdjęcia.</p>
                        <p><strong>Final:</strong> Ostateczne zdjęcia do pobrania (wymaga pełnej płatności).</p>
                        <p><strong>Archive:</strong> Archiwum (bez wyboru i pobierania).</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Setup form
    const form = document.getElementById('galleryForm');
    wireClearOnInput(form);
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!validateRequiredFields(form)) {
            return;
        }
        
        const formData = new FormData(form);
        const galleryTypeValue = formData.get('gallery_type');
        const data = {
            job_id: isEdit ? gallery?.job_id : (parseInt(formData.get('job_id')) || parseInt(jobId)),
            name: formData.get('name'),
            description: formData.get('description') || null,
            expires_at: formData.get('expires_at') || null,
            max_selections: formData.get('max_selections') ? parseInt(formData.get('max_selections')) : null,
            watermark_enabled: formData.get('watermark_enabled') === 'on',
            allow_download: formData.get('allow_download') === 'on',
        };

        // Disabled inputs are not included in FormData, so avoid sending null.
        // For create, gallery_type is required; for edit, include only if present.
        if (!isEdit || (galleryTypeValue !== null && galleryTypeValue !== undefined && String(galleryTypeValue).trim() !== '')) {
            data.gallery_type = galleryTypeValue;
        }
        
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Zapisywanie...';
        
        try {
            if (isEdit) {
                await galleriesAPI.update(galleryId, data, { showErrors: false });
                navigate(`/galleries/${galleryId}`);
            } else {
                const response = await galleriesAPI.create(data, { showErrors: false });
                navigate(`/galleries/${response.data.id}`);
            }
        } catch (error) {
            console.error('Failed to save gallery:', error);

            // Prefer marshmallow validation errors when present.
            const payload = error?.payload;
            const fieldErrors = payload?.errors;
            if (fieldErrors && typeof fieldErrors === 'object') {
                const parts = Object.entries(fieldErrors)
                    .flatMap(([field, msgs]) => {
                        if (Array.isArray(msgs)) return msgs.map(m => `${field}: ${m}`);
                        if (typeof msgs === 'string') return [`${field}: ${msgs}`];
                        return [];
                    });
                if (parts.length) {
                    showToast(parts.join(' | '), 'danger');
                } else {
                    showToast(error?.message || 'Nie udało się zapisać galerii', 'danger');
                }
            } else {
                showToast(error?.message || 'Nie udało się zapisać galerii', 'danger');
            }

            submitBtn.disabled = false;
            submitBtn.innerHTML = `<i class="bi bi-check-lg"></i> ${isEdit ? 'Zapisz zmiany' : 'Utwórz galerię'}`;
        }
    });
}

async function renderGalleryDetails(galleryId) {
    const container = document.getElementById('viewContainer');
    
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await galleriesAPI.getById(galleryId);
        const gallery = response.data;
        const storedPin = getStoredGalleryPin(gallery.id);
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-images"></i> ${gallery.name}</h1>
                    <span class="badge bg-${getGalleryTypeColor(gallery.gallery_type)} me-2">${getGalleryTypeLabel(gallery.gallery_type)}</span>
                    <span class="badge bg-${getGalleryStatusColor(gallery.status)}">${getGalleryStatusLabel(gallery.status)}</span>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/galleries/${gallery.id}/edit'">
                        <i class="bi bi-pencil"></i> Edytuj
                    </button>
                    ${gallery.status === 'draft' ? `
                        <button class="btn btn-success" onclick="publishGallery(${gallery.id})">
                            <i class="bi bi-upload"></i> Opublikuj
                        </button>
                    ` : ''}
                    ${gallery.status === 'published' ? `
                        <button class="btn btn-primary" onclick="sendGalleryLink(${gallery.id})">
                            <i class="bi bi-send"></i> Wyślij link
                        </button>
                    ` : ''}
                    <button class="btn btn-outline-primary" onclick="window.location.hash='#/photos?gallery=${gallery.id}'">
                        <i class="bi bi-camera"></i> Zdjęcia
                    </button>
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/galleries'">
                        <i class="bi bi-arrow-left"></i> Lista
                    </button>
                </div>
            </div>
            
            <div class="row">
                <div class="col-lg-8">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-info-circle"></i> Informacje</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Nazwa:</strong> ${gallery.name}</p>
                            <div class="row g-2 align-items-center mb-2">
                                <div class="col-auto"><strong>Typ:</strong></div>
                                <div class="col-auto" style="min-width: 220px;">
                                    <select class="form-select form-select-sm" id="galleryTypeSelect">
                                        <option value="proof" ${gallery.gallery_type === 'proof' ? 'selected' : ''}>Proof</option>
                                        <option value="selection" ${gallery.gallery_type === 'selection' ? 'selected' : ''}>Selection</option>
                                        <option value="final" ${gallery.gallery_type === 'final' ? 'selected' : ''}>Final</option>
                                        <option value="archive" ${gallery.gallery_type === 'archive' ? 'selected' : ''}>Archive</option>
                                    </select>
                                </div>
                                <div class="col-auto">
                                    <button class="btn btn-outline-secondary btn-sm" onclick="changeGalleryType(${gallery.id})">
                                        <i class="bi bi-arrow-repeat"></i> Zmień
                                    </button>
                                </div>
                            </div>
                            <div class="text-muted small mb-2">
                                <div><strong>Proof</strong> – podgląd z watermarkiem, bez plików full‑res.</div>
                                <div><strong>Selection</strong> – etap wyboru zdjęć przez klienta.</div>
                                <div><strong>Final</strong> – galeria końcowa (“finished”); tu docelowo udostępnia się materiały po spełnieniu warunków (płatność, ukończenie, watermark off, allow_download).</div>
                                <div><strong>Archive</strong> – archiwum; nie jest dostępne dla klienta pod linkiem publicznym.</div>
                            </div>
                            <p><strong>Opis:</strong> ${gallery.description || '-'}</p>
                            <p><strong>Zdjęć:</strong> ${gallery.photo_count || 0}</p>
                            <p><strong>Wyświetleń:</strong> ${gallery.view_count || 0}</p>
                            ${gallery.expires_at ? `<p><strong>Wygasa:</strong> ${formatDate(gallery.expires_at)}</p>` : ''}
                            ${gallery.max_selections ? `<p><strong>Max wybór:</strong> ${gallery.max_selections}</p>` : ''}
                        </div>
                    </div>
                    
                    ${gallery.status === 'published' && (gallery.public_hash || gallery.access_token) ? `
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="bi bi-link-45deg"></i> Link dla klienta</h5>
                            </div>
                            <div class="card-body">
                                <div class="input-group">
                                    <input type="text" class="form-control" id="galleryLink" 
                                           value="${gallery.public_hash ? `${window.location.origin}/g/${gallery.public_hash}` : `${window.location.origin}/galleries/access/${gallery.access_token}`}" readonly>
                                    <button class="btn btn-outline-secondary" onclick="copyGalleryLink()">
                                        <i class="bi bi-clipboard"></i> Kopiuj
                                    </button>
                                </div>

                                <div class="input-group mt-2">
                                    <input type="text" class="form-control" id="galleryPin"
                                           value="${storedPin || ''}" placeholder="PIN (kliknij 'Wyślij link', aby wygenerować)" readonly>
                                    <button class="btn btn-outline-secondary" onclick="copyGalleryPin()" ${storedPin ? '' : 'disabled'}>
                                        <i class="bi bi-clipboard"></i> Kopiuj PIN
                                    </button>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                <div class="col-lg-4">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-gear"></i> Ustawienia</h5>
                        </div>
                        <div class="card-body">
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" ${gallery.watermark_enabled ? 'checked' : ''} disabled>
                                <label class="form-check-label">Watermark</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" ${gallery.allow_download ? 'checked' : ''} disabled>
                                <label class="form-check-label">Pobieranie</label>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-briefcase"></i> Zlecenie</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>#${gallery.job?.id}</strong></p>
                            <p>${gallery.job?.customer?.display_name}</p>
                            <a href="#/jobs/${gallery.job?.id || gallery.job_id}" class="btn btn-sm btn-outline-primary">
                                Zobacz zlecenie
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to load gallery:', error);
        showToast('Nie znaleziono galerii', 'danger');
        navigate('/galleries');
    }
}

window.publishGallery = async (galleryId) => {
    const ok = await confirmDialog({
        title: 'Opublikuj galerię',
        message: 'Czy na pewno chcesz opublikować tę galerię? Klient otrzyma dostęp.',
        confirmText: 'Opublikuj',
        cancelText: 'Anuluj',
        danger: true,
    });
    if (!ok) {
        return;
    }
    
    try {
        await galleriesAPI.publish(galleryId);
        renderGalleryDetails(galleryId);
    } catch (error) {
        console.error('Failed to publish gallery:', error);
    }
};

window.sendGalleryLink = async (galleryId) => {
    try {
        const resp = await galleriesAPI.sendAccess(galleryId);
        const pin = resp?.data?.pin;
        const link = resp?.data?.link ? `${window.location.origin}${resp.data.link}` : null;

        if (link) {
            const input = document.getElementById('galleryLink');
            if (input) input.value = link;
        }

        if (pin) {
            setStoredGalleryPin(galleryId, pin);

            const pinInput = document.getElementById('galleryPin');
            if (pinInput) {
                pinInput.value = pin;
            }

            const pinCopyBtn = document.querySelector("button[onclick='copyGalleryPin()']");
            if (pinCopyBtn) {
                pinCopyBtn.disabled = false;
            }
            showToast(`PIN: ${pin}`, 'success');
        } else {
            showToast('Dostęp do galerii przygotowany', 'success');
        }
    } catch (error) {
        console.error('Failed to send gallery link:', error);
    }
};

window.copyGalleryLink = () => {
    const input = document.getElementById('galleryLink');
    input.select();
    document.execCommand('copy');
    showToast('Link skopiowany', 'success');
};

window.copyGalleryPin = () => {
    const input = document.getElementById('galleryPin');
    if (!input || !input.value) {
        showToast('Brak PIN-u do skopiowania', 'warning');
        return;
    }
    input.select();
    document.execCommand('copy');
    showToast('PIN skopiowany', 'success');
};

window.changeGalleryType = async (galleryId) => {
    const select = document.getElementById('galleryTypeSelect');
    const newType = (select?.value || '').trim();
    if (!newType) {
        showToast('Wybierz typ galerii', 'warning');
        return;
    }

    const ok = await confirmDialog({
        title: 'Zmień typ galerii',
        message: `Zmień typ na: ${newType.toUpperCase()}?`,
        confirmText: 'Zmień',
        cancelText: 'Anuluj',
        danger: false,
    });
    if (!ok) return;

    try {
        await galleriesAPI.patchType(galleryId, newType, { successMessage: 'Typ galerii zaktualizowany' });
        await renderGalleryDetails(galleryId);
    } catch (error) {
        console.error('Failed to patch gallery type:', error);
    }
};

function getStoredGalleryPin(galleryId) {
    try {
        return localStorage.getItem(`gallery_pin_${galleryId}`);
    } catch (_) {
        return null;
    }
}

function setStoredGalleryPin(galleryId, pin) {
    try {
        if (!pin) return;
        localStorage.setItem(`gallery_pin_${galleryId}`, String(pin));
    } catch (_) {
        // Ignore storage errors (private mode, disabled storage, etc.)
    }
}

function getGalleryTypeColor(type) {
    const colors = {
        'proof': 'info',
        'selection': 'warning',
        'final': 'success',
        'archive': 'secondary',
    };
    return colors[type] || 'secondary';
}

function getGalleryTypeLabel(type) {
    const labels = {
        'proof': 'Proof',
        'selection': 'Selection',
        'final': 'Final',
        'archive': 'Archive',
    };
    return labels[type] || type;
}

function getGalleryStatusColor(status) {
    const colors = {
        'draft': 'secondary',
        'published': 'success',
        'archived': 'dark',
    };
    return colors[status] || 'secondary';
}

function getGalleryStatusLabel(status) {
    const labels = {
        'draft': 'Szkic',
        'published': 'Opublikowane',
        'archived': 'Zarchiwizowane',
    };
    return labels[status] || status;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('pl-PL', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function formatDateShort(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('pl-PL');
}

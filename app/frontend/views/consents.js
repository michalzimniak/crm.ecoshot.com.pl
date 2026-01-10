/**
 * Consents View - Zgody (np. publikacja wizerunku)
 *
 * Backend supports:
 * - GET  /api/consents/<id>
 * - GET  /api/consents/job/<job_id>
 * - POST /api/consents
 * - POST /api/consents/<id>/send
 * - POST /api/consents/<id>/signed-scan   (multipart field: file)
 * - GET  /api/consents/<id>/pdf
 */

import { consentsAPI, jobsAPI, apiDownload } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';

let currentJobId = null;
let currentPage = 1;
let currentFilters = {};

const consentTemplateCache = new Map();

export async function renderConsents(params) {
    const container = document.getElementById('viewContainer');

    // Routes:
    // - #/consents                 => picker + list (if selected)
    // - #/consents/job/<job_id>    => list for job
    // - #/consents/<consent_id>    => details
    if (params?.[0] === 'job' && params?.[1]) {
        currentJobId = parseInt(params[1], 10);
        return renderConsentsForJob(currentJobId);
    }

    if (params?.[0]) {
        const consentId = parseInt(params[0], 10);
        if (Number.isFinite(consentId)) {
            return renderConsentDetails(consentId);
        }
    }

    // Default view
    currentJobId = currentJobId || null;
    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-shield-check"></i> Zgody</h1>
                <p class="text-muted mb-0">Zgody powiązane ze zleceniami (np. publikacja wizerunku)</p>
            </div>
            <div>
                <button class="btn btn-success" id="openConsentCreateBtn">
                    <i class="bi bi-plus-lg"></i> Nowa zgoda
                </button>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-body">
                <div class="row g-3 align-items-end">
                    <div class="col-md-4">
                        <label class="form-label">Zlecenie</label>
                        <select class="form-select" id="consentsJobSelect">
                            <option value="">Wybierz zlecenie…</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <button class="btn btn-outline-primary w-100" id="loadConsentsBtn">
                            <i class="bi bi-search"></i> Pokaż zgody
                        </button>
                    </div>
                    <div class="col-md-4">
                        <button class="btn btn-outline-secondary w-100" id="clearConsentsBtn">
                            <i class="bi bi-x-circle"></i> Wyczyść
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div id="consentsListContainer" class="card">
            <div class="card-body text-center py-5">
                <div class="spinner-border text-success" role="status"></div>
            </div>
        </div>

        <!-- Create Consent Modal -->
        <div class="modal fade" id="consentCreateModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="bi bi-plus-lg"></i> Nowa zgoda</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="consentCreateForm" class="row g-3" novalidate>
                            <div class="col-md-6">
                                <label class="form-label">Zlecenie</label>
                                <select class="form-select" id="createConsentJobId" required>
                                    <option value="">Ładowanie…</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Typ zgody</label>
                                <select class="form-select" id="createConsentType" required>
                                    <option value="image_publication" selected>Publikacja wizerunku</option>
                                    <option value="data_processing">Przetwarzanie danych</option>
                                    <option value="marketing">Marketing</option>
                                </select>
                            </div>
                            <div class="col-12">
                                <label class="form-label">Zakres (opcjonalnie)</label>
                                <input class="form-control" id="createConsentScope" placeholder="np. social media, strona www">
                            </div>
                            <div class="col-12">
                                <label class="form-label">Uwagi (opcjonalnie)</label>
                                <textarea class="form-control" id="createConsentNotes" rows="2"></textarea>
                            </div>
                            <div class="col-12">
                                <label class="form-label">Treść zgody</label>
                                <textarea class="form-control" id="createConsentText" rows="6" placeholder="Dla publikacji wizerunku oraz przetwarzania danych może pozostać puste (backend wstawi domyślną treść)."></textarea>
                                <div class="form-text">
                                    Dla typów innych niż publikacja wizerunku i przetwarzanie danych treść jest wymagana.
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="submit" class="btn btn-success" form="consentCreateForm">
                            <i class="bi bi-check2"></i> Zapisz
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    await populateJobsSelects();
    setupConsentsHomeListeners();

    // Show all consents by default
    currentFilters = {};
    currentPage = 1;
    await loadConsentsList();
}

async function loadConsentsList() {
    const container = document.getElementById('consentsListContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="card-body text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const res = await consentsAPI.getAll(currentFilters, currentPage);
        const consents = res?.data || [];
        const pagination = res?.pagination || { page: 1, pages: 1, total: consents.length };

        container.innerHTML = renderConsentsTable(consents, pagination);
        setupConsentActions();
    } catch (err) {
        console.error(err);
        container.innerHTML = `
            <div class="card-body text-center py-5 text-muted">
                Nie udało się załadować zgód.
            </div>
        `;
    }
}

function renderConsentsTable(consents, pagination) {
    const header = `
        <div class="card-header d-flex justify-content-between align-items-center">
            <div>
                <strong>Lista zgód</strong>
                <span class="text-muted"> (${pagination.total || consents.length})</span>
            </div>
        </div>
    `;

    if (!consents || consents.length === 0) {
        return `${header}<div class="card-body text-center py-5 text-muted">Brak zgód</div>`;
    }

    const table = `
        <div class="table-responsive">
            <table class="table table-hover mb-0">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Zlecenie</th>
                        <th>Typ</th>
                        <th>Status</th>
                        <th>Zakres</th>
                        <th>Utworzono</th>
                        <th>Akcje</th>
                    </tr>
                </thead>
                <tbody>
                    ${consents.map(c => `
                        <tr style="cursor:pointer" onclick="window.location.hash='#/consents/${c.id}'">
                            <td><strong>#${c.id}</strong></td>
                            <td>#${(c.job_id ?? c.job?.id ?? '—')}</td>
                            <td>${consentTypeLabel(c.consent_type)}</td>
                            <td>
                                <div class="d-flex flex-wrap gap-1">
                                    <span class="badge bg-${consentStatusColor(c)}">${consentStatusLabel(c)}</span>
                                    ${c.has_signature ? `
                                        <span class="badge bg-info text-dark" title="Podpis elektroniczny">
                                            <i class="bi bi-pen"></i> podpis
                                        </span>
                                    ` : ''}
                                    ${c.has_signed_scan ? `
                                        <span class="badge bg-primary" title="Wgrany skan podpisanej zgody">
                                            <i class="bi bi-file-earmark-check"></i> skan
                                        </span>
                                    ` : ''}
                                </div>
                            </td>
                            <td>${c.scope || '—'}</td>
                            <td>${formatDateTime(c.created_at)}</td>
                            <td onclick="event.stopPropagation();">
                                <div class="btn-group btn-group-sm">
                                    <button class="btn btn-outline-primary" onclick="window.openConsentPdf(${c.id});">
                                        <i class="bi bi-file-pdf"></i>
                                    </button>
                                    <button class="btn btn-outline-secondary" onclick="window.sendConsent(${c.id});">
                                        <i class="bi bi-send"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;

    const pager = `
        <div class="card-footer d-flex justify-content-between align-items-center">
            <div class="text-muted">Strona ${pagination.page} z ${pagination.pages} (${pagination.total ?? consents.length} zgód)</div>
            ${(pagination.pages && pagination.pages > 1)
                ? `
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-secondary" ${pagination.page === 1 ? 'disabled' : ''} onclick="window.goToConsentsPage(${pagination.page - 1});">Poprzednia</button>
                        <button class="btn btn-outline-secondary" ${pagination.page === pagination.pages ? 'disabled' : ''} onclick="window.goToConsentsPage(${pagination.page + 1});">Następna</button>
                    </div>
                `
                : ''}
        </div>
    `;

    return `${header}${table}${pager}`;
}

async function renderConsentsForJob(jobId) {
    const container = document.getElementById('viewContainer');

    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-shield-check"></i> Zgody</h1>
                <p class="text-muted mb-0">Zlecenie #${jobId}</p>
            </div>
            <div class="btn-group">
                <button class="btn btn-success" onclick="window.openConsentCreateModal(${jobId});">
                    <i class="bi bi-plus-lg"></i> Nowa zgoda
                </button>
                <button class="btn btn-outline-secondary" onclick="window.location.hash='#/consents'">
                    <i class="bi bi-arrow-left"></i> Wybór zlecenia
                </button>
            </div>
        </div>

        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>

        <!-- Create Consent Modal (reused) -->
        <div class="modal fade" id="consentCreateModal" tabindex="-1" aria-hidden="true"></div>
    `;

    try {
        // Prefer the paginated list endpoint for consistency
        const res = await consentsAPI.getAll({ job_id: jobId }, 1);
        const consents = res?.data || [];
        const pagination = res?.pagination || { page: 1, pages: 1, total: consents.length };

        // Inject modal skeleton (same markup as in home view)
        injectCreateModalMarkup(container);
        await populateJobsSelects(jobId);

        const listHtml = renderConsentsTable(
            consents.map(c => ({ ...c, job_id: c.job_id || jobId })),
            pagination
        );

        container.querySelector('.spinner-border')?.closest('.text-center')?.remove();
        container.insertAdjacentHTML('beforeend', listHtml);

        setupConsentActions();

    } catch (err) {
        console.error(err);
        showToast('Błąd ładowania zgód', 'danger');
        navigate('/consents');
    }
}

async function renderConsentDetails(consentId) {
    const container = document.getElementById('viewContainer');

    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const res = await consentsAPI.getById(consentId);
        const c = res?.data;
        if (!c) throw new Error('Consent missing');

        currentJobId = c.job_id;

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-shield-check"></i> Zgoda #${c.id}</h1>
                    <div class="text-muted">Zlecenie #${c.job_id} • ${consentTypeLabel(c.consent_type)}</div>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-primary" onclick="window.openConsentPdf(${c.id});">
                        <i class="bi bi-file-pdf"></i> PDF
                    </button>
                    <button class="btn btn-outline-secondary" onclick="window.sendConsent(${c.id});">
                        <i class="bi bi-send"></i> Wyślij
                    </button>
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/consents/job/${c.job_id}'">
                        <i class="bi bi-arrow-left"></i> Lista
                    </button>
                </div>
            </div>

            <div class="row">
                <div class="col-lg-7">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">Szczegóły</h5>
                        </div>
                        <div class="card-body">
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <div class="text-muted">Status</div>
                                    <div>
                                        <span class="badge bg-${consentStatusColor(c)} fs-6">${consentStatusLabel(c)}</span>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="text-muted">Zakres</div>
                                    <div>${c.scope || '—'}</div>
                                </div>
                                <div class="col-12">
                                    <div class="text-muted">Uwagi</div>
                                    <div>${c.notes || '—'}</div>
                                </div>
                                <div class="col-12">
                                    <div class="text-muted">Treść</div>
                                    <pre class="bg-light p-3 rounded mb-0" style="white-space:pre-wrap;">${escapeHtml(c.consent_text || '')}</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-lg-5">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">Pliki i podpis</h5>
                        </div>
                        <div class="card-body">
                            <div class="d-flex justify-content-between mb-2">
                                <span>Podpis elektroniczny:</span>
                                <strong>${c.has_signature ? 'tak' : 'nie'}</strong>
                            </div>
                            <div class="d-flex justify-content-between mb-2">
                                <span>Skan podpisany:</span>
                                <strong>${c.has_signed_scan ? 'tak' : 'nie'}</strong>
                            </div>
                            ${c.has_signed_scan ? `
                                <button class="btn btn-outline-primary w-100 mb-3" onclick="window.downloadConsentSignedScan(${c.id});">
                                    <i class="bi bi-download"></i> Pobierz skan
                                </button>
                                ${c.signed_scan_original_filename ? `
                                    <div class="text-muted small mb-2">Plik: ${escapeHtml(c.signed_scan_original_filename)}</div>
                                ` : ''}
                            ` : ''}
                            <hr>
                            <div>
                                <label class="form-label">Wgraj skan podpisanej zgody</label>
                                <input type="file" class="form-control" id="consentSignedScanFile" accept="image/*,application/pdf">
                                <button class="btn btn-success w-100 mt-2" onclick="window.uploadConsentSignedScan(${c.id});">
                                    <i class="bi bi-upload"></i> Wyślij skan
                                </button>
                                <div class="form-text">Po wgraniu skanu backend oznacza zgodę jako udzieloną.</div>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">Daty</h5>
                        </div>
                        <div class="card-body">
                            <div class="d-flex justify-content-between mb-2"><span>Utworzono:</span><span>${formatDateTime(c.created_at)}</span></div>
                            <div class="d-flex justify-content-between mb-2"><span>Udzielono:</span><span>${formatDateTime(c.granted_at) || '—'}</span></div>
                            <div class="d-flex justify-content-between"><span>Wycofano:</span><span>${formatDateTime(c.revoked_at) || '—'}</span></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        setupConsentActions();

    } catch (err) {
        console.error(err);
        showToast('Nie znaleziono zgody', 'danger');
        navigate('/consents');
    }
}

function setupConsentsHomeListeners() {
    document.getElementById('loadConsentsBtn')?.addEventListener('click', () => {
        const selectVal = document.getElementById('consentsJobSelect')?.value;
        const jobId = parseInt(selectVal || '', 10);

        if (!Number.isFinite(jobId)) {
            // No job => show all
            currentFilters = {};
            currentPage = 1;
            loadConsentsList();
            return;
        }

        // Use list-all endpoint filtered by job (keeps user on /consents)
        currentJobId = jobId;
        currentFilters = { job_id: jobId };
        currentPage = 1;
        loadConsentsList();
    });

    document.getElementById('clearConsentsBtn')?.addEventListener('click', () => {
        currentJobId = null;
        currentFilters = {};
        currentPage = 1;
        if (document.getElementById('consentsJobSelect')) {
            document.getElementById('consentsJobSelect').value = '';
        }
        loadConsentsList();
    });

    document.getElementById('openConsentCreateBtn')?.addEventListener('click', () => {
        window.openConsentCreateModal(currentJobId);
    });

    // Global helpers
    setupConsentActions();
    window.openConsentCreateModal = (jobId) => openCreateConsentModal(jobId);

    window.goToConsentsPage = (page) => {
        currentPage = page;
        loadConsentsList();
    };
}

function setupConsentActions() {
    window.openConsentPdf = async (consentId) => {
        const w = window.open('', '_blank');
        if (!w) {
            showToast('Przeglądarka zablokowała otwarcie nowej karty', 'warning');
            return;
        }

        try {
            const res = await apiDownload(`/consents/${consentId}/pdf`, { showLoading: true });
            if (!res?.blob) {
                w.close();
                return;
            }
            const blobUrl = URL.createObjectURL(res.blob);
            w.location = blobUrl;
            w.document.title = res.filename || `zgoda_${consentId}.pdf`;
            setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
        } catch (err) {
            console.error(err);
            try { w.close(); } catch (_) { /* ignore */ }
        }
    };

    window.sendConsent = async (consentId) => {
        try {
            await consentsAPI.send(consentId);
        } catch (err) {
            console.error(err);
        }
    };

    window.uploadConsentSignedScan = async (consentId) => {
        const input = document.getElementById('consentSignedScanFile');
        const file = input?.files?.[0];
        if (!file) {
            showToast('Wybierz plik', 'warning');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('file', file);
            await consentsAPI.uploadSignedScan(consentId, formData);
            // Refresh details view
            window.location.hash = `#/consents/${consentId}`;
        } catch (err) {
            console.error(err);
        }
    };

    window.downloadConsentSignedScan = async (consentId) => {
        try {
            const res = await apiDownload(`/consents/${consentId}/signed-scan`, { showLoading: true });
            if (!res?.blob) return;

            const blobUrl = URL.createObjectURL(res.blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = res.filename || `zgoda_${consentId}_skan`;
            document.body.appendChild(a);
            a.click();
            a.remove();

            setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
        } catch (err) {
            console.error(err);
        }
    };
}

async function openCreateConsentModal(preselectJobId = null) {
    const modalEl = document.getElementById('consentCreateModal');
    if (!modalEl) return;

    // Ensure modal has markup (in job view we inject placeholder div)
    if (!modalEl.innerHTML.trim()) {
        injectCreateModalMarkup(document.getElementById('viewContainer'));
        await populateJobsSelects(preselectJobId);
    }

    const jobSelect = document.getElementById('createConsentJobId');
    const typeSelect = document.getElementById('createConsentType');
    const textInput = document.getElementById('createConsentText');
    const scopeInput = document.getElementById('createConsentScope');
    const notesInput = document.getElementById('createConsentNotes');
    const form = document.getElementById('consentCreateForm');

    if (preselectJobId && jobSelect) {
        jobSelect.value = String(preselectJobId);
    }

    const fallbackTemplate = (type) => {
        // Fallback only (e.g. network errors). Backend is the source of truth.
        if (type === 'data_processing') {
            return (
                'ZGODA NA PRZETWARZANIE DANYCH OSOBOWYCH (RODO)\n\n'
                + 'Ja, niżej podpisany/a, wyrażam zgodę na przetwarzanie moich danych osobowych przez:\n\n'
                + 'Administrator danych:\n'
                + '[Nazwa firmy / Imię i nazwisko fotografa]\n'
                + '[Adres siedziby]\n'
                + '[NIP]\n'
                + '[E-mail]\n\n'
                + '(...)\n'
            );
        }
        if (type === 'image_publication') {
            return (
                'ZGODA NA PUBLIKACJĘ WIZERUNKU\n\n'
                + 'Wyrażam zgodę na nieodpłatne utrwalanie oraz rozpowszechnianie mojego wizerunku (...)\n'
            );
        }
        return '';
    };

    const getConsentTemplateText = async (type) => {
        if (!type || !['data_processing', 'image_publication'].includes(type)) return '';

        const selectedJobId = parseInt(jobSelect?.value || '', 10);
        const hasJob = Number.isFinite(selectedJobId);
        const cacheKey = (type === 'image_publication' && hasJob) ? `${type}:${selectedJobId}` : type;

        if (consentTemplateCache.has(cacheKey)) return consentTemplateCache.get(cacheKey);

        try {
            const params = (type === 'image_publication' && hasJob) ? { job_id: selectedJobId } : {};
            const res = await consentsAPI.getTemplate(type, params, { showErrors: false });
            const text = res?.data?.consent_text || '';
            if (text) {
                consentTemplateCache.set(cacheKey, text);
                return text;
            }
        } catch (e) {
            // ignore and fall back
        }

        const fb = fallbackTemplate(type);
        if (fb) consentTemplateCache.set(cacheKey, fb);
        return fb;
    };

    let templateReqId = 0;
    const maybeAutofillConsentText = async () => {
        const t = typeSelect.value;
        if (!['data_processing', 'image_publication'].includes(t)) return;

        const current = (textInput.value || '').trim();
        const wasAutofilled = textInput.dataset.autofilled === '1';
        if (current && !wasAutofilled) return;

        const myReq = ++templateReqId;
        const text = await getConsentTemplateText(t);
        if (myReq !== templateReqId) return; // stale
        if (!text) return;

        // Only set if still eligible
        const nowCurrent = (textInput.value || '').trim();
        const nowWasAutofilled = textInput.dataset.autofilled === '1';
        if (!nowCurrent || nowWasAutofilled) {
            textInput.value = text;
            textInput.dataset.autofilled = '1';
        }
    };

    textInput.oninput = () => {
        // If user edits, don't overwrite on next type change.
        textInput.dataset.autofilled = '0';
    };

    const updateTextRequirement = () => {
        const t = typeSelect.value;
        // Only marketing requires manual text; other types can be autogenerated.
        textInput.required = (t === 'marketing');
    };
    typeSelect.onchange = () => {
        updateTextRequirement();
        void maybeAutofillConsentText();
    };

    if (jobSelect) {
        jobSelect.onchange = () => {
            void maybeAutofillConsentText();
        };
    }
    updateTextRequirement();
    void maybeAutofillConsentText();

    form.onsubmit = async (e) => {
        e.preventDefault();

        const jobId = parseInt(jobSelect.value || '', 10);
        if (!Number.isFinite(jobId)) {
            showToast('Wybierz zlecenie', 'warning');
            return;
        }

        const consentType = typeSelect.value;
        const consentText = (textInput.value || '').trim();

        if (consentType === 'marketing' && !consentText) {
            showToast('Treść zgody jest wymagana', 'warning');
            return;
        }

        const payload = {
            job_id: jobId,
            consent_type: consentType,
        };

        const scope = (scopeInput.value || '').trim();
        const notes = (notesInput.value || '').trim();
        if (scope) payload.scope = scope;
        if (notes) payload.notes = notes;
        // If we auto-filled a template, keep backend as source-of-truth (it fills company data).
        const isTemplateType = consentType === 'image_publication' || consentType === 'data_processing';
        const wasAutofilled = textInput.dataset.autofilled === '1';
        if (consentText && !(isTemplateType && wasAutofilled)) {
            payload.consent_text = consentText;
        }

        try {
            const res = await consentsAPI.create(payload);
            const created = res?.data;
            const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            modal.hide();

            if (created?.id) {
                window.location.hash = `#/consents/${created.id}`;
            } else {
                window.location.hash = `#/consents/job/${jobId}`;
            }
        } catch (err) {
            console.error(err);
        }
    };

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}

async function populateJobsSelects(preselectJobId = null) {
    const selectHome = document.getElementById('consentsJobSelect');
    const selectCreate = document.getElementById('createConsentJobId');

    const fill = (select, jobs) => {
        if (!select) return;
        select.innerHTML = '<option value="">Wybierz zlecenie…</option>';
        jobs.forEach(job => {
            const customerName = job.customer?.display_name || job.customer?.full_name || '';
            const label = `#${job.id}${customerName ? ' — ' + customerName : ''}${job.title ? ' — ' + job.title : ''}`;
            const opt = document.createElement('option');
            opt.value = String(job.id);
            opt.textContent = label;
            select.appendChild(opt);
        });

        if (preselectJobId) {
            select.value = String(preselectJobId);
        }
    };

    try {
        const res = await jobsAPI.getAll({}, 1);
        const jobs = res?.data || [];

        fill(selectHome, jobs);
        fill(selectCreate, jobs);

        if (selectCreate && preselectJobId) {
            selectCreate.value = String(preselectJobId);
        }
    } catch (err) {
        console.error('Failed to load jobs for consents view:', err);
        if (selectHome) selectHome.innerHTML = '<option value="">Nie udało się załadować zleceń</option>';
        if (selectCreate) selectCreate.innerHTML = '<option value="">Nie udało się załadować zleceń</option>';
    }
}

function injectCreateModalMarkup(container) {
    // Replace placeholder modal div with actual markup
    const modalEl = document.getElementById('consentCreateModal');
    if (!modalEl) return;

    modalEl.outerHTML = `
        <div class="modal fade" id="consentCreateModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="bi bi-plus-lg"></i> Nowa zgoda</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="consentCreateForm" class="row g-3" novalidate>
                            <div class="col-md-6">
                                <label class="form-label">Zlecenie</label>
                                <select class="form-select" id="createConsentJobId" required>
                                    <option value="">Ładowanie…</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Typ zgody</label>
                                <select class="form-select" id="createConsentType" required>
                                    <option value="image_publication" selected>Publikacja wizerunku</option>
                                    <option value="data_processing">Przetwarzanie danych</option>
                                    <option value="marketing">Marketing</option>
                                </select>
                            </div>
                            <div class="col-12">
                                <label class="form-label">Zakres (opcjonalnie)</label>
                                <input class="form-control" id="createConsentScope" placeholder="np. social media, strona www">
                            </div>
                            <div class="col-12">
                                <label class="form-label">Uwagi (opcjonalnie)</label>
                                <textarea class="form-control" id="createConsentNotes" rows="2"></textarea>
                            </div>
                            <div class="col-12">
                                <label class="form-label">Treść zgody</label>
                                <textarea class="form-control" id="createConsentText" rows="6" placeholder="Dla publikacji wizerunku oraz przetwarzania danych może pozostać puste (backend wstawi domyślną treść)."></textarea>
                                <div class="form-text">
                                    Dla typów innych niż publikacja wizerunku i przetwarzanie danych treść jest wymagana.
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="submit" class="btn btn-success" form="consentCreateForm">
                            <i class="bi bi-check2"></i> Zapisz
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Keep container reference used to satisfy linter (not needed otherwise).
    void container;
}

function consentTypeLabel(t) {
    if (t === 'image_publication') return 'Publikacja wizerunku';
    if (t === 'data_processing') return 'Przetwarzanie danych';
    if (t === 'marketing') return 'Marketing';
    return t || '—';
}

function consentStatusLabel(c) {
    if (c.is_revoked) return 'Wycofana';
    if (c.is_granted) return 'Udzielona';
    return 'Oczekuje';
}

function consentStatusColor(c) {
    if (c.is_revoked) return 'secondary';
    if (c.is_granted) return 'success';
    return 'warning';
}

function formatDateTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleString('pl-PL');
}

function escapeHtml(str) {
    return String(str)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

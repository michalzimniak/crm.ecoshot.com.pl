/**
 * Jobs View - Zarządzanie zleceniami
 */

import { jobsAPI, customersAPI, consentsAPI, vouchersAPI } from '../api.js';
import { clearAuth, getStoredAuth, scheduleLoginRedirect } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { openAddressPicker } from '../address_picker.js';
import { validateRequiredFields, wireClearOnInput } from '../forms.js';

let currentPage = 1;
let currentFilters = {};
let availableOffers = [];

let scheduleVoucherValidationGlobal = null;

export async function renderJobs(params) {
    const container = document.getElementById('viewContainer');
    
    // Check if viewing/editing specific job
    if (params && params[0]) {
        if (params[0] === 'new') {
            return renderJobForm(null);
        } else {
            return renderJobDetails(parseInt(params[0]));
        }
    }
    
    // Show loading
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-briefcase"></i> Zlecenia</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await jobsAPI.getAll(currentFilters, currentPage);
        const jobs = response.data || [];
        const pagination = response.pagination || { page: 1, pages: 1, total: 0 };
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-briefcase"></i> Zlecenia</h1>
                    <p class="text-muted mb-0">Zarządzanie zleceniami fotograficznymi</p>
                </div>
                <div>
                    <button class="btn btn-success" onclick="window.location.hash='#/jobs/new'">
                        <i class="bi bi-plus-lg"></i> Nowe zlecenie
                    </button>
                </div>
            </div>
            
            <!-- Filters -->
            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <select class="form-select" id="statusFilter">
                                <option value="">Wszystkie statusy</option>
                                <option value="draft" ${currentFilters.status === 'draft' ? 'selected' : ''}>Oczekujące</option>
                                <option value="accepted" ${currentFilters.status === 'accepted' ? 'selected' : ''}>Potwierdzone</option>
                                <option value="in_progress" ${currentFilters.status === 'in_progress' ? 'selected' : ''}>W realizacji</option>
                                <option value="completed" ${currentFilters.status === 'completed' ? 'selected' : ''}>Zakończone</option>
                                <option value="cancelled" ${currentFilters.status === 'cancelled' ? 'selected' : ''}>Anulowane</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <input type="date" class="form-control" id="dateFromFilter" 
                                   placeholder="Data od" value="${currentFilters.date_from || ''}">
                        </div>
                        <div class="col-md-3">
                            <input type="date" class="form-control" id="dateToFilter" 
                                   placeholder="Data do" value="${currentFilters.date_to || ''}">
                        </div>
                        <div class="col-md-3">
                            <button class="btn btn-outline-secondary w-100" id="resetFiltersBtn">
                                <i class="bi bi-x-circle"></i> Wyczyść filtry
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Jobs Table -->
            ${jobs.length === 0 ? `
                <div class="card">
                    <div class="card-body text-center py-5">
                        <i class="bi bi-inbox display-1 text-muted"></i>
                        <p class="text-muted mt-3 mb-0">Brak zleceń</p>
                        <button class="btn btn-success mt-3" onclick="window.location.hash='#/jobs/new'">
                            <i class="bi bi-plus-lg"></i> Utwórz pierwsze zlecenie
                        </button>
                    </div>
                </div>
            ` : `
                <div class="card">
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Status</th>
                                    <th>Klient</th>
                                    <th>Pakiet</th>
                                    <th>Data</th>
                                    <th>Lokalizacja</th>
                                    <th>Dodatki</th>
                                    <th class="text-end">Cena</th>
                                    <th class="text-end">Akcje</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${jobs.map(job => `
                                    <tr style="cursor:pointer" onclick="window.location.hash='#/jobs/${job.id}'">
                                        <td><strong>#${job.id}</strong></td>
                                        <td><span class="badge bg-${getStatusColor(job.status)}">${getStatusLabel(job.status)}</span></td>
                                        <td>
                                            ${job.customer?.display_name || job.customer?.full_name || 'Brak klienta'}
                                            ${job.title ? `<div class="text-muted small">${job.title}</div>` : ''}
                                        </td>
                                        <td>${job.offer?.name || 'Brak oferty'}</td>
                                        <td>${formatDate(job.event_start || job.event_date) || '—'}</td>
                                        <td>${job.event_location || '—'}</td>
                                        <td>${job.selected_addons_count > 0 ? `${job.selected_addons_count}` : '—'}</td>
                                        <td class="text-end"><strong class="text-success">${formatCurrency(job.final_price)}</strong></td>
                                        <td class="text-end" onclick="event.stopPropagation();">
                                            <div class="btn-group btn-group-sm">
                                                <a class="btn btn-outline-primary" href="#/jobs/${job.id}">Otwórz</a>
                                                <a class="btn btn-outline-secondary" href="#/contracts/job/${job.id}">Umowa</a>
                                            </div>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `}
            
            <!-- Pagination (footer always visible) -->
            <div class="card">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="text-muted">
                            Strona ${pagination.page} z ${pagination.pages} (${pagination.total} zleceń)
                        </div>
                        ${pagination.pages > 1 ? `
                            <nav>
                                <ul class="pagination mb-0">
                                    <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                        <a class="page-link" href="#" onclick="goToJobsPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                    </li>
                                    ${Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                                        const pageNum = i + 1;
                                        return `
                                            <li class="page-item ${pageNum === pagination.page ? 'active' : ''}">
                                                <a class="page-link" href="#" onclick="goToJobsPage(${pageNum}); return false;">${pageNum}</a>
                                            </li>
                                        `;
                                    }).join('')}
                                    <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                        <a class="page-link" href="#" onclick="goToJobsPage(${pagination.page + 1}); return false;">Następna</a>
                                    </li>
                                </ul>
                            </nav>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
        
        setupJobsListeners();
        
    } catch (error) {
        console.error('Failed to load jobs:', error);
        showToast('Błąd ładowania zleceń', 'danger');
    }
}

function setupJobsListeners() {
    document.getElementById('statusFilter')?.addEventListener('change', (e) => {
        currentFilters.status = e.target.value;
        currentPage = 1;
        renderJobs();
    });
    
    document.getElementById('dateFromFilter')?.addEventListener('change', (e) => {
        currentFilters.date_from = e.target.value;
        currentPage = 1;
        renderJobs();
    });
    
    document.getElementById('dateToFilter')?.addEventListener('change', (e) => {
        currentFilters.date_to = e.target.value;
        currentPage = 1;
        renderJobs();
    });
    
    document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
        currentFilters = {};
        currentPage = 1;
        renderJobs();
    });
}

window.goToJobsPage = (page) => {
    currentPage = page;
    renderJobs();
};

async function renderJobForm(jobId) {
    const container = document.getElementById('viewContainer');
    const isEdit = jobId !== null;
    
    // Load required data
    let job = null;
    let customers = [];
    let offers = [];
    
    try {
        [customers, offers] = await Promise.all([
            customersAPI.getAll({ is_active: 'true', per_page: 1000 }),
            jobsAPI.getOffers(),
        ]);
        
        if (isEdit) {
            const response = await jobsAPI.getById(jobId);
            job = response.data;
        }
        
    } catch (error) {
        showToast('Błąd ładowania danych', 'danger');
        navigate('/jobs');
        return;
    }
    
    availableOffers = offers.data || [];
    
    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-${isEdit ? 'pencil' : 'plus-lg'}"></i> ${isEdit ? 'Edytuj zlecenie' : 'Nowe zlecenie'}</h1>
            </div>
            <div>
                <button class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs'">
                    <i class="bi bi-arrow-left"></i> Powrót
                </button>
            </div>
        </div>
        
        <div class="row">
            <div class="col-lg-8">
                <form id="jobForm" novalidate>
                    <!-- Basic info -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-card-text"></i> Podstawowe</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="title" class="form-label">Tytuł *</label>
                                <input type="text" class="form-control" id="title" name="title" required
                                       value="${job?.title || ''}" placeholder="np. Ślub – Kowalscy">
                            </div>
                            <div class="mb-3">
                                <label for="description" class="form-label">Opis</label>
                                <textarea class="form-control" id="description" name="description" rows="3">${job?.description || ''}</textarea>
                            </div>
                        </div>
                    </div>
                    <!-- Customer -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-person"></i> Klient</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="customerId" class="form-label">Wybierz klienta *</label>
                                <select class="form-select" id="customerId" name="customer_id" required>
                                    <option value="">-- Wybierz --</option>
                                    ${(customers.data || []).map(customer => `
                                        <option value="${customer.id}" ${job?.customer_id === customer.id ? 'selected' : ''}>
                                            ${customer.display_name || customer.full_name} ${customer.email ? `(${customer.email})` : ''}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>
                            <a href="#/customers/new" class="btn btn-sm btn-outline-primary">
                                <i class="bi bi-person-plus"></i> Dodaj nowego klienta
                            </a>
                        </div>
                    </div>
                    
                    <!-- Offer -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-camera"></i> Oferta</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="offerId" class="form-label">Wybierz pakiet *</label>
                                <select class="form-select" id="offerId" name="offer_id" required>
                                    <option value="">-- Wybierz --</option>
                                    ${availableOffers.map(offer => `
                                        <option value="${offer.id}" ${job?.offer_id === offer.id ? 'selected' : ''}
                                                data-price="${offer.base_price}"
                                                data-hours="${offer.hours_included || ''}"
                                                data-photos="${offer.photos_count || ''}">
                                            ${offer.name} - ${formatOfferPriceLabel(offer)}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>
                            <div id="offerDetails" class="alert alert-info d-none">
                                <strong>Szczegóły pakietu:</strong>
                                <ul class="mb-0 mt-2">
                                    <li id="offerDesc" class="small text-muted"></li>
                                    <li id="offerHours"></li>
                                    <li id="offerPhotos"></li>
                                    <li id="offerPrice"></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Add-ons -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-plus-circle"></i> Dodatki i album online</h5>
                        </div>
                        <div class="card-body">
                            <div id="addonsContainer" class="text-muted">Wybierz ofertę, aby zobaczyć dostępne dodatki.</div>
                        </div>
                    </div>
                    
                    <!-- Event Details -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-calendar3"></i> Szczegóły wydarzenia</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="eventStart" class="form-label">Data i godzina *</label>
                                <input type="datetime-local" class="form-control" id="eventStart" name="event_start"
                                    value="${job?.event_start ? toDatetimeLocalValue(job.event_start) : (job?.event_date ? `${job.event_date}T00:00` : '')}" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="eventLocation" class="form-label">Lokalizacja *</label>
                                <div class="input-group">
                                    <input type="text" class="form-control" id="eventLocation" name="event_location"
                                           value="${job?.event_location || ''}" required placeholder="np. Bydgoszcz, ul. Gdańska 1">
                                    <button class="btn btn-outline-secondary" type="button" id="pickJobLocationBtn" title="Wybierz z Google Maps">
                                        <i class="bi bi-geo-alt"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notes" class="form-label">Notatki</label>
                                <textarea class="form-control" id="notes" name="notes" rows="3">${job?.notes || ''}</textarea>
                            </div>

                            <div class="mb-3">
                                <label for="voucherCode" class="form-label">Voucher (kod)</label>
                                <input class="form-control" id="voucherCode" name="voucher_code" value="${job?.voucher_code || ''}" placeholder="Zeskanuj lub wpisz kod" autocomplete="off">
                                <div class="form-text">Opcjonalnie. Kod zostanie sprawdzony po zapisie.</div>
                                <div id="voucherCodeStatus" class="small mt-1"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Submit -->
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-check-lg"></i> ${isEdit ? 'Zapisz zmiany' : 'Utwórz zlecenie'}
                                </button>
                                <button type="button" class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs'">
                                    Anuluj
                                </button>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
            
            <!-- Summary Sidebar -->
            <div class="col-lg-4">
                <div class="card sticky-top" style="top: 80px;">
                    <div class="card-header">
                        <h5 class="mb-0"><i class="bi bi-calculator"></i> Podsumowanie</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-flex justify-content-between mb-2">
                            <span>Cena bazowa:</span>
                            <strong id="summaryBasePrice">0,00 zł</strong>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span>Dodatki:</span>
                            <strong id="summaryAddons">0,00 zł</strong>
                        </div>
                        <div class="d-flex justify-content-between mb-2" id="summaryDiscountRow" data-amount="${job?.discount_amount || 0}" style="display:none;">
                            <span>Rabat (voucher):</span>
                            <strong class="text-danger" id="summaryDiscount">0,00 zł</strong>
                        </div>
                        <hr>
                        <div class="d-flex justify-content-between">
                            <strong>Razem:</strong>
                            <strong class="text-success fs-4" id="summaryTotal">0,00 zł</strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    setupJobFormListeners(jobId);
}

function setupJobFormListeners(jobId) {
    const form = document.getElementById('jobForm');
    const offerSelect = document.getElementById('offerId');
    const offerDetails = document.getElementById('offerDetails');
    const voucherInput = document.getElementById('voucherCode');
    const voucherStatusEl = document.getElementById('voucherCodeStatus');

    document.getElementById('pickJobLocationBtn')?.addEventListener('click', () => {
        openAddressPicker({
            title: 'Wybierz lokalizację wydarzenia',
            initialQuery: document.getElementById('eventLocation')?.value || '',
            onSelect: (details) => {
                const value = details?.formatted_address || details?.name || '';
                if (value) document.getElementById('eventLocation').value = value;
            }
        });
    });
    
    // Show offer details
    offerSelect.addEventListener('change', () => {
        const selected = offerSelect.options[offerSelect.selectedIndex];
        
        if (selected.value) {
            const offerId = parseInt(selected.value);
            const offer = availableOffers.find(o => o.id === offerId);
            const price = selected.dataset.price;
            const hours = selected.dataset.hours;
            const photos = selected.dataset.photos;

            const descEl = document.getElementById('offerDesc');
            const desc = offer?.description || '';
            descEl.innerHTML = desc
                ? `<div style="white-space: pre-line;">${escapeHtml(desc)}</div>`
                : '';
            descEl.style.display = desc ? '' : 'none';

            const hoursEl = document.getElementById('offerHours');
            hoursEl.textContent = hours ? `${hours} godzin` : '';
            hoursEl.style.display = hours ? '' : 'none';

            const photosEl = document.getElementById('offerPhotos');
            photosEl.textContent = photos ? `${photos} zdjęć` : '';
            photosEl.style.display = photos ? '' : 'none';
            
            document.getElementById('offerPrice').textContent = `Cena: ${formatCurrency(price)}`;
            
            offerDetails.classList.remove('d-none');

            renderAddonsForOffer(offerId);
            updateSummary();
            if (typeof scheduleVoucherValidationGlobal === 'function') {
                scheduleVoucherValidationGlobal();
            }
        } else {
            offerDetails.classList.add('d-none');
            document.getElementById('addonsContainer').innerHTML = '<div class="text-muted">Wybierz ofertę, aby zobaczyć dostępne dodatki.</div>';
            updateSummary();
            if (typeof scheduleVoucherValidationGlobal === 'function') {
                scheduleVoucherValidationGlobal();
            }
        }
    });
    
    // Trigger initial update if editing
    offerSelect.dispatchEvent(new Event('change'));

    // Show discount row (edit mode), if any.
    updateSummary();

    // --- Live voucher validation (debounced) ---
    const discountRow = document.getElementById('summaryDiscountRow');
    if (discountRow) {
        // Preserve applied state so clearing the field restores it.
        discountRow.dataset.appliedAmount = discountRow.dataset.amount || '0';
        discountRow.dataset.appliedCode = (voucherInput?.value || '').trim().toUpperCase();
    }

    let voucherTimer = null;
    let voucherAbort = null;
    let lastValidatedKey = '';

    function setVoucherStatus(kind, text) {
        if (!voucherStatusEl) return;
        const cls = {
            ok: 'text-success',
            warn: 'text-warning',
            err: 'text-danger',
            info: 'text-muted',
        }[kind] || 'text-muted';
        voucherStatusEl.className = `small mt-1 ${cls}`;
        voucherStatusEl.textContent = text || '';
    }

    function computeCurrentSubtotal() {
        const selected = offerSelect?.options[offerSelect.selectedIndex];
        if (!selected?.value) return null;

        const parseMoney = (raw) => {
            if (raw === null || raw === undefined) return Number.NaN;
            const s = String(raw).replace(/\s+/g, '').replace(',', '.');
            const n = parseFloat(s);
            return Number.isFinite(n) ? n : Number.NaN;
        };

        // Prefer DOM data attribute, but fall back to offers list if needed.
        const selectedOfferId = String(selected.value);
        let base = parseMoney(selected.dataset?.price);
        if (!Number.isFinite(base)) {
            const offer = (availableOffers || []).find(o => String(o.id) === selectedOfferId);
            base = parseMoney(offer?.base_price);
        }
        if (!Number.isFinite(base)) return null;

        let addonsTotal = 0;
        document.querySelectorAll('.addon-check:checked').forEach(el => {
            addonsTotal += parseMoney(el.dataset?.price) || 0;
        });
        document.querySelectorAll('.addon-qty').forEach(el => {
            const qty = parseInt(el.value || '0');
            const unit = parseMoney(el.dataset?.unitPrice) || 0;
            addonsTotal += Math.max(0, qty) * unit;
        });
        const planEl = document.querySelector('input[name="online_album_plan"]:checked');
        if (planEl && planEl.value) {
            addonsTotal += parseMoney(planEl.dataset?.price) || 0;
        }

        const subtotal = base + addonsTotal;
        return Math.max(0, subtotal);
    }

    async function validateVoucherLive() {
        if (!voucherInput) return;

        const raw = (voucherInput.value || '').trim();
        const code = raw.toUpperCase();

        // Restore applied values when cleared.
        if (!code) {
            if (discountRow) {
                discountRow.dataset.amount = discountRow.dataset.appliedAmount || '0';
            }
            updateSummary();
            setVoucherStatus('info', '');
            lastValidatedKey = '';
            return;
        }

        const subtotal = computeCurrentSubtotal();
        const validateKey = `${code}|${subtotal === null ? 'null' : String(subtotal)}`;

        // Avoid spamming API if unchanged (code + subtotal).
        if (validateKey === lastValidatedKey) return;
        lastValidatedKey = validateKey;

        // Abort previous request.
        if (voucherAbort) {
            try { voucherAbort.abort(); } catch (_) {}
        }
        voucherAbort = new AbortController();

        setVoucherStatus('info', 'Sprawdzanie vouchera…');

        try {
            const res = await vouchersAPI.validate(
                code,
                { job_id: jobId || null, total: subtotal !== null ? subtotal : null },
                { showErrors: false, signal: voucherAbort.signal }
            );

            const data = res?.data;
            const status = data?.status;
            const expiresAt = data?.expires_at ? new Date(data.expires_at).toLocaleString('pl-PL') : null;

            if (status === 'valid') {
                const promoValue = parseFloat(data.promotion_value || '0') || 0;

                // If offer isn't selected yet, we can validate the code but we can't apply a discount.
                if (subtotal === null) {
                    if (discountRow) discountRow.dataset.amount = '0';
                    updateSummary();
                    setVoucherStatus('ok', `OK: wartość vouchera ${formatCurrency(promoValue)} — wybierz ofertę, aby naliczyć rabat${expiresAt ? ` (ważny do ${expiresAt})` : ''}`);
                    return;
                }

                const discount = parseFloat(data.discount_amount || '0') || 0;
                if (discountRow) discountRow.dataset.amount = String(discount);
                updateSummary();
                setVoucherStatus('ok', `OK: rabat ${formatCurrency(discount)}${expiresAt ? `, ważny do ${expiresAt}` : ''}`);
                return;
            }

            if (status === 'applied') {
                const discount = parseFloat(data.discount_amount || discountRow?.dataset.appliedAmount || '0') || 0;
                if (discountRow) discountRow.dataset.amount = String(discount);
                updateSummary();
                setVoucherStatus('ok', `Voucher przypisany do tego zlecenia${expiresAt ? ` (ważny do ${expiresAt})` : ''}`);
                return;
            }

            // Invalid statuses: clear pending discount (unless this is the already-applied code).
            const appliedCode = (discountRow?.dataset.appliedCode || '').trim().toUpperCase();
            if (discountRow) {
                if (appliedCode && code === appliedCode) {
                    discountRow.dataset.amount = discountRow.dataset.appliedAmount || '0';
                } else {
                    discountRow.dataset.amount = '0';
                }
            }
            updateSummary();

            if (status === 'used') {
                setVoucherStatus('err', 'Voucher został już wykorzystany');
            } else if (status === 'expired') {
                setVoucherStatus('err', 'Voucher jest po terminie (nieważny)');
            } else if (status === 'not_found') {
                setVoucherStatus('err', 'Nieprawidłowy kod vouchera');
            } else {
                setVoucherStatus('err', data?.message || 'Voucher nieprawidłowy');
            }
        } catch (e) {
            // Ignore aborts.
            if (e?.name === 'AbortError') return;
            console.error(e);
            setVoucherStatus('warn', 'Nie udało się sprawdzić vouchera');
        }
    }

    function scheduleVoucherValidation() {
        if (voucherTimer) clearTimeout(voucherTimer);
        voucherTimer = setTimeout(() => {
            validateVoucherLive().catch(() => {});
        }, 350);
    }

    scheduleVoucherValidationGlobal = scheduleVoucherValidation;

    voucherInput?.addEventListener('input', scheduleVoucherValidation);

    // Initial validation (edit mode may show "applied").
    if (voucherInput && (voucherInput.value || '').trim()) {
        scheduleVoucherValidation();
    }

    // Clear inline errors while typing
    wireClearOnInput(form);
    
    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!validateRequiredFields(form)) {
            return;
        }
        
        const formData = new FormData(form);

        const { selectedAddonIds, addonQuantities } = collectAddonsSelection();

        const data = {
            customer_id: parseInt(formData.get('customer_id')),
            offer_id: parseInt(formData.get('offer_id')),
            title: formData.get('title'),
            description: formData.get('description') || null,
            event_start: formData.get('event_start') || null,
            event_location: formData.get('event_location'),
            notes: formData.get('notes') || null,
            voucher_code: (formData.get('voucher_code') || '').trim() || null,
            selected_addon_ids: selectedAddonIds,
            addon_quantities: addonQuantities,
        };
        
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Zapisywanie...';
        
        try {
            if (jobId) {
                await jobsAPI.update(jobId, data);
            } else {
                const response = await jobsAPI.create(data);
                const newJobId = response.data?.id;
                if (newJobId) {
                    navigate(`/jobs/${newJobId}`);
                    return;
                }
            }
            
            navigate('/jobs');
            
        } catch (error) {
            console.error('Failed to save job:', error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<i class="bi bi-check-lg"></i> ${jobId ? 'Zapisz zmiany' : 'Utwórz zlecenie'}`;
        }
    });
}

function renderAddonsForOffer(offerId) {
    const container = document.getElementById('addonsContainer');
    const offer = availableOffers.find(o => o.id === offerId);
    const addons = (offer?.addons || []).filter(a => a.is_available);

    if (!offer || addons.length === 0) {
        container.innerHTML = '<div class="text-muted">Brak dodatków dla tej oferty.</div>';
        return;
    }

    const onlinePlans = addons.filter(a => a.category === 'online_album' && a.duration_months);
    const normalAddons = addons.filter(a => a.category !== 'online_album');

    const onlineHtml = onlinePlans.length ? `
        <div class="mb-3">
            <div class="fw-semibold mb-2">Album online (ważność)</div>
            <div class="form-check">
                <input class="form-check-input" type="radio" name="online_album_plan" id="onlineAlbumNone" value="" checked>
                <label class="form-check-label" for="onlineAlbumNone">Brak</label>
            </div>
            ${onlinePlans.map(p => `
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="online_album_plan" id="onlineAlbum${p.id}" value="${p.id}" data-price="${p.price}">
                    <label class="form-check-label" for="onlineAlbum${p.id}">
                        ${p.duration_months} mies. – ${formatCurrency(p.price)}
                    </label>
                </div>
            `).join('')}
        </div>
    ` : '';

    const addonsHtml = normalAddons.length ? `
        <div class="fw-semibold mb-2">Dodatki</div>
        ${normalAddons.map(a => {
            if (a.pricing_model === 'per_unit') {
                return `
                    <div class="row align-items-center mb-2">
                        <div class="col-7">
                            <div class="fw-semibold">${a.name}</div>
                            ${a.description ? `<div class="text-muted small">${a.description}</div>` : ''}
                        </div>
                        <div class="col-5">
                            <div class="input-group">
                                <input type="number" min="0" step="1" class="form-control addon-qty" data-addon-id="${a.id}" data-unit-price="${a.price}" value="0">
                                <span class="input-group-text">× ${formatCurrency(a.price)}</span>
                            </div>
                        </div>
                    </div>
                `;
            }
            return `
                <div class="form-check mb-2">
                    <input class="form-check-input addon-check" type="checkbox" id="addon${a.id}" data-addon-id="${a.id}" data-price="${a.price}">
                    <label class="form-check-label" for="addon${a.id}">
                        ${a.name} <span class="text-muted">(${formatCurrency(a.price)})</span>
                    </label>
                </div>
            `;
        }).join('')}
    ` : '<div class="text-muted">Brak dodatków.</div>';

    container.innerHTML = `${onlineHtml}${addonsHtml}`;

    container.querySelectorAll('input').forEach(el => {
        const handler = () => {
            updateSummary();
            if (typeof scheduleVoucherValidationGlobal === 'function') {
                scheduleVoucherValidationGlobal();
            }
        };
        el.addEventListener('change', handler);
        el.addEventListener('input', handler);
    });
}

function collectAddonsSelection() {
    const selectedAddonIds = [];
    const addonQuantities = {};

    document.querySelectorAll('.addon-check:checked').forEach(el => {
        const id = parseInt(el.dataset.addonId);
        if (id) selectedAddonIds.push(id);
    });

    document.querySelectorAll('.addon-qty').forEach(el => {
        const id = parseInt(el.dataset.addonId);
        const qty = parseInt(el.value || '0');
        if (id && qty > 0) {
            addonQuantities[String(id)] = qty;
        }
    });

    const planEl = document.querySelector('input[name="online_album_plan"]:checked');
    const planId = parseInt(planEl?.value);
    if (planId) selectedAddonIds.push(planId);

    return { selectedAddonIds, addonQuantities };
}

function updateSummary() {
    const offerSelect = document.getElementById('offerId');
    const selected = offerSelect?.options[offerSelect.selectedIndex];
    const base = selected?.value ? parseFloat(selected.dataset.price || '0') : 0;

    let addonsTotal = 0;
    document.querySelectorAll('.addon-check:checked').forEach(el => {
        addonsTotal += parseFloat(el.dataset.price || '0');
    });
    document.querySelectorAll('.addon-qty').forEach(el => {
        const qty = parseInt(el.value || '0');
        const unit = parseFloat(el.dataset.unitPrice || '0');
        addonsTotal += Math.max(0, qty) * unit;
    });
    const planEl = document.querySelector('input[name="online_album_plan"]:checked');
    if (planEl && planEl.value) {
        addonsTotal += parseFloat(planEl.dataset.price || '0');
    }

    const discountRow = document.getElementById('summaryDiscountRow');
    const discountAmount = parseFloat(discountRow?.dataset.amount || '0') || 0;

    document.getElementById('summaryBasePrice').textContent = formatCurrency(base);
    document.getElementById('summaryAddons').textContent = formatCurrency(addonsTotal);

    if (discountRow && discountAmount > 0) {
        discountRow.style.display = '';
        const discountEl = document.getElementById('summaryDiscount');
        if (discountEl) discountEl.textContent = `- ${formatCurrency(discountAmount)}`;
    } else if (discountRow) {
        discountRow.style.display = 'none';
    }

    document.getElementById('summaryTotal').textContent = formatCurrency(Math.max(0, base + addonsTotal - Math.max(0, discountAmount)));
}

async function renderJobDetails(jobId) {
    const container = document.getElementById('viewContainer');
    
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const [jobResponse, consentsResponse] = await Promise.all([
            jobsAPI.getById(jobId),
            consentsAPI.getByJobId(jobId, { showErrors: false }).catch(() => ({ data: [] })),
        ]);

        const job = jobResponse.data;
        const consents = consentsResponse?.data || [];
        const imageConsent = consents.find(c => c.consent_type === 'image_publication');

        const getConsentStatus = (c) => {
            if (!c) return { label: 'Brak', color: 'warning' };
            if (c.is_revoked) return { label: 'Cofnięta', color: 'danger' };
            if (c.is_granted) return { label: 'Udzielona', color: 'success' };
            return { label: 'Nieudzielona', color: 'secondary' };
        };
        const consentStatus = getConsentStatus(imageConsent);
        const consentScanInputId = `consentScanFile_${jobId}`;

        const selectedAddons = (job.addons || []).filter(a => {
            const pricingModel = a.pricing_model || 'fixed';
            const qty = parseInt(a.quantity || '0');
            if (pricingModel === 'per_unit') return qty > 0;
            return !!a.is_selected;
        });

        const addonsTotal = selectedAddons.reduce((sum, a) => {
            const pricingModel = a.pricing_model || 'fixed';
            const qty = parseInt(a.quantity || '0');
            const unitPrice = parseFloat(a.price || '0');
            const lineTotal = pricingModel === 'per_unit' ? Math.max(0, qty) * unitPrice : unitPrice;
            return sum + lineTotal;
        }, 0);

        const discountAmount = parseFloat(job.discount_amount || '0') || 0;
        const voucherCode = (job.voucher_code || '').trim();

        const selectedAddonsHtml = selectedAddons.length ? `
            <ul class="mb-0 ps-3">
                ${selectedAddons.map(a => {
                    const pricingModel = a.pricing_model || 'fixed';
                    const qty = parseInt(a.quantity || '0');
                    const unitPrice = parseFloat(a.price || '0');
                    const lineTotal = pricingModel === 'per_unit' ? Math.max(0, qty) * unitPrice : unitPrice;
                    const qtyLabel = pricingModel === 'per_unit' ? ` <span class="text-muted">(x${Math.max(0, qty)})</span>` : '';
                    return `
                        <li>
                            ${escapeHtml(a.name)}${qtyLabel}
                            <span class="text-muted">— ${formatCurrency(lineTotal)}</span>
                        </li>
                    `;
                }).join('')}
            </ul>
        ` : '<div class="text-muted">Brak wybranych dodatków.</div>';

        const offerDesc = (job.offer?.description || '').trim();
        const offerHours = job.offer?.hours_included;
        const offerPhotos = job.offer?.photos_count;
        const offerPriceLabel = job.offer ? formatOfferPriceLabel(job.offer) : '';

        const offerDetailsHtml = (offerDesc || offerHours || offerPhotos || offerPriceLabel) ? `
            <div class="alert alert-info mb-3">
                <strong>Szczegóły pakietu:</strong>
                <ul class="mb-0 mt-2">
                    ${offerDesc ? `<li class="small text-muted"><div style="white-space: pre-line;">${escapeHtml(offerDesc)}</div></li>` : ''}
                    ${offerHours ? `<li>${escapeHtml(offerHours)} godzin</li>` : ''}
                    ${offerPhotos ? `<li>${escapeHtml(offerPhotos)} zdjęć</li>` : ''}
                    ${offerPriceLabel ? `<li>Cena: ${escapeHtml(offerPriceLabel)}</li>` : ''}
                </ul>
            </div>
        ` : '';
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-briefcase"></i> Zlecenie #${job.id}</h1>
                    <span class="badge bg-${getStatusColor(job.status)} fs-6">${getStatusLabel(job.status)}</span>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-primary" onclick="window.location.hash='#/jobs/${job.id}/edit'">
                        <i class="bi bi-pencil"></i> Edytuj
                    </button>
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs'">
                        <i class="bi bi-arrow-left"></i> Powrót
                    </button>
                </div>
            </div>
            
            <div class="row">
                <div class="col-lg-8">
                    <!-- Customer Info -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-person"></i> Klient</h5>
                        </div>
                        <div class="card-body">
                            <h4>${job.customer?.display_name || job.customer?.full_name}</h4>
                            <p class="mb-1"><i class="bi bi-envelope"></i> ${job.customer?.email || '-'}</p>
                            <p class="mb-1"><i class="bi bi-telephone"></i> ${job.customer?.phone || '-'}</p>
                            <a href="#/customers/${job.customer_id}" class="btn btn-sm btn-outline-primary mt-2">
                                Zobacz profil klienta
                            </a>
                        </div>
                    </div>
                    
                    <!-- Event Details -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-calendar3"></i> Szczegóły wydarzenia</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Data:</strong> ${formatDate(job.event_start || job.event_date)}</p>
                            <p><strong>Lokalizacja:</strong> ${job.event_location}</p>
                            ${job.event_description ? `<p><strong>Opis:</strong><br>${job.event_description}</p>` : ''}
                        </div>
                    </div>
                    
                    <!-- Status Actions -->
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-arrow-repeat"></i> Zmiana statusu</h5>
                        </div>
                        <div class="card-body">
                            <div class="d-flex flex-wrap gap-2" role="group">
                                ${['draft', 'accepted', 'in_progress', 'completed', 'cancelled'].map(status => `
                                    <button class="btn btn-outline-${getStatusColor(status)} flex-fill ${job.status === status ? 'active' : ''}"
                                            onclick="changeJobStatus(${job.id}, '${status}', '${job.status}')">
                                        ${getStatusLabel(status)}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-4">
                    <!-- Consent -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-check2-square"></i> Zgoda na publikację wizerunku</h5>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-info py-2 mb-3">
                                <div class="small">
                                    Brak zgody oznacza, że <strong>nie możemy</strong> wykorzystywać wizerunku klienta w portfolio/reklamach.
                                    <strong>Nie blokuje</strong> to wykonania sesji ani wystawienia faktury.
                                </div>
                            </div>

                            <div class="alert alert-warning py-2 mb-3">
                                <div class="fw-semibold small mb-1">Wskazówki praktyczne (ważne)</div>
                                <ul class="small mb-0 ps-3">
                                    <li>Zawsze osobna zgoda dla: rodzin</li>
                                    <li>Zawsze osobna zgoda dla: biznesu (tam zgoda jest szczególnie ważna)</li>
                                    <li>Dla dzieci: podpis obojga rodziców (jeśli to możliwe)</li>
                                </ul>
                            </div>

                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span>Status:</span>
                                <span class="badge bg-${consentStatus.color}">${consentStatus.label}</span>
                            </div>
                            ${imageConsent?.has_signed_scan ? `
                                <div class="text-muted small mb-2">Skan: ${escapeHtml(imageConsent.signed_scan_original_filename || '—')}</div>
                            ` : ''}
                            <div class="d-grid gap-2">
                                ${!imageConsent ? `
                                    <button class="btn btn-outline-primary" onclick="createImagePublicationConsent(${job.id})">
                                        <i class="bi bi-plus-lg"></i> Utwórz zgodę
                                    </button>
                                ` : `
                                    <button class="btn btn-outline-primary" onclick="downloadImagePublicationConsentPdf(${imageConsent.id})">
                                        <i class="bi bi-download"></i> Pobierz PDF do wydruku
                                    </button>
                                    <div>
                                        <input class="form-control form-control-sm" type="file" id="${consentScanInputId}" accept=".pdf,.jpg,.jpeg,.png">
                                        <button class="btn btn-outline-success btn-sm w-100 mt-2" onclick="uploadImagePublicationConsentScan(${imageConsent.id}, ${job.id}, '${consentScanInputId}')">
                                            <i class="bi bi-upload"></i> Wyślij skan podpisanej zgody
                                        </button>
                                    </div>
                                `}
                            </div>
                        </div>
                    </div>

                    <!-- Pricing -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-cash-coin"></i> Wycena</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <div class="text-muted">Pakiet</div>
                                <div><strong>${escapeHtml(job.offer?.name || '-')}</strong></div>
                            </div>
                            ${offerDetailsHtml}
                            <div class="d-flex justify-content-between mb-2">
                                <span>Cena bazowa:</span>
                                <strong>${formatCurrency(job.base_price)}</strong>
                            </div>
                            ${selectedAddons.length > 0 ? `
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Dodatki (${selectedAddons.length}):</span>
                                    <strong>${formatCurrency(addonsTotal)}</strong>
                                </div>
                            ` : ''}
                            ${discountAmount > 0 ? `
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Rabat (voucher${voucherCode ? ` ${escapeHtml(voucherCode)}` : ''}):</span>
                                    <strong class="text-danger">- ${formatCurrency(discountAmount)}</strong>
                                </div>
                            ` : ''}
                            <div class="mb-3">
                                <div class="text-muted">Wybrane dodatki</div>
                                ${selectedAddonsHtml}
                            </div>
                            <hr>
                            <div class="d-flex justify-content-between">
                                <strong>Razem:</strong>
                                <strong class="text-success fs-4">${formatCurrency(job.final_price)}</strong>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Quick Actions -->
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-lightning"></i> Szybkie akcje</h5>
                        </div>
                        <div class="card-body d-grid gap-2">
                            <button class="btn btn-outline-primary" onclick="window.location.hash='#/contracts/job/${job.id}'">
                                <i class="bi bi-file-earmark-text"></i> Umowa
                            </button>
                            <button class="btn btn-outline-warning" onclick="window.location.hash='#/invoices/job/${job.id}'">
                                <i class="bi bi-receipt"></i> Faktura
                            </button>
                            <button class="btn btn-outline-info" onclick="window.location.hash='#/galleries/job/${job.id}'">
                                <i class="bi bi-images"></i> Galeria
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to load job details:', error);
        showToast('Nie znaleziono zlecenia', 'danger');
        navigate('/jobs');
    }
}

async function fetchBlobWithAuth(url) {
    const auth = getStoredAuth();
    const headers = {};
    if (auth?.access_token) headers['Authorization'] = `Bearer ${auth.access_token}`;

    const resp = await fetch(url, { headers });

    if ((resp.status === 401 || resp.status === 422)) {
        clearAuth();
        showToast('Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.', 'warning');
        scheduleLoginRedirect(2500);
        throw new Error('UNAUTHORIZED');
    }

    if (!resp.ok) {
        try {
            const payload = await resp.json();
            throw new Error(payload?.error || payload?.message || `Błąd ${resp.status}`);
        } catch (e) {
            throw new Error(`Błąd ${resp.status}`);
        }
    }

    return await resp.blob();
}

async function openBlobInNewTab(blob, fallbackName) {
    const blobUrl = URL.createObjectURL(blob);
    const win = window.open(blobUrl, '_blank', 'noopener');
    if (!win) {
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = fallbackName || 'download';
        document.body.appendChild(a);
        a.click();
        a.remove();
    }
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

window.createImagePublicationConsent = async (jobId) => {
    try {
        await consentsAPI.create({ job_id: jobId, consent_type: 'image_publication' });
        await renderJobDetails(jobId);
    } catch (e) {
        showToast(e?.message || 'Nie udało się utworzyć zgody', 'danger');
    }
};

window.downloadImagePublicationConsentPdf = async (consentId) => {
    try {
        const blob = await fetchBlobWithAuth(`/api/consents/${consentId}/pdf`);
        await openBlobInNewTab(blob, `zgoda_${consentId}.pdf`);
    } catch (e) {
        if (e?.message !== 'UNAUTHORIZED') {
            showToast(e?.message || 'Nie udało się pobrać PDF', 'danger');
        }
    }
};

window.uploadImagePublicationConsentScan = async (consentId, jobId, inputId) => {
    try {
        const input = document.getElementById(inputId);
        const file = input?.files?.[0];
        if (!file) {
            showToast('Wybierz plik', 'warning');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);

        await consentsAPI.uploadSignedScan(consentId, formData, { showLoading: true });
        await renderJobDetails(jobId);
    } catch (e) {
        showToast(e?.message || 'Nie udało się wysłać skanu', 'danger');
    }
};

async function applyJobWorkflowTransition(jobId, currentStatus, targetStatus) {
    // Mirrors backend enforcement rules in app/core/enforcement.py
    const nextStepByTarget = (from, target) => {
        if (target === 'cancelled') return 'cancelled';
        if (from === target) return null;

        if (from === 'draft') {
            if (target === 'quote_sent') return 'quote_sent';
            if (target === 'accepted' || target === 'in_progress' || target === 'completed') return 'quote_sent';
        }
        if (from === 'quote_sent') {
            if (target === 'accepted' || target === 'in_progress' || target === 'completed') return 'accepted';
            if (target === 'rejected') return 'rejected';
        }
        if (from === 'accepted') {
            if (target === 'in_progress' || target === 'completed') return 'in_progress';
        }
        if (from === 'in_progress') {
            if (target === 'completed') return 'completed';
        }
        return null;
    };

    let status = currentStatus;
    const seen = new Set();

    while (status !== targetStatus) {
        const step = nextStepByTarget(status, targetStatus);
        if (!step) throw new Error(`Nie można zmienić statusu: ${status} -> ${targetStatus}`);
        if (seen.has(`${status}->${step}`)) throw new Error('Wykryto pętlę w zmianie statusu');
        seen.add(`${status}->${step}`);

        await jobsAPI.updateStatus(jobId, step);
        status = step;
    }
}

window.changeJobStatus = async (jobId, newStatus, currentStatus) => {
    try {
        await applyJobWorkflowTransition(jobId, currentStatus, newStatus);
        renderJobDetails(jobId);
    } catch (error) {
        console.error('Failed to change status:', error);
        showToast('Nie udało się zmienić statusu', 'danger');
    }
};

function getStatusColor(status) {
    const colors = {
        'draft': 'secondary',
        'quote_sent': 'warning',
        'accepted': 'primary',
        'rejected': 'danger',
        'in_progress': 'info',
        'completed': 'success',
        'cancelled': 'danger',
    };
    return colors[status] || 'secondary';
}

function getStatusLabel(status) {
    const labels = {
        'draft': 'Oczekujące',
        'quote_sent': 'Oferta wysłana',
        'accepted': 'Potwierdzone',
        'rejected': 'Odrzucone',
        'in_progress': 'W realizacji',
        'completed': 'Zakończone',
        'cancelled': 'Anulowane',
    };
    return labels[status] || status;
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: 'PLN'
    }).format(amount || 0);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('pl-PL', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function escapeHtml(str) {
    return String(str)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatOfferPriceLabel(offer) {
    const desc = (offer?.description || '').trim();
    const m = desc.match(/^Cena:\s*([^\n]+)$/m);
    if (m && m[1]) return m[1].trim();
    return formatCurrency(offer?.base_price);
}

function toDatetimeLocalValue(value) {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';

    const pad = (n) => String(n).padStart(2, '0');
    const yyyy = d.getFullYear();
    const mm = pad(d.getMonth() + 1);
    const dd = pad(d.getDate());
    const hh = pad(d.getHours());
    const mi = pad(d.getMinutes());
    return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
}

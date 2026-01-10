/**
 * Payments View - Zarządzanie płatnościami (manual + PayU)
 */

import { paymentsAPI } from '../api.js';
import { showToast } from '../toasts.js';

import { invoicesAPI, jobsAPI } from '../api.js';
import { validateRequiredFields, requireNumberMin, setFieldError, wireClearOnInput } from '../forms.js';
import { confirmDialog } from '../confirm.js';

let currentPage = 1;
let currentFilters = {};

function getHashQueryParams() {
    const hash = window.location.hash || '';
    const query = hash.includes('?') ? hash.split('?')[1] : '';
    return new URLSearchParams(query || '');
}

function parseOptionalInt(value) {
    const n = parseInt(String(value || ''), 10);
    return Number.isFinite(n) ? n : null;
}

export async function renderPayments(params) {
    const container = document.getElementById('viewContainer');

    const action = params?.[0] || null;
    const query = getHashQueryParams();
    const preselectInvoiceId = parseOptionalInt(query.get('invoice'));
    const preselectJobId = parseOptionalInt(query.get('job'));
    const openCreateOnLoad = action === 'new';

    if (params && params[0]) {
        // Keep list view; some subroutes (like /payments/new) are handled via modal.
        currentPage = 1;
    }

    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-cash-coin"></i> Płatności</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const response = await paymentsAPI.getAll(currentFilters, currentPage);
        const payments = response.data || [];
        const pagination = response.pagination || { page: 1, pages: 1, total: 0 };

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-cash-coin"></i> Płatności</h1>
                    <p class="text-muted mb-0">Manualne + PayU, przedpłaty i wpłaty do faktur</p>
                </div>
                <div>
                    <button class="btn btn-success" id="openCreatePaymentBtn">
                        <i class="bi bi-plus-lg"></i> Dodaj płatność
                    </button>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-body">
                    <div class="d-flex align-items-center justify-content-between">
                        <div>
                            <h5 class="card-title mb-1">Dodaj płatność</h5>
                            <div class="text-muted">Dodawanie odbywa się w oknie modalnym</div>
                        </div>
                        <button class="btn btn-outline-success" id="openCreatePaymentBtn2">
                            <i class="bi bi-plus-lg"></i> Otwórz
                        </button>
                    </div>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <select class="form-select" id="statusFilter">
                                <option value="">Wszystkie statusy</option>
                                <option value="pending" ${currentFilters.status === 'pending' ? 'selected' : ''}>Oczekuje</option>
                                <option value="completed" ${currentFilters.status === 'completed' ? 'selected' : ''}>Zrealizowane</option>
                                <option value="failed" ${currentFilters.status === 'failed' ? 'selected' : ''}>Nieudane</option>
                                <option value="refunded" ${currentFilters.status === 'refunded' ? 'selected' : ''}>Zwrócone</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="sourceFilter">
                                <option value="">Wszystkie źródła</option>
                                <option value="manual" ${currentFilters.source === 'manual' ? 'selected' : ''}>Manual</option>
                                <option value="payu" ${currentFilters.source === 'payu' ? 'selected' : ''}>PayU</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="kindFilter">
                                <option value="">Wszystkie typy</option>
                                <option value="invoice" ${currentFilters.kind === 'invoice' ? 'selected' : ''}>Do faktury</option>
                                <option value="deposit" ${currentFilters.kind === 'deposit' ? 'selected' : ''}>Zaliczka</option>
                                <option value="prepayment" ${currentFilters.kind === 'prepayment' ? 'selected' : ''}>Przedpłata</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <button class="btn btn-outline-secondary w-100" id="resetFiltersBtn">
                                <i class="bi bi-x-circle"></i> Wyczyść filtry
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                ${payments.length === 0 ? `
                    <div class="card-body text-center py-5">
                        <i class="bi bi-inbox display-1 text-muted"></i>
                        <p class="text-muted mt-3">Brak płatności</p>
                    </div>
                ` : `
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Data</th>
                                    <th>Kwota</th>
                                    <th>Źródło</th>
                                    <th>Typ</th>
                                    <th>Faktura</th>
                                    <th>Zlecenie</th>
                                    <th>Status</th>
                                    <th>Akcje</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${payments.map(p => `
                                    <tr>
                                        <td><strong>#${p.id}</strong></td>
                                        <td>${formatDateTime(p.payment_date)}</td>
                                        <td><strong>${formatCurrency(p.amount, p.currency || 'PLN')}</strong></td>
                                        <td>${formatSource(p.source)}</td>
                                        <td>${formatKind(p.kind)}</td>
                                        <td>${renderInvoiceCell(p)}</td>
                                        <td>${renderJobCell(p)}</td>
                                        <td><span class="badge bg-${statusColor(p.status)}">${statusLabel(p.status)}</span></td>
                                        <td>
                                            <div class="btn-group btn-group-sm">
                                                ${p.status === 'pending' ? `
                                                    <button class="btn btn-outline-success" onclick="window.completePayment(${p.id});" title="Potwierdź">
                                                        <i class="bi bi-check2"></i>
                                                    </button>
                                                ` : ''}
                                                ${p.status === 'completed' ? `
                                                    <button class="btn btn-outline-warning" onclick="window.refundPayment(${p.id});" title="Zwrot">
                                                        <i class="bi bi-arrow-counterclockwise"></i>
                                                    </button>
                                                ` : ''}
                                                ${p.status === 'pending' ? `
                                                    <button class="btn btn-outline-danger" onclick="window.deletePayment(${p.id});" title="Usuń">
                                                        <i class="bi bi-trash"></i>
                                                    </button>
                                                ` : ''}
                                                ${p.redirect_url ? `
                                                    <a class="btn btn-outline-primary" href="${p.redirect_url}" target="_blank" title="PayU">
                                                        <i class="bi bi-box-arrow-up-right"></i>
                                                    </a>
                                                ` : ''}
                                            </div>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>

                    <div class="card-footer">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="text-muted">
                                Strona ${pagination.page} z ${pagination.pages} (${pagination.total} płatności)
                            </div>
                            ${pagination.pages > 1 ? `
                                <nav>
                                    <ul class="pagination mb-0">
                                        <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                            <a class="page-link" href="#" onclick="window.goToPaymentsPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                        </li>
                                        <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                            <a class="page-link" href="#" onclick="window.goToPaymentsPage(${pagination.page + 1}); return false;">Następna</a>
                                        </li>
                                    </ul>
                                </nav>
                            ` : ''}
                        </div>
                    </div>
                `}
            </div>

            <!-- Create Payment Modal -->
            <div class="modal fade" id="paymentCreateModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-plus-lg"></i> Dodaj płatność</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="paymentCreateForm" class="row g-3" novalidate>
                                <div class="col-md-4">
                                    <label class="form-label">Źródło</label>
                                    <select class="form-select" id="createSource" required>
                                        <option value="manual" selected>Manual</option>
                                        <option value="payu">PayU</option>
                                    </select>
                                </div>

                                <div class="col-md-4">
                                    <label class="form-label">Typ</label>
                                    <select class="form-select" id="createKind" required>
                                        <option value="invoice" selected>Do faktury</option>
                                        <option value="deposit">Zaliczka</option>
                                        <option value="prepayment">Przedpłata</option>
                                    </select>
                                </div>

                                <div class="col-md-4">
                                    <label class="form-label">Dotyczy</label>
                                    <select class="form-select" id="createTargetType" required>
                                        <option value="invoice" selected>Faktura</option>
                                        <option value="job">Zlecenie</option>
                                    </select>
                                </div>

                                <div class="col-12" id="invoiceSelectRow">
                                    <label class="form-label">Faktura</label>
                                    <select class="form-select" id="createInvoiceId" required>
                                        <option value="">Ładowanie…</option>
                                    </select>
                                </div>

                                <div class="col-12" id="jobSelectRow" style="display:none;">
                                    <label class="form-label">Zlecenie</label>
                                    <select class="form-select" id="createJobId" required>
                                        <option value="">Ładowanie…</option>
                                    </select>
                                </div>

                                <div class="col-md-4" id="amountCol">
                                    <label class="form-label">Kwota</label>
                                    <input class="form-control" id="createAmount" type="number" step="0.01" min="0.01" placeholder="Kwota" required>
                                </div>

                                <div class="col-md-4" id="methodCol">
                                    <label class="form-label">Metoda</label>
                                    <select class="form-select" id="createMethod" required>
                                        <option value="transfer" selected>Przelew</option>
                                        <option value="cash">Gotówka</option>
                                        <option value="card">Karta</option>
                                        <option value="paypal">PayPal</option>
                                        <option value="other">Inne</option>
                                    </select>
                                </div>

                                <div class="col-md-4" id="statusCol">
                                    <label class="form-label">Status</label>
                                    <select class="form-select" id="createStatus" required>
                                        <option value="pending" selected>Oczekuje</option>
                                        <option value="completed">Zrealizowana</option>
                                    </select>
                                </div>

                                <div class="col-12" id="buyerEmailCol" style="display:none;">
                                    <label class="form-label">Email kupującego (PayU)</label>
                                    <input class="form-control" id="buyerEmail" type="email" placeholder="Email kupującego (opcjonalnie)">
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                            <button type="submit" class="btn btn-success" form="paymentCreateForm">
                                <i class="bi bi-check2"></i> Zapisz
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        setupPaymentsListeners({
            openCreateOnLoad,
            preselectInvoiceId,
            preselectJobId,
        });

        if (openCreateOnLoad) {
            // Open create flow immediately for routes like #/payments/new?invoice=2
            queueMicrotask(() => {
                openCreatePaymentModal({
                    invoiceId: preselectInvoiceId,
                    jobId: preselectJobId,
                    openedFromRoute: true,
                });
            });
        }

    } catch (error) {
        console.error('Failed to load payments:', error);
        showToast('Błąd ładowania płatności', 'danger');
    }
}

function setupPaymentsListeners(context = {}) {
    const { openCreateOnLoad, preselectInvoiceId, preselectJobId } = context;

    const openBtn = document.getElementById('openCreatePaymentBtn');
    const openBtn2 = document.getElementById('openCreatePaymentBtn2');

    const openHandler = () => {
        openCreatePaymentModal({
            invoiceId: preselectInvoiceId,
            jobId: preselectJobId,
            openedFromRoute: Boolean(openCreateOnLoad),
        });
    };

    openBtn?.addEventListener('click', openHandler);
    openBtn2?.addEventListener('click', openHandler);

    document.getElementById('statusFilter')?.addEventListener('change', (e) => {
        currentFilters.status = e.target.value;
        currentPage = 1;
        renderPayments();
    });

    document.getElementById('sourceFilter')?.addEventListener('change', (e) => {
        currentFilters.source = e.target.value;
        currentPage = 1;
        renderPayments();
    });

    document.getElementById('kindFilter')?.addEventListener('change', (e) => {
        currentFilters.kind = e.target.value;
        currentPage = 1;
        renderPayments();
    });

    document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
        currentFilters = {};
        currentPage = 1;
        renderPayments();
    });

    // Modal form listeners are attached when opening the modal.
}

async function openRefundPaymentModal(paymentId) {
    const modalEl = document.getElementById('paymentRefundModal');
    if (!modalEl) return;

    const form = document.getElementById('paymentRefundForm');
    const idEl = document.getElementById('refundPaymentId');
    const reasonEl = document.getElementById('refundReason');

    if (idEl) idEl.value = String(paymentId);
    if (reasonEl) reasonEl.value = '';

    const modal = new bootstrap.Modal(modalEl);

    // Clear inline errors while typing (avoid stacking listeners)
    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    // Avoid stacking submit listeners
    if (form && form.dataset.wiredSubmit !== '1') {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const pid = parseOptionalInt(idEl?.value);
            const reason = String(reasonEl?.value || '').trim();

            if (!pid) {
                console.error('Missing refund payment id');
                return;
            }
            if (!reason || reason.length < 3) {
                setFieldError(reasonEl, 'Podaj powód zwrotu (min. 3 znaki)');
                reasonEl?.focus?.();
                return;
            }

            try {
                await paymentsAPI.refund(pid, reason);
                modal.hide();
                showToast('success', 'Zwrot zrealizowany');
                await renderPayments();
            } catch (err) {
                console.error(err);
            }
        });
        form.dataset.wiredSubmit = '1';
    }

    modal.show();
    // Focus textarea after the modal is shown.
    setTimeout(() => reasonEl?.focus?.(), 50);
}

async function openCreatePaymentModal({ invoiceId = null, jobId = null, openedFromRoute = false } = {}) {
    const modalEl = document.getElementById('paymentCreateModal');
    if (!modalEl) return;

    const form = document.getElementById('paymentCreateForm');
    const sourceSelect = document.getElementById('createSource');
    const kindSelect = document.getElementById('createKind');
    const targetTypeSelect = document.getElementById('createTargetType');
    const invoiceSelect = document.getElementById('createInvoiceId');
    const jobSelect = document.getElementById('createJobId');
    const invoiceRow = document.getElementById('invoiceSelectRow');
    const jobRow = document.getElementById('jobSelectRow');

    const modal = new bootstrap.Modal(modalEl);

    const amountEl = document.getElementById('createAmount');

    const prefillAmountFromInvoice = () => {
        if (!amountEl || !invoiceSelect) return;
        // Do not prefill for PayU flow (amount field is hidden/irrelevant).
        if (sourceSelect?.value === 'payu') return;
        if (targetTypeSelect?.value !== 'invoice') return;

        const selected = invoiceSelect.selectedOptions?.[0];
        if (!selected || !selected.value) return;

        // Only prefill if empty or previously auto-filled.
        const alreadyAuto = amountEl.dataset.autofilledFromInvoice === '1';
        const hasUserValue = Boolean(String(amountEl.value || '').trim());
        if (hasUserValue && !alreadyAuto) return;

        const remaining = Number(selected.dataset.remaining || '');
        const total = Number(selected.dataset.total || '');

        const pick = (Number.isFinite(remaining) && remaining > 0)
            ? remaining
            : (Number.isFinite(total) && total > 0 ? total : null);

        if (pick === null) return;

        amountEl.value = String(pick.toFixed(2));
        amountEl.dataset.autofilledFromInvoice = '1';
    };

    // Clear inline errors while typing (avoid stacking listeners)
    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    // If user changes amount manually, stop auto-overwriting.
    if (amountEl && amountEl.dataset.wireManualOverride !== '1') {
        amountEl.addEventListener('input', () => {
            amountEl.dataset.autofilledFromInvoice = '0';
        });
        amountEl.dataset.wireManualOverride = '1';
    }

    // Populate lists
    await populateInvoiceAndJobLists({ invoiceId, jobId });

    // Preselect
    if (invoiceId) {
        targetTypeSelect.value = 'invoice';
        invoiceSelect.value = String(invoiceId);
    } else if (jobId) {
        targetTypeSelect.value = 'job';
        jobSelect.value = String(jobId);
    }

    // Ensure UI state is consistent
    const applyTargetVisibility = () => {
        const t = targetTypeSelect.value;
        if (invoiceRow) invoiceRow.style.display = (t === 'invoice') ? '' : 'none';
        if (jobRow) jobRow.style.display = (t === 'job') ? '' : 'none';

        if (invoiceSelect) invoiceSelect.required = (t === 'invoice');
        if (jobSelect) jobSelect.required = (t === 'job');
    };

    const applyKindDefaults = () => {
        const source = sourceSelect.value;
        const kind = kindSelect.value;

        if (source === 'payu') {
            kindSelect.value = 'invoice';
            kindSelect.disabled = true;
            targetTypeSelect.value = 'invoice';
            targetTypeSelect.disabled = true;
        } else {
            kindSelect.disabled = false;
            targetTypeSelect.disabled = false;

            // Simple flow: invoice payments -> invoice, deposits/prepayments -> job.
            if (kind === 'invoice') targetTypeSelect.value = 'invoice';
            if (kind === 'deposit' || kind === 'prepayment') targetTypeSelect.value = 'job';
        }

        toggleCreateMode();
        applyTargetVisibility();
        prefillAmountFromInvoice();
    };

    // Avoid stacking listeners when opening modal multiple times.
    sourceSelect.onchange = applyKindDefaults;
    kindSelect.onchange = applyKindDefaults;
    targetTypeSelect.onchange = () => {
        toggleCreateMode();
        applyTargetVisibility();
        prefillAmountFromInvoice();
    };

    if (invoiceSelect) {
        invoiceSelect.onchange = () => {
            prefillAmountFromInvoice();
        };
    }

    // Submit handler
    form.onsubmit = async (e) => {
        e.preventDefault();

        if (!validateRequiredFields(form)) {
            return;
        }

        const source = sourceSelect.value;
        const kind = kindSelect.value;
        const targetType = targetTypeSelect.value;

        const selectedInvoiceId = parseOptionalInt(invoiceSelect.value);
        const selectedJobId = parseOptionalInt(jobSelect.value);

        if (source === 'payu') {
            if (!selectedInvoiceId) {
                setFieldError(invoiceSelect, 'PayU wymaga wyboru faktury');
                invoiceSelect?.focus?.();
                return;
            }

            try {
                const buyerEmail = document.getElementById('buyerEmail').value || undefined;
                const res = await paymentsAPI.payuCreateOrder({ invoice_id: selectedInvoiceId, buyer_email: buyerEmail });
                const redirectUrl = res?.data?.redirect_url;
                if (redirectUrl) {
                    window.open(redirectUrl, '_blank');
                }
                modal.hide();

                // If this came from invoice flow, go back there.
                if (openedFromRoute && selectedInvoiceId) {
                    window.location.hash = `#/invoices/${selectedInvoiceId}`;
                } else {
                    await renderPayments();
                }
            } catch (err) {
                console.error(err);
            }
            return;
        }

        const amountEl = document.getElementById('createAmount');
        if (!requireNumberMin(amountEl, 0.01, 'Podaj kwotę > 0')) {
            return;
        }
        const amount = parseFloat(amountEl.value);
        const method = document.getElementById('createMethod').value;
        const status = document.getElementById('createStatus').value;

        if (targetType === 'invoice' && !selectedInvoiceId) {
            setFieldError(invoiceSelect, 'Wybierz fakturę');
            invoiceSelect?.focus?.();
            return;
        }
        if (targetType === 'job' && !selectedJobId) {
            setFieldError(jobSelect, 'Wybierz zlecenie');
            jobSelect?.focus?.();
            return;
        }

        try {
            await paymentsAPI.create({
                invoice_id: targetType === 'invoice' ? selectedInvoiceId : undefined,
                job_id: targetType === 'job' ? selectedJobId : undefined,
                amount,
                currency: 'PLN',
                kind,
                source,
                payment_method: method,
                status,
            });

            modal.hide();

            if (openedFromRoute && selectedInvoiceId) {
                window.location.hash = `#/invoices/${selectedInvoiceId}`;
                return;
            }
            if (openedFromRoute && selectedJobId) {
                window.location.hash = `#/jobs/${selectedJobId}`;
                return;
            }

            await renderPayments();
        } catch (err) {
            console.error(err);
        }
    };

    // If user entered via #/payments/new, leaving modal should take them back to the list.
    modalEl.onhidden = () => {
        const hash = window.location.hash || '';
        if (openedFromRoute && hash.startsWith('#/payments/new')) {
            window.location.hash = '#/payments';
        }
    };

    applyKindDefaults();
    // If invoice preselected, prefill amount immediately.
    prefillAmountFromInvoice();
    modal.show();
}

async function populateInvoiceAndJobLists({ invoiceId = null, jobId = null } = {}) {
    const invoiceSelect = document.getElementById('createInvoiceId');
    const jobSelect = document.getElementById('createJobId');

    if (invoiceSelect) {
        invoiceSelect.innerHTML = '<option value="">Wybierz fakturę…</option>';
    }
    if (jobSelect) {
        jobSelect.innerHTML = '<option value="">Wybierz zlecenie…</option>';
    }

    try {
        const [invRes, jobRes] = await Promise.all([
            invoicesAPI.getAll({}, 1),
            jobsAPI.getAll({}, 1),
        ]);

        const invoices = invRes?.data || [];
        const jobs = jobRes?.data || [];

        const ensureInvoice = async () => {
            if (!invoiceId) return;
            if (invoices.some(i => i.id === invoiceId)) return;
            try {
                const single = await invoicesAPI.getById(invoiceId);
                if (single?.data) invoices.unshift(single.data);
            } catch (_) { /* ignore */ }
        };

        const ensureJob = async () => {
            if (!jobId) return;
            if (jobs.some(j => j.id === jobId)) return;
            try {
                const single = await jobsAPI.getById(jobId);
                if (single?.data) jobs.unshift(single.data);
            } catch (_) { /* ignore */ }
        };

        await Promise.all([ensureInvoice(), ensureJob()]);

        // Sort: invoices with highest remaining first; jobs by nearest event date (undated last)
        const invoiceRemaining = (inv) => {
            const total = Number(inv?.total_gross ?? inv?.total_amount ?? 0);
            const paid = Number(inv?.paid_amount ?? 0);
            const remaining = (inv?.remaining_amount !== undefined && inv?.remaining_amount !== null)
                ? Number(inv.remaining_amount)
                : Math.max(0, total - paid);
            return Number.isFinite(remaining) ? remaining : 0;
        };

        invoices.sort((a, b) => {
            const ra = invoiceRemaining(a);
            const rb = invoiceRemaining(b);
            if (rb !== ra) return rb - ra;
            return (b?.id || 0) - (a?.id || 0);
        });

        const jobEventTs = (job) => {
            if (!job?.event_date) return null;
            const t = new Date(job.event_date).getTime();
            return Number.isFinite(t) ? t : null;
        };

        jobs.sort((a, b) => {
            const ta = jobEventTs(a);
            const tb = jobEventTs(b);
            const aMissing = ta === null;
            const bMissing = tb === null;
            if (aMissing && !bMissing) return 1;
            if (!aMissing && bMissing) return -1;
            if (!aMissing && !bMissing && ta !== tb) return ta - tb;
            return (b?.id || 0) - (a?.id || 0);
        });

        if (invoiceSelect) {
            invoices.forEach(inv => {
                const invoiceNumber = inv.invoice_number || ('#' + inv.id);
                const customerName = inv.customer_name ? ` — ${inv.customer_name}` : '';

                const total = Number(inv.total_gross ?? inv.total_amount ?? 0);
                const paid = Number(inv.paid_amount ?? 0);
                const remaining = (inv.remaining_amount !== undefined && inv.remaining_amount !== null)
                    ? Number(inv.remaining_amount)
                    : Math.max(0, total - paid);

                const remainingPart = Number.isFinite(remaining) && (remaining > 0)
                    ? ` — pozostało ${formatCurrency(remaining, inv.currency || 'PLN')}`
                    : '';

                const label = `${invoiceNumber}${customerName}${remainingPart}`;
                const opt = document.createElement('option');
                opt.value = String(inv.id);
                opt.textContent = label;
                opt.dataset.total = String(total);
                opt.dataset.remaining = String(remaining);
                invoiceSelect.appendChild(opt);
            });
        }

        if (jobSelect) {
            jobs.forEach(job => {
                const customerName = job.customer?.display_name || job.customer?.full_name || '';
                const eventDate = formatDateShort(job.event_date);
                const datePart = eventDate ? ` — ${eventDate}` : '';
                const label = `#${job.id}${customerName ? ' — ' + customerName : ''}${job.title ? ' — ' + job.title : ''}${datePart}`;
                const opt = document.createElement('option');
                opt.value = String(job.id);
                opt.textContent = label;
                jobSelect.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('Failed to load invoice/job lists for payment modal:', err);
        if (invoiceSelect) {
            invoiceSelect.innerHTML = '<option value="">Nie udało się załadować faktur</option>';
        }
        if (jobSelect) {
            jobSelect.innerHTML = '<option value="">Nie udało się załadować zleceń</option>';
        }
    }
}

function toggleCreateMode() {
    const source = document.getElementById('createSource')?.value;
    const buyerEmailCol = document.getElementById('buyerEmailCol');
    const amountCol = document.getElementById('amountCol');
    const methodCol = document.getElementById('methodCol');
    const statusCol = document.getElementById('statusCol');

    const isPayu = source === 'payu';

    if (buyerEmailCol) buyerEmailCol.style.display = isPayu ? '' : 'none';
    if (amountCol) amountCol.style.display = isPayu ? 'none' : '';
    if (methodCol) methodCol.style.display = isPayu ? 'none' : '';
    if (statusCol) statusCol.style.display = isPayu ? 'none' : '';

    const amount = document.getElementById('createAmount');
    const method = document.getElementById('createMethod');

    if (amount) amount.required = !isPayu;
    if (method) method.required = !isPayu;
}

function formatCurrency(amount, currency = 'PLN') {
    const n = Number(amount || 0);
    return `${n.toFixed(2)} ${currency}`;
}

function renderInvoiceCell(p) {
    const inv = p?.invoice;
    if (!inv?.id) return '-';

    const invoiceNumber = escapeHtml(inv.invoice_number || ('#' + inv.id));
    const customerName = inv.customer_name ? escapeHtml(inv.customer_name) : '';

    return `
        <div>
            <a href="#/invoices/${inv.id}">${invoiceNumber}</a>
            ${customerName ? `<div class="text-muted small">${customerName}</div>` : ''}
        </div>

            <!-- Refund Payment Modal -->
            <div class="modal fade" id="paymentRefundModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-arrow-counterclockwise"></i> Zwrot płatności</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="paymentRefundForm" novalidate>
                                <input type="hidden" id="refundPaymentId" />
                                <div class="mb-3">
                                    <label class="form-label" for="refundReason">Powód zwrotu</label>
                                    <textarea class="form-control" id="refundReason" rows="3" required></textarea>
                                    <div class="form-text">Wymagane (min. 3 znaki)</div>
                                </div>
                                <div class="d-flex justify-content-end gap-2">
                                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                                    <button type="submit" class="btn btn-warning">Wykonaj zwrot</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
    `;
}

function renderJobCell(p) {
    const job = p?.job || p?.invoice?.job;
    if (!job?.id) return '-';

    const title = job.title ? escapeHtml(job.title) : '';
    const idPart = `#${job.id}`;

    return `
        <div>
            <a href="#/jobs/${job.id}">${escapeHtml(idPart)}</a>
            ${title ? `<div class="text-muted small">${title}</div>` : ''}
        </div>
    `;
}

function escapeHtml(str) {
    return String(str ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatDateTime(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('pl-PL');
}

function formatDateShort(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('pl-PL');
}

function statusColor(status) {
    if (status === 'completed') return 'success';
    if (status === 'pending') return 'warning';
    if (status === 'failed') return 'danger';
    if (status === 'refunded') return 'secondary';
    return 'secondary';
}

function statusLabel(status) {
    if (status === 'completed') return 'Zrealizowana';
    if (status === 'pending') return 'Oczekuje';
    if (status === 'failed') return 'Nieudana';
    if (status === 'refunded') return 'Zwrócona';
    return status || '-';
}

function formatSource(source) {
    if (source === 'payu') return 'PayU';
    if (source === 'manual') return 'Manual';
    return source || '-';
}

function formatKind(kind) {
    if (kind === 'invoice') return 'Do faktury';
    if (kind === 'deposit') return 'Zaliczka';
    if (kind === 'prepayment') return 'Przedpłata';
    return kind || '-';
}

window.goToPaymentsPage = (page) => {
    currentPage = page;
    renderPayments();
};

window.completePayment = async (id) => {
    const ok = await confirmDialog({
        title: 'Potwierdź płatność',
        message: 'Potwierdzić tę płatność?',
        confirmText: 'Potwierdź',
        cancelText: 'Anuluj',
        danger: false,
    });
    if (!ok) return;
    try {
        await paymentsAPI.complete(id);
        await renderPayments();
    } catch (err) {
        console.error(err);
    }
};

window.refundPayment = async (id) => {
    await openRefundPaymentModal(id);
};

window.deletePayment = async (id) => {
    const ok = await confirmDialog({
        title: 'Usuń płatność',
        message: 'Usunąć tę płatność? (tylko pending)',
        confirmText: 'Usuń',
        cancelText: 'Anuluj',
        danger: true,
    });
    if (!ok) return;
    try {
        await paymentsAPI.delete(id);
        await renderPayments();
    } catch (err) {
        console.error(err);
    }
};

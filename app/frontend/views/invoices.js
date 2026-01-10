/**
 * Invoices View - Zarządzanie fakturami
 */

import { invoicesAPI, jobsAPI, apiDownload } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { confirmDialog } from '../confirm.js';

let currentPage = 1;
let currentFilters = {};

export async function renderInvoices(params) {
    const container = document.getElementById('viewContainer');
    
    // Check if viewing invoice for specific job
    if (params && params[0] === 'job' && params[1]) {
        return renderInvoiceForJob(parseInt(params[1]));
    }

    // New: create correction invoice for an existing invoice
    if (params && params[0] && params[1] === 'correction') {
        return renderCorrectionForm(parseInt(params[0]));
    }
    
    if (params && params[0] === 'new') {
        return renderInvoiceForm(null);
    }
    
    if (params && params[0]) {
        return renderInvoiceDetails(parseInt(params[0]));
    }
    
    // Show loading
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-receipt"></i> Faktury</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await invoicesAPI.getAll(currentFilters, currentPage);
        const invoices = response.data || [];
        const pagination = response.pagination || { page: 1, pages: 1, total: 0 };
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-receipt"></i> Faktury</h1>
                    <p class="text-muted mb-0">Zarządzanie fakturami VAT</p>
                </div>
            </div>
            
            <!-- Filters -->
            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <select class="form-select" id="statusFilter">
                                <option value="">Wszystkie statusy</option>
                                <option value="draft" ${currentFilters.status === 'draft' ? 'selected' : ''}>Szkic</option>
                                <option value="issued" ${currentFilters.status === 'issued' ? 'selected' : ''}>Wystawione</option>
                                <option value="sent" ${currentFilters.status === 'sent' ? 'selected' : ''}>Wysłane</option>
                                <option value="paid" ${currentFilters.status === 'paid' ? 'selected' : ''}>Opłacone</option>
                                <option value="cancelled" ${currentFilters.status === 'cancelled' ? 'selected' : ''}>Anulowane</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="paymentStatusFilter">
                                <option value="">Wszystkie płatności</option>
                                <option value="unpaid" ${currentFilters.payment_status === 'unpaid' ? 'selected' : ''}>Nieopłacone</option>
                                <option value="partial" ${currentFilters.payment_status === 'partial' ? 'selected' : ''}>Częściowo</option>
                                <option value="paid" ${currentFilters.payment_status === 'paid' ? 'selected' : ''}>Opłacone</option>
                                <option value="overpaid" ${currentFilters.payment_status === 'overpaid' ? 'selected' : ''}>Nadpłacone</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <input type="month" class="form-control" id="monthFilter" 
                                   value="${currentFilters.month || ''}">
                        </div>
                        <div class="col-md-3">
                            <button class="btn btn-outline-secondary w-100" id="resetFiltersBtn">
                                <i class="bi bi-x-circle"></i> Wyczyść filtry
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Invoices Table -->
            <div class="card">
                ${invoices.length === 0 ? `
                    <div class="card-body text-center py-5">
                        <i class="bi bi-inbox display-1 text-muted"></i>
                        <p class="text-muted mt-3">Brak faktur</p>
                    </div>
                ` : `
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>Numer</th>
                                    <th>Klient</th>
                                    <th>Data wystawienia</th>
                                    <th>Termin płatności</th>
                                    <th>Kwota</th>
                                    <th>Zapłacono</th>
                                    <th>Status</th>
                                    <th>Akcje</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${invoices.map(invoice => `
                                    <tr onclick="window.location.hash='#/invoices/${invoice.id}'" style="cursor: pointer;">
                                        <td><strong>${invoice.invoice_number}</strong></td>
                                        <td>${invoice.customer_name || '-'}</td>
                                        <td>${formatDateShort(invoice.issue_date)}</td>
                                        <td>${formatDateShort(invoice.payment_deadline)}</td>
                                        <td><strong>${formatCurrency(invoice.total_gross)}</strong></td>
                                        <td>${formatCurrency(invoice.paid_amount)}</td>
                                        <td>
                                            <span class="badge bg-${getPaymentStatusColor(invoice.payment_status)}">
                                                ${getPaymentStatusLabel(invoice.payment_status)}
                                            </span>
                                        </td>
                                        <td>
                                            <div class="btn-group btn-group-sm">
                                                                <button class="btn btn-outline-primary" 
                                                                    title="PDF" onclick="openInvoicePdf(${invoice.id}, '${invoice.invoice_number}'); event.stopPropagation()">
                                                    <i class="bi bi-file-pdf"></i>
                                                                </button>
                                                ${invoice.status === 'draft' ? `
                                                    <button class="btn btn-outline-danger" 
                                                            onclick="deleteInvoice(${invoice.id}); event.stopPropagation();" 
                                                            title="Usuń">
                                                        <i class="bi bi-trash"></i>
                                                    </button>
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
                                Strona ${pagination.page} z ${pagination.pages} (${pagination.total} faktur)
                            </div>
                            ${pagination.pages > 1 ? `
                                <nav>
                                    <ul class="pagination mb-0">
                                        <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                            <a class="page-link" href="#" onclick="goToInvoicesPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                        </li>
                                        ${Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                                            const pageNum = i + 1;
                                            return `
                                                <li class="page-item ${pageNum === pagination.page ? 'active' : ''}">
                                                    <a class="page-link" href="#" onclick="goToInvoicesPage(${pageNum}); return false;">${pageNum}</a>
                                                </li>
                                            `;
                                        }).join('')}
                                        <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                            <a class="page-link" href="#" onclick="goToInvoicesPage(${pagination.page + 1}); return false;">Następna</a>
                                        </li>
                                    </ul>
                                </nav>
                            ` : ''}
                        </div>
                    </div>
                `}
            </div>
        `;
        
        setupInvoicesListeners();
        
    } catch (error) {
        console.error('Failed to load invoices:', error);
        showToast('Błąd ładowania faktur', 'danger');
    }
}

function setupInvoicesListeners() {
    document.getElementById('statusFilter')?.addEventListener('change', (e) => {
        currentFilters.status = e.target.value;
        currentPage = 1;
        renderInvoices();
    });
    
    document.getElementById('paymentStatusFilter')?.addEventListener('change', (e) => {
        currentFilters.payment_status = e.target.value;
        currentPage = 1;
        renderInvoices();
    });
    
    document.getElementById('monthFilter')?.addEventListener('change', (e) => {
        currentFilters.month = e.target.value;
        currentPage = 1;
        renderInvoices();
    });
    
    document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
        currentFilters = {};
        currentPage = 1;
        renderInvoices();
    });
}

window.goToInvoicesPage = (page) => {
    currentPage = page;
    renderInvoices();
};

window.deleteInvoice = async (id) => {
    const ok = await confirmDialog({
        title: 'Anuluj fakturę',
        message: 'Czy na pewno chcesz anulować tę fakturę (tylko szkic)?',
        confirmText: 'Anuluj',
        cancelText: 'Wróć',
        danger: true,
    });
    if (!ok) {
        return;
    }
    
    try {
        await invoicesAPI.delete(id);
        renderInvoices();
    } catch (error) {
        console.error('Failed to delete invoice:', error);
    }
};

async function renderInvoiceForJob(jobId) {
    const container = document.getElementById('viewContainer');
    
    try {
        const [invoicesResponse, jobResponse] = await Promise.all([
            invoicesAPI.getAll({ job_id: jobId }),
            jobsAPI.getById(jobId),
        ]);
        const job = jobResponse.data;
        const invoices = invoicesResponse.data || [];

        const normType = (t) => (t || 'final');
        const depositInvoices = invoices.filter((i) => normType(i.invoice_type) === 'deposit');
        const finalInvoices = invoices.filter((i) => ['final', 'standard'].includes(normType(i.invoice_type)));

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-receipt"></i> Faktury dla zlecenia #${jobId}</h1>
                    <p class="text-muted mb-0">${escapeHtml(job?.title || '')}</p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs/${jobId}'">
                        <i class="bi bi-arrow-left"></i> Zlecenie
                    </button>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header"><strong>Akcje</strong></div>
                <div class="card-body d-flex gap-2 flex-wrap">
                    ${depositInvoices.length === 0 ? `
                        <button class="btn btn-outline-warning" onclick="createDepositInvoiceForJob(${jobId})">
                            <i class="bi bi-cash-coin"></i> Wystaw fakturę zaliczkową
                        </button>
                    ` : ''}
                    ${finalInvoices.length === 0 ? `
                        <button class="btn btn-outline-primary" onclick="createFinalInvoiceForJob(${jobId})">
                            <i class="bi bi-receipt"></i> Wystaw fakturę końcową VAT
                        </button>
                    ` : ''}
                </div>
            </div>

            <div class="card">
                <div class="card-header"><strong>Lista faktur</strong></div>
                <div class="card-body">
                    ${invoices.length === 0 ? `
                        <div class="text-muted">Brak faktur dla tego zlecenia.</div>
                    ` : `
                        <div class="list-group">
                            ${invoices.map((inv) => {
                                const type = normType(inv.invoice_type);
                                const typeLabel = type === 'deposit' ? 'Zaliczkowa' : (type === 'correction' ? 'Korygująca' : 'VAT');
                                return `
                                    <a class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                                       href="#/invoices/${inv.id}">
                                        <div>
                                            <div><strong>${inv.invoice_number}</strong></div>
                                            <div class="text-muted small">${typeLabel} • ${formatDateShort(inv.issue_date || inv.created_at)}</div>
                                        </div>
                                        <span class="badge bg-${getPaymentStatusColor(inv.payment_status)}">${getPaymentStatusLabel(inv.payment_status)}</span>
                                    </a>
                                `;
                            }).join('')}
                        </div>
                    `}
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to create invoice for job:', error);
        showToast('Błąd ładowania faktur dla zlecenia', 'danger');
        navigate('/jobs');
    }
}

window.createDepositInvoiceForJob = async (jobId) => {
    try {
        const resp = await invoicesAPI.createDeposit(jobId, { successMessage: 'Faktura zaliczkowa wygenerowana' });
        navigate(`/invoices/${resp.data.id}`);
    } catch (e) {
        console.error(e);
        showToast('Nie udało się wystawić faktury zaliczkowej', 'danger');
    }
};

window.createFinalInvoiceForJob = async (jobId) => {
    try {
        const resp = await invoicesAPI.createFinal(jobId, { successMessage: 'Faktura końcowa wygenerowana' });
        navigate(`/invoices/${resp.data.id}`);
    } catch (e) {
        console.error(e);
        showToast('Nie udało się wystawić faktury końcowej', 'danger');
    }
};

async function renderInvoiceDetails(invoiceId) {
    const container = document.getElementById('viewContainer');
    
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await invoicesAPI.getById(invoiceId);
        const invoice = response.data;

        const invoiceType = String(invoice.invoice_type || 'final');
        const invoiceTitle = invoiceType === 'deposit'
            ? 'FAKTURA VAT ZALICZKOWA'
            : (invoiceType === 'correction' ? 'FAKTURA KORYGUJĄCA' : 'FAKTURA VAT');
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-receipt"></i> Faktura ${invoice.invoice_number}</h1>
                    <span class="badge bg-${getPaymentStatusColor(invoice.payment_status)} fs-6">
                        ${getPaymentStatusLabel(invoice.payment_status)}
                    </span>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-primary" onclick="window.openInvoicePdf(${invoice.id}, '${String(invoice.invoice_number).replace(/'/g, "\\'")}');">
                        <i class="bi bi-file-pdf"></i> PDF
                    </button>
                    ${invoiceType !== 'correction' ? `
                        <button class="btn btn-outline-warning" onclick="window.location.hash='#/invoices/${invoice.id}/correction'">
                            <i class="bi bi-arrow-repeat"></i> Korekta
                        </button>
                    ` : ''}
                    ${invoice.status === 'draft' || invoice.status === 'issued' ? `
                        <button class="btn btn-success" onclick="sendInvoice(${invoice.id})">
                            <i class="bi bi-send"></i> Wyślij
                        </button>
                    ` : ''}
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/invoices'">
                        <i class="bi bi-arrow-left"></i> Lista
                    </button>
                </div>
            </div>
            
            <div class="row">
                <div class="col-lg-8">
                    <!-- Invoice Preview -->
                    <div class="card mb-4">
                        <div class="card-body p-4">
                            <div class="row mb-4">
                                <div class="col-6">
                                    <h3>${invoiceTitle}</h3>
                                    <p class="mb-0"><strong>${invoice.invoice_number}</strong></p>
                                    ${invoiceType === 'correction' && invoice.original_invoice_number ? `
                                        <p class="mb-0 text-muted small">Koryguje: <strong>${invoice.original_invoice_number}</strong></p>
                                    ` : ''}
                                    ${invoiceType === 'correction' && invoice.correction_reason ? `
                                        <p class="mb-0 text-muted small">Powód: ${escapeHtml(invoice.correction_reason)}</p>
                                    ` : ''}
                                </div>
                                <div class="col-6 text-end">
                                    <p class="mb-1"><strong>Data wystawienia:</strong> ${formatDateShort(invoice.issue_date)}</p>
                                    <p class="mb-1"><strong>Termin płatności:</strong> ${formatDateShort(invoice.payment_deadline)}</p>
                                    <p class="mb-0"><strong>Metoda płatności:</strong> ${invoice.payment_method || 'Przelew'}</p>
                                </div>
                            </div>
                            
                            <div class="row mb-4">
                                <div class="col-6">
                                    <h6>Sprzedawca:</h6>
                                    <p class="mb-0">${invoice.seller_name}<br>
                                    ${invoice.seller_address}<br>
                                    ${invoice.seller_nip ? `NIP: ${invoice.seller_nip}` : ''}</p>
                                </div>
                                <div class="col-6">
                                    <h6>Nabywca:</h6>
                                    <p class="mb-0">${invoice.customer_name}<br>
                                    ${invoice.customer_address || ''}<br>
                                    ${invoice.customer_nip ? `NIP: ${invoice.customer_nip}` : ''}</p>
                                </div>
                            </div>
                            
                            <!-- Invoice Items -->
                            <table class="table table-bordered">
                                <thead class="table-light">
                                    <tr>
                                        <th>Lp</th>
                                        <th>Nazwa</th>
                                        <th>Ilość</th>
                                        <th>Cena netto</th>
                                        <th>VAT</th>
                                        <th>Wartość brutto</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${(invoice.items || []).map((item, index) => `
                                        <tr>
                                            <td>${index + 1}</td>
                                            <td>${item.description}</td>
                                            <td>${item.quantity}</td>
                                            <td>${formatCurrency(item.unit_price_net)}</td>
                                            <td>${item.vat_rate}%</td>
                                            <td>${formatCurrency(item.total_gross)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                                <tfoot class="table-light">
                                    <tr>
                                        <th colspan="5" class="text-end">Razem netto:</th>
                                        <th>${formatCurrency(invoice.total_net)}</th>
                                    </tr>
                                    <tr>
                                        <th colspan="5" class="text-end">VAT:</th>
                                        <th>${formatCurrency(invoice.total_vat)}</th>
                                    </tr>
                                    <tr>
                                        <th colspan="5" class="text-end">Razem brutto:</th>
                                        <th class="text-success">${formatCurrency(invoice.total_gross)}</th>
                                    </tr>
                                </tfoot>
                            </table>
                            
                            ${invoice.notes ? `
                                <div class="mt-3">
                                    <strong>Uwagi:</strong>
                                    <p class="mb-0">${invoice.notes}</p>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-4">
                    <!-- Payment Info -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-cash-coin"></i> Płatności</h5>
                        </div>
                        <div class="card-body">
                            <div class="d-flex justify-content-between mb-2">
                                <span>Do zapłaty:</span>
                                <strong>${formatCurrency(invoice.total_gross)}</strong>
                            </div>
                            <div class="d-flex justify-content-between mb-2">
                                <span>Zapłacono:</span>
                                <strong class="text-success">${formatCurrency(invoice.paid_amount)}</strong>
                            </div>
                            <hr>
                            <div class="d-flex justify-content-between">
                                <strong>Pozostało:</strong>
                                <strong class="text-${invoice.remaining_amount > 0 ? 'danger' : 'success'}">
                                    ${formatCurrency(invoice.remaining_amount)}
                                </strong>
                            </div>
                            
                            ${invoice.payment_status !== 'paid' ? `
                                <button class="btn btn-success w-100 mt-3" onclick="window.location.hash='#/payments/new?invoice=${invoice.id}'">
                                    <i class="bi bi-plus-lg"></i> Dodaj płatność
                                </button>
                            ` : ''}
                        </div>
                    </div>
                    
                    <!-- Related Job -->
                    ${invoice.job ? `
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="bi bi-briefcase"></i> Zlecenie</h5>
                            </div>
                            <div class="card-body">
                                <p><strong>#${invoice.job.id}</strong></p>
                                <p>${invoice.job.offer?.name}</p>
                                <p class="text-muted mb-0">${formatDate(invoice.job.event_date)}</p>
                                <a href="#/jobs/${invoice.job_id}" class="btn btn-sm btn-outline-primary mt-2">
                                    Zobacz zlecenie
                                </a>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to load invoice:', error);
        showToast('Nie znaleziono faktury', 'danger');
        navigate('/invoices');
    }
}

window.openInvoicePdf = async (invoiceId, invoiceNumber) => {
    // Open a window immediately to avoid popup blockers, then navigate it once blob is ready.
    const w = window.open('', '_blank');
    if (!w) {
        showToast('Przeglądarka zablokowała otwarcie nowej karty', 'warning');
        return;
    }

    try {
        const res = await apiDownload(`/invoices/${invoiceId}/pdf`, { showLoading: true });
        if (!res?.blob) {
            w.close();
            return;
        }

        const blobUrl = URL.createObjectURL(res.blob);
        w.location = blobUrl;

        // Attempt to suggest filename when user downloads from the PDF viewer.
        w.document.title = res.filename || `${invoiceNumber || 'invoice'}\.pdf`;

        // Revoke after some time (PDF viewer might still be reading it).
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (err) {
        console.error(err);
        try { w.close(); } catch (_) { /* ignore */ }
    }
};

window.sendInvoice = async (invoiceId) => {
    const ok = await confirmDialog({
        title: 'Wyślij fakturę',
        message: 'Czy na pewno chcesz wysłać fakturę do klienta?',
        confirmText: 'Wyślij',
        cancelText: 'Anuluj',
        danger: false,
    });
    if (!ok) {
        return;
    }
    
    try {
        await invoicesAPI.send(invoiceId);
        renderInvoiceDetails(invoiceId);
    } catch (error) {
        console.error('Failed to send invoice:', error);
    }
};

function getPaymentStatusColor(status) {
    const colors = {
        'unpaid': 'danger',
        'partial': 'warning',
        'paid': 'success',
        'overpaid': 'info',
    };
    return colors[status] || 'secondary';
}

function getPaymentStatusLabel(status) {
    const labels = {
        'unpaid': 'Nieopłacone',
        'partial': 'Częściowo',
        'paid': 'Opłacone',
        'overpaid': 'Nadpłacone',
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
        day: 'numeric'
    });
}

function formatDateShort(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('pl-PL');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str ?? '');
    return div.innerHTML;
}

async function renderCorrectionForm(originalInvoiceId) {
    const container = document.getElementById('viewContainer');

    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const resp = await invoicesAPI.getById(originalInvoiceId);
        const original = resp.data;

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-arrow-repeat"></i> Faktura korygująca</h1>
                    <p class="text-muted mb-0">Korygowana: <strong>${escapeHtml(original.invoice_number)}</strong></p>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/invoices/${originalInvoiceId}'">
                        <i class="bi bi-arrow-left"></i> Powrót
                    </button>
                </div>
            </div>

            <div class="card">
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">Powód korekty</label>
                        <input id="correctionReason" class="form-control" placeholder="np. zmiana zakresu usługi / rabat / błąd w cenie" />
                        <div class="form-text">Pozycje poniżej wpisuj jako różnice (+ / -) w wartościach netto.</div>
                    </div>

                    <div class="table-responsive">
                        <table class="table table-bordered align-middle">
                            <thead class="table-light">
                                <tr>
                                    <th>Opis</th>
                                    <th style="width:120px">Ilość</th>
                                    <th style="width:180px">Cena netto</th>
                                    <th style="width:70px"></th>
                                </tr>
                            </thead>
                            <tbody id="correctionItemsBody"></tbody>
                        </table>
                    </div>

                    <div class="d-flex gap-2">
                        <button class="btn btn-outline-secondary" id="addCorrectionRowBtn">
                            <i class="bi bi-plus-circle"></i> Dodaj pozycję
                        </button>
                        <button class="btn btn-warning" id="submitCorrectionBtn">
                            <i class="bi bi-check2"></i> Utwórz korektę
                        </button>
                    </div>
                </div>
            </div>
        `;

        const bodyEl = container.querySelector('#correctionItemsBody');
        const addBtn = container.querySelector('#addCorrectionRowBtn');
        const submitBtn = container.querySelector('#submitCorrectionBtn');

        const addRow = (name = '', qty = 1, unit = 0) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input class="form-control form-control-sm js-name" value="${escapeHtml(name)}" placeholder="np. Rabat / dopłata" /></td>
                <td><input type="number" step="0.01" class="form-control form-control-sm js-qty" value="${qty}" /></td>
                <td><input type="number" step="0.01" class="form-control form-control-sm js-unit" value="${unit}" /></td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-danger js-remove" title="Usuń">
                        <i class="bi bi-x"></i>
                    </button>
                </td>
            `;
            tr.querySelector('.js-remove').addEventListener('click', (e) => {
                e.preventDefault();
                tr.remove();
            });
            bodyEl.appendChild(tr);
        };

        addRow('Korekta', 1, 0);

        addBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            addRow('', 1, 0);
        });

        submitBtn?.addEventListener('click', async (e) => {
            e.preventDefault();
            const reason = String(container.querySelector('#correctionReason')?.value || '').trim();
            const rows = Array.from(bodyEl.querySelectorAll('tr'));
            const items = rows
                .map((tr) => {
                    const name = String(tr.querySelector('.js-name')?.value || '').trim();
                    const qty = parseFloat(String(tr.querySelector('.js-qty')?.value || '0'));
                    const unit = parseFloat(String(tr.querySelector('.js-unit')?.value || '0'));
                    if (!name) return null;
                    if (!Number.isFinite(qty) || !Number.isFinite(unit)) return null;
                    return { name, quantity: qty, unit_price: unit, total: qty * unit };
                })
                .filter(Boolean);

            if (items.length === 0) {
                showToast('Dodaj przynajmniej jedną pozycję korekty', 'warning');
                return;
            }

            try {
                submitBtn.disabled = true;
                const created = await invoicesAPI.createCorrection(originalInvoiceId, { correction_reason: reason, items });
                navigate(`/invoices/${created.data.id}`);
            } catch (err) {
                console.error(err);
                showToast('Nie udało się utworzyć korekty', 'danger');
            } finally {
                submitBtn.disabled = false;
            }
        });
    } catch (err) {
        console.error(err);
        showToast('Nie udało się wczytać faktury', 'danger');
        navigate('/invoices');
    }
}

function renderInvoiceForm(invoiceId) {
    const container = document.getElementById('viewContainer');
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-receipt"></i> Nowa faktura</h1>
        </div>
        <div class="alert alert-info" role="alert">
            Faktury generują się automatycznie ze zleceń. Przejdź do widoku zlecenia i użyj przycisku "Faktura".
        </div>
    `;
}

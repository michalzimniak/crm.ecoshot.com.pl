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
        title: 'Usuń fakturę',
        message: 'Czy na pewno chcesz usunąć tę fakturę?',
        confirmText: 'Usuń',
        cancelText: 'Anuluj',
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
        // Check if invoice already exists for this job
        const invoicesResponse = await invoicesAPI.getAll({ job_id: jobId });
        const existingInvoices = invoicesResponse.data || [];
        
        if (existingInvoices.length > 0) {
            return renderInvoiceDetails(existingInvoices[0].id);
        }
        
        // Get job data
        const jobResponse = await jobsAPI.getById(jobId);
        const job = jobResponse.data;
        
        // Auto-create invoice from job
        const invoiceData = {
            job_id: jobId,
            payment_term_days: 14,
        };
        
        const response = await invoicesAPI.create(invoiceData, { successMessage: 'Faktura wygenerowana automatycznie' });
        navigate(`/invoices/${response.data.id}`);
        
    } catch (error) {
        console.error('Failed to create invoice for job:', error);
        showToast('Błąd tworzenia faktury', 'danger');
        navigate('/jobs');
    }
}

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
                                    <h3>FAKTURA VAT</h3>
                                    <p class="mb-0"><strong>${invoice.invoice_number}</strong></p>
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

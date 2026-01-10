/**
 * Contracts View - Zarządzanie umowami
 */

import { contractsAPI, jobsAPI } from '../api.js';
import { clearAuth, getStoredAuth, scheduleLoginRedirect } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { validateRequiredFields, wireClearOnInput } from '../forms.js';
import { confirmDialog } from '../confirm.js';

let currentContractsPage = 1;

function getDepositStatusColor(status) {
    const colors = {
        'paid': 'success',
        'waived': 'secondary',
        'unpaid': 'warning',
    };
    return colors[status] || 'warning';
}

function getDepositStatusLabel(status) {
    const labels = {
        'paid': 'Opłacona',
        'waived': 'Odstąpiono',
        'unpaid': 'Nieopłacona',
    };
    return labels[status] || (status || '—');
}

export async function renderContracts(params) {
    const container = document.getElementById('viewContainer');
    
    // Check if viewing contract for specific job
    if (params && params[0] === 'job' && params[1]) {
        return renderContractForJob(parseInt(params[1]));
    }
    
    if (params && params[0]) {
        return renderContractDetails(parseInt(params[0]));
    }

    // Contracts list
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-file-earmark-text"></i> Umowy</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const response = await contractsAPI.getAll({}, currentContractsPage);
        const contracts = response.data || [];
        const pagination = response.pagination || { page: 1, pages: 1, total: contracts.length, per_page: 50 };

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-file-earmark-text"></i> Umowy</h1>
                    <p class="text-muted mb-0">Lista umów wygenerowanych w systemie</p>
                </div>
            </div>

            ${contracts.length === 0 ? `
                <div class="card">
                    <div class="card-body text-center py-5">
                        <i class="bi bi-inbox display-1 text-muted"></i>
                        <p class="text-muted mt-3 mb-0">Brak umów</p>
                    </div>
                </div>
            ` : `
                <div class="card">
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>Status</th>
                                    <th>Zlecenie</th>
                                    <th>Klient</th>
                                    <th>Skan</th>
                                    <th>Zaliczka</th>
                                    <th>Utworzono</th>
                                    <th class="text-end">Akcje</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${contracts.map(c => `
                                    <tr>
                                        <td>
                                            <a href="#/contracts/${c.id}">${c.contract_number || ('#' + c.id)}</a>
                                        </td>
                                        <td>
                                            <span class="badge bg-${getContractStatusColor(c.status)}">${getContractStatusLabel(c.status)}</span>
                                        </td>
                                        <td>
                                            ${(() => {
                                                const jobId = c.job_id ?? c.job?.id;
                                                if (!jobId) return `<span class="text-muted">—</span>`;
                                                return `<a href="#/jobs/${jobId}">#${jobId}</a>`;
                                            })()}
                                            ${c.job?.title ? `<div class="text-muted small">${c.job.title}</div>` : ''}
                                        </td>
                                        <td>
                                            ${c.job?.customer?.display_name || c.job?.customer?.full_name || '-'}
                                        </td>
                                        <td>
                                            ${c.signed_scan_path ? `
                                                <span class="badge bg-success">TAK</span>
                                                <a class="ms-2" href="#" onclick="downloadContractSignedScan(${c.id}); return false;">pobierz</a>
                                            ` : `<span class="badge bg-light text-dark">NIE</span>`}
                                        </td>
                                        <td>
                                            <span class="badge bg-${getDepositStatusColor(c.deposit_status)}">${getDepositStatusLabel(c.deposit_status)}</span>
                                            ${(() => {
                                                const total = Number(c.job?.final_price || 0);
                                                const pct = Number(c.deposit_percent ?? 10);
                                                const target = (c.deposit_amount != null) ? Number(c.deposit_amount) : (total * (pct / 100));
                                                if (!target || Number.isNaN(target)) return '';
                                                return `<div class="text-muted small">${formatCurrency(target)}</div>`;
                                            })()}
                                        </td>
                                        <td>${formatDate(c.created_at)}</td>
                                        <td class="text-end">
                                            <div class="btn-group btn-group-sm">
                                                <a class="btn btn-outline-primary" href="#/contracts/${c.id}">
                                                    Otwórz
                                                </a>
                                                <a class="btn btn-outline-secondary" href="#/jobs/${c.job_id ?? c.job?.id ?? ''}" ${(!c.job_id && !c.job?.id) ? 'aria-disabled="true" tabindex="-1"' : ''}>
                                                    Zlecenie
                                                </a>
                                                ${c.pdf_path ? `
                                                    <button class="btn btn-outline-danger" type="button" onclick="downloadContractPdf(${c.id})">
                                                        PDF/Druk
                                                    </button>
                                                ` : `
                                                    <button class="btn btn-outline-danger" disabled>
                                                        PDF
                                                    </button>
                                                `}
                                            </div>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="text-muted">
                                Strona ${pagination.page} z ${pagination.pages} (${pagination.total} umów)
                            </div>
                            ${pagination.pages > 1 ? `
                                <nav>
                                    <ul class="pagination mb-0">
                                        <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                            <a class="page-link" href="#" onclick="goToContractsPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                        </li>
                                        ${Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                                            const pageNum = i + 1;
                                            return `
                                                <li class="page-item ${pageNum === pagination.page ? 'active' : ''}">
                                                    <a class="page-link" href="#" onclick="goToContractsPage(${pageNum}); return false;">${pageNum}</a>
                                                </li>
                                            `;
                                        }).join('')}
                                        <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                            <a class="page-link" href="#" onclick="goToContractsPage(${pagination.page + 1}); return false;">Następna</a>
                                        </li>
                                    </ul>
                                </nav>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `}
        `;

    } catch (error) {
        console.error('Failed to load contracts:', error);
        showToast('Błąd ładowania umów', 'danger');
    }
}

window.goToContractsPage = (page) => {
    currentContractsPage = page;
    renderContracts();
};

async function renderContractForJob(jobId) {
    const container = document.getElementById('viewContainer');
    
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        // Try to load existing contract; if not found (404), show creation form.
        let contract = null;
        try {
            const contractResponse = await contractsAPI.getByJobId(jobId, { showErrors: false });
            contract = contractResponse?.data || null;
        } catch (e) {
            contract = null;
        }

        if (contract && contract.id) {
            return renderContractDetails(contract.id);
        }

        // No contract exists - show creation form
        const jobResponse = await jobsAPI.getById(jobId);
        const job = jobResponse.data;

        const includedHours = job.offer?.hours_included ?? job.offer?.included_hours ?? 0;
        const includedPhotos = job.offer?.photos_count ?? job.offer?.included_photos ?? 0;
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-file-earmark-text"></i> Nowa umowa</h1>
                    <p class="text-muted mb-0">Zlecenie #${job.id} - ${job.customer?.display_name}</p>
                </div>
                <div>
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs/${jobId}'">
                        <i class="bi bi-arrow-left"></i> Powrót do zlecenia
                    </button>
                </div>
            </div>
            
            <div class="row">
                <div class="col-lg-8">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-info-circle"></i> Informacje o umowie</h5>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-primary">
                                <strong>Klient:</strong> ${job.customer?.display_name || job.customer?.full_name}<br>
                                <strong>Email:</strong> ${job.customer?.email}<br>
                                <strong>Wydarzenie:</strong> ${formatDate(job.event_date)}<br>
                                <strong>Lokalizacja:</strong> ${job.event_location}<br>
                                <strong>Wartość zlecenia:</strong> ${formatCurrency(job.final_price)}
                            </div>
                            
                            <form id="contractForm" novalidate>
                                <div class="mb-3">
                                    <label for="terms" class="form-label">Warunki umowy</label>
                                    <textarea class="form-control" id="terms" name="terms_content" rows="8" required>Warunki realizacji usługi fotograficznej:

1. Wykonawca zobowiązuje się wykonać usługę fotograficzną w dniu ${formatDate(job.event_date)} w lokalizacji ${job.event_location}.

2. Zakres usługi obejmuje pakiet "${job.offer?.name}" zawierający ${includedHours} godzin pracy i ${includedPhotos} zdjęć.

3. Cena usługi wynosi ${formatCurrency(job.final_price)} brutto.

4. Zapłata następuje zgodnie z wystawioną fakturą.

5. Terminy realizacji:
   - Galeria proofingowa: do 14 dni od wydarzenia
   - Ostateczne zdjęcia: do 30 dni od wydarzenia

6. Prawa autorskie pozostają przy Wykonawcy. Klient otrzymuje prawo do użytku prywatnego.</textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="notes" class="form-label">Dodatkowe notatki (opcjonalne)</label>
                                    <textarea class="form-control" id="notes" name="notes" rows="3"></textarea>
                                </div>
                                
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-file-earmark-plus"></i> Generuj umowę
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-4">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-list-check"></i> Checklist</h5>
                        </div>
                        <div class="card-body">
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" checked disabled>
                                <label class="form-check-label">Zlecenie utworzone</label>
                            </div>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" checked disabled>
                                <label class="form-check-label">Dane klienta kompletne</label>
                            </div>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="checkbox" id="checkTerms">
                                <label class="form-check-label" for="checkTerms">Warunki uzgodnione</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="checkPrice">
                                <label class="form-check-label" for="checkPrice">Cena potwierdzona</label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Setup form
        const form = document.getElementById('contractForm');
        wireClearOnInput(form);
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (!validateRequiredFields(form)) {
                return;
            }
            
            const formData = new FormData(form);
            const notesValue = (formData.get('notes') || '').trim();
            const data = {
                job_id: jobId,
                terms_content: formData.get('terms_content'),
                ...(notesValue ? { notes: notesValue } : {}),
            };
            
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generowanie...';
            
            try {
                const response = await contractsAPI.create(data);
                navigate(`/contracts/${response.data.id}`);
            } catch (error) {
                console.error('Failed to create contract:', error);

                // If contract already exists, redirect to it.
                const msg = (error && error.message) ? String(error.message) : '';
                if (msg.includes('już istnieje')) {
                    try {
                        const existing = await contractsAPI.getByJobId(jobId, { showErrors: false });
                        const existingId = existing?.data?.id;
                        if (existingId) {
                            showToast('Umowa już istnieje — otwieram ją', 'info');
                            navigate(`/contracts/${existingId}`);
                            return;
                        }
                    } catch (e2) {
                        // fall through to re-enable the button
                    }
                }

                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="bi bi-file-earmark-plus"></i> Generuj umowę';
            }
        });
        
    } catch (error) {
        console.error('Failed to load contract data:', error);
        showToast('Błąd ładowania danych', 'danger');
        navigate('/jobs');
    }
}

async function renderContractDetails(contractId) {
    const container = document.getElementById('viewContainer');
    
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await contractsAPI.getById(contractId);
        const contract = response.data;

        const orderTotal = contract.job?.final_price ?? 0;
        const depositPercent = contract.deposit_percent ?? 10;
        const depositTarget = contract.deposit_amount ?? (orderTotal * (Number(depositPercent) / 100));
        const depositPaid = contract.deposit_paid_amount ?? 0;
        const depositRemaining = Math.max(0, (Number(depositTarget) || 0) - (Number(depositPaid) || 0));
        const orderRemainingAfterDeposit = Math.max(0, (Number(orderTotal) || 0) - (Number(depositTarget) || 0));
        const depositStatusLabel = (s) => {
            if (s === 'paid') return 'Opłacona';
            if (s === 'waived') return 'Odstąpiono';
            return 'Nieopłacona';
        };
        const depositStatusColor = (s) => {
            if (s === 'paid') return 'success';
            if (s === 'waived') return 'secondary';
            return 'warning';
        };
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-file-earmark-text"></i> Umowa ${contract.contract_number}</h1>
                    <span class="badge bg-${getContractStatusColor(contract.status)} fs-6">${getContractStatusLabel(contract.status)}</span>
                </div>
                <div class="btn-group">
                    ${contract.pdf_path ? `
                        <button type="button" class="btn btn-outline-primary" onclick="downloadContractPdf(${contract.id})">
                            <i class="bi bi-file-pdf"></i> Pobierz PDF
                        </button>
                    ` : ''}
                    ${contract.status === 'draft' ? `
                        <button class="btn btn-success" onclick="sendContract(${contract.id})">
                            <i class="bi bi-send"></i> Wyślij klientowi
                        </button>
                    ` : ''}
                    ${contract.status !== 'signed' && contract.signed_scan_path ? `
                        <button class="btn btn-success" onclick="markContractSigned(${contract.id})">
                            <i class="bi bi-check2"></i> Oznacz jako podpisaną
                        </button>
                    ` : ''}
                    <button class="btn btn-outline-secondary" onclick="window.location.hash='#/jobs/${contract.job_id}'">
                        <i class="bi bi-arrow-left"></i> Zlecenie
                    </button>
                </div>
            </div>
            
            <div class="row">
                <div class="col-lg-8">
                    <!-- Contract Details -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-file-text"></i> Treść umowy</h5>
                        </div>
                        <div class="card-body">
                            <pre class="border p-3 bg-light" style="white-space: pre-wrap;">${contract.terms_content || ''}</pre>
                            
                            ${contract.notes ? `
                                <div class="mt-3">
                                    <strong>Notatki:</strong>
                                    <p class="mb-0">${contract.notes}</p>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    
                    <!-- Signature -->
                    ${contract.status === 'signed' && contract.has_signature ? `
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="bi bi-pen"></i> Podpis klienta</h5>
                            </div>
                            <div class="card-body">
                                <p class="text-muted mt-2 mb-0">
                                    <small>
                                        Podpisano: ${formatDate(contract.signed_at)}<br>
                                        IP: ${contract.signature_ip || ''}
                                    </small>
                                </p>
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                <div class="col-lg-4">
                    <!-- Info Card -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-info-circle"></i> Informacje</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Numer:</strong> ${contract.contract_number}</p>
                            <p><strong>Utworzono:</strong> ${formatDate(contract.created_at)}</p>
                            <p><strong>Status:</strong> <span class="badge bg-${getContractStatusColor(contract.status)}">${getContractStatusLabel(contract.status)}</span></p>
                            ${contract.sent_at ? `<p><strong>Wysłano:</strong> ${formatDate(contract.sent_at)}</p>` : ''}
                            ${contract.signed_at ? `<p><strong>Podpisano:</strong> ${formatDate(contract.signed_at)}</p>` : ''}
                        </div>
                    </div>

                    <!-- Deposit tracking -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-cash-coin"></i> Zaliczka</h5>
                        </div>
                        <div class="card-body">
                            <p class="mb-1"><strong>Status:</strong> <span class="badge bg-${depositStatusColor(contract.deposit_status)}">${depositStatusLabel(contract.deposit_status)}</span></p>
                            <p class="mb-1"><strong>Wartość zlecenia:</strong> ${formatCurrency(orderTotal)}</p>
                            <p class="mb-1"><strong>Zaliczka (${depositPercent}%):</strong> ${formatCurrency(depositTarget)}</p>
                            <p class="mb-1"><strong>Wpłacono:</strong> ${formatCurrency(depositPaid)}</p>
                            <p class="mb-1"><strong>Pozostało do wpłaty zaliczki:</strong> ${formatCurrency(depositRemaining)}</p>
                            <p class="mb-3"><strong>Pozostało do zapłaty po zaliczce:</strong> ${formatCurrency(orderRemainingAfterDeposit)}</p>
                            ${contract.deposit_paid_at ? `<p class="text-muted mb-3"><small>Opłacono: ${formatDate(contract.deposit_paid_at)}</small></p>` : ''}

                            <div class="text-muted small mb-3">Ten status dotyczy wyłącznie zaliczki, nie całej kwoty zlecenia.</div>

                            ${contract.deposit_status !== 'paid' ? `
                                <button type="button" class="btn btn-sm btn-success" id="markDepositPaidBtn">
                                    <i class="bi bi-check2"></i> Oznacz zaliczkę jako opłaconą (${formatCurrency(depositTarget)})
                                </button>
                            ` : ''}
                        </div>
                    </div>
                    
                    <!-- Job Info -->
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-briefcase"></i> Zlecenie</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Klient:</strong> ${contract.job?.customer?.display_name}</p>
                            <p><strong>Wydarzenie:</strong> ${formatDate(contract.job?.event_date)}</p>
                            <p><strong>Wartość:</strong> ${formatCurrency(contract.job?.final_price)}</p>
                            <a href="#/jobs/${contract.job_id}" class="btn btn-sm btn-outline-primary">
                                Zobacz zlecenie
                            </a>
                        </div>
                    </div>

                    <!-- Signed scan archive -->
                    <div class="card mt-4">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-paperclip"></i> Skan podpisanej umowy</h5>
                        </div>
                        <div class="card-body">
                            ${contract.signed_scan_path ? `
                                <div class="alert alert-success py-2">
                                    <small>
                                        Zapisano: ${formatDate(contract.signed_scan_uploaded_at)}<br>
                                        Plik: ${contract.signed_scan_original_filename || '—'}
                                    </small>
                                </div>
                                <button type="button" class="btn btn-sm btn-outline-primary" onclick="downloadContractSignedScan(${contract.id})">
                                    <i class="bi bi-download"></i> Pobierz skan
                                </button>
                            ` : `
                                <div class="alert alert-warning py-2">
                                    <small>Brak zarchiwizowanego skanu/zdjęcia.</small>
                                </div>
                            `}

                            <div class="mt-3">
                                <input type="file" class="form-control" id="signedScanFile" accept=".pdf,image/*">
                                <button class="btn btn-sm btn-success mt-2" id="uploadSignedScanBtn">
                                    <i class="bi bi-upload"></i> ${contract.signed_scan_path ? 'Zastąp skan' : 'Dodaj skan'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const uploadBtn = document.getElementById('uploadSignedScanBtn');
        const fileInput = document.getElementById('signedScanFile');
        if (uploadBtn && fileInput) {
            uploadBtn.addEventListener('click', async () => {
                const file = fileInput.files && fileInput.files[0];
                if (!file) {
                    showToast('Wybierz plik do wysłania', 'warning');
                    return;
                }

                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Wysyłanie...';

                try {
                    const fd = new FormData();
                    fd.append('file', file);
                    await contractsAPI.uploadSignedScan(contract.id, fd, { showErrors: true });
                    await renderContractDetails(contract.id);
                } catch (e) {
                    console.error('Failed to upload signed scan:', e);
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = `<i class="bi bi-upload"></i> ${contract.signed_scan_path ? 'Zastąp skan' : 'Dodaj skan'}`;
                }
            });
        }

        const markDepositPaidBtn = document.getElementById('markDepositPaidBtn');
        if (markDepositPaidBtn) {
            markDepositPaidBtn.addEventListener('click', async () => {
                const ok = await confirmDialog({
                    title: 'Potwierdź zaliczkę',
                    message: `Oznaczyć zaliczkę jako opłaconą (${formatCurrency(depositTarget)})?\n\nTo nie oznacza opłacenia całej kwoty zlecenia.`,
                    confirmText: 'Potwierdź',
                    cancelText: 'Anuluj',
                    danger: false,
                });
                if (!ok) return;

                markDepositPaidBtn.disabled = true;
                markDepositPaidBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Zapisywanie...';

                try {
                    // MySQL DATETIME is timezone-naive; send a simple "YYYY-MM-DD HH:MM:SS" string.
                    const nowIso = new Date().toISOString();
                    const nowMysql = nowIso.replace('T', ' ').replace('Z', '').split('.')[0];
                    await contractsAPI.update(contract.id, {
                        deposit_status: 'paid',
                        deposit_paid_amount: Number(depositTarget || 0),
                        deposit_paid_at: nowMysql,
                    }, { successMessage: 'Zaliczka oznaczona jako opłacona' });
                    await renderContractDetails(contract.id);
                } catch (e) {
                    console.error('Failed to mark deposit paid:', e);
                    markDepositPaidBtn.disabled = false;
                    markDepositPaidBtn.innerHTML = '<i class="bi bi-check2"></i> Oznacz jako opłaconą';
                }
            });
        }
        
    } catch (error) {
        console.error('Failed to load contract:', error);
        showToast('Nie znaleziono umowy', 'danger');
        navigate('/jobs');
    }
}

window.sendContract = async (contractId) => {
    const ok = await confirmDialog({
        title: 'Wyślij umowę',
        message: 'Czy na pewno chcesz wysłać umowę do klienta?',
        confirmText: 'Wyślij',
        cancelText: 'Anuluj',
        danger: false,
    });
    if (!ok) return;
    
    try {
        await contractsAPI.send(contractId);
        renderContractDetails(contractId);
    } catch (error) {
        console.error('Failed to send contract:', error);
    }
};

window.markContractSigned = async (contractId) => {
    const ok = await confirmDialog({
        title: 'Oznacz jako podpisaną',
        message: 'Oznaczyć umowę jako podpisaną na podstawie zarchiwizowanego skanu?',
        confirmText: 'Oznacz',
        cancelText: 'Anuluj',
        danger: false,
    });
    if (!ok) return;

    try {
        await contractsAPI.updateStatus(contractId, 'signed');
        await renderContractDetails(contractId);
    } catch (error) {
        console.error('Failed to mark contract as signed:', error);
    }
};

function getContractStatusColor(status) {
    const colors = {
        'draft': 'secondary',
        'sent': 'primary',
        'signed': 'success',
        'cancelled': 'danger',
    };
    return colors[status] || 'secondary';
}

function getContractStatusLabel(status) {
    const labels = {
        'draft': 'Szkic',
        'sent': 'Wysłano',
        'signed': 'Podpisano',
        'cancelled': 'Anulowano',
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

async function fetchBlobWithAuth(url) {
    const auth = getStoredAuth();
    const headers = {};
    if (auth && auth.access_token) {
        headers['Authorization'] = `Bearer ${auth.access_token}`;
    }

    const resp = await fetch(url, { headers });

    if ((resp.status === 401 || resp.status === 422)) {
        clearAuth();
        showToast('Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.', 'warning');
        scheduleLoginRedirect(2500);
        throw new Error('UNAUTHORIZED');
    }

    if (!resp.ok) {
        // Try to parse JSON error (if API returns it), otherwise fall back.
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

    // Try to open in a new tab (good for PDF print).
    const win = window.open(blobUrl, '_blank', 'noopener');
    if (!win) {
        // Popup blocked -> force download.
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = fallbackName || 'download';
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    // Revoke later to allow the tab to read it.
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}

window.downloadContractPdf = async (contractId) => {
    try {
        const blob = await fetchBlobWithAuth(`/api/contracts/${contractId}/pdf`);
        await openBlobInNewTab(blob, `umowa_${contractId}.pdf`);
    } catch (e) {
        if (e?.message !== 'UNAUTHORIZED') {
            showToast(e?.message || 'Nie udało się pobrać PDF', 'danger');
        }
    }
};

window.downloadContractSignedScan = async (contractId) => {
    try {
        const blob = await fetchBlobWithAuth(`/api/contracts/${contractId}/signed-scan`);
        await openBlobInNewTab(blob, `signed_scan_${contractId}`);
    } catch (e) {
        if (e?.message !== 'UNAUTHORIZED') {
            showToast(e?.message || 'Nie udało się pobrać skanu', 'danger');
        }
    }
};

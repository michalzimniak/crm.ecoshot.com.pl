/**
 * Vouchers View - Generowanie i lista voucherów
 */

import { promotionsAPI, vouchersAPI } from '../api.js';
import { showToast } from '../toasts.js';

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function formatDateTime(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return '-';
    return d.toLocaleString('pl-PL');
}

function statusBadge(v) {
    if (v?.is_used) return '<span class="badge bg-secondary">Wykorzystany</span>';
    if (v?.is_expired) return '<span class="badge bg-warning text-dark">Wygasł</span>';
    if (v?.is_valid) return '<span class="badge bg-success">Ważny</span>';
    return '<span class="badge bg-light text-dark">-</span>';
}

async function triggerDownload(downloadResult) {
    if (!downloadResult) return;

    const { blob, filename } = downloadResult;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'vouchery.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function renderVouchers() {
    const container = document.getElementById('viewContainer');
    let currentPage = 1;
    let currentFilters = {};

    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-qr-code"></i> Vouchery</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const promotionsRes = await promotionsAPI.getAll({}, { showErrors: true });
        const promotions = Array.isArray(promotionsRes?.data) ? promotionsRes.data.slice() : [];
        promotions.sort((a, b) => (a?.promo_type || '').localeCompare(b?.promo_type || '', 'pl'));
        const promoById = new Map(promotions.map((p) => [String(p.id), p]));

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-qr-code"></i> Vouchery</h1>
                    <p class="text-muted mb-0">Generowanie PDF z voucherami + lista i statusy.</p>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-header"><strong>Generowanie</strong></div>
                <div class="card-body">
                    <div class="row g-3 align-items-end">
                        <div class="col-md-6">
                            <label class="form-label">Promocja</label>
                            <select class="form-select" id="voucherPromotionId">
                                <option value="">-- wybierz promocję --</option>
                                ${promotions
                                    .map(
                                        (p) =>
                                            `<option value="${p.id}">${escapeHtml(p.promo_type)} — ${escapeHtml((p.value ?? '').toString())} PLN (${escapeHtml((p.duration_days ?? '').toString())} dni)</option>`
                                    )
                                    .join('')}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Ilość</label>
                            <input class="form-control" id="voucherCount" type="number" min="1" max="200" value="10" />
                            <div class="form-text">Max 200 na raz.</div>
                        </div>
                        <div class="col-md-3 d-grid">
                            <button class="btn btn-success" id="generateVouchersBtn">
                                <i class="bi bi-download"></i> Generuj PDF
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header d-flex align-items-center justify-content-between">
                    <strong>Lista voucherów</strong>
                    <button class="btn btn-outline-secondary btn-sm" id="refreshVouchersBtn">
                        <i class="bi bi-arrow-clockwise"></i> Odśwież
                    </button>
                </div>
                <div class="card-body">
                    <div class="row g-3 mb-3">
                        <div class="col-md-6">
                            <label class="form-label">Filtr: promocja</label>
                            <select class="form-select" id="filterPromotionId">
                                <option value="">(wszystkie)</option>
                                ${promotions
                                    .map(
                                        (p) =>
                                            `<option value="${p.id}">${escapeHtml(p.promo_type)} — ${escapeHtml((p.value ?? '').toString())} PLN</option>`
                                    )
                                    .join('')}
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Filtr: status</label>
                            <select class="form-select" id="filterStatus">
                                <option value="">(wszystkie)</option>
                                <option value="unused">Ważne (niewykorzystane)</option>
                                <option value="used">Wykorzystane</option>
                                <option value="expired">Wygasłe</option>
                            </select>
                        </div>
                    </div>

                    <div id="vouchersTableContainer" class="text-muted">Ładowanie…</div>
                </div>
            </div>
        `;

        async function loadVouchers() {
            const promoId = document.getElementById('filterPromotionId')?.value || '';
            const status = document.getElementById('filterStatus')?.value || '';

            currentFilters = {
                ...(promoId ? { promotion_id: promoId } : {}),
                ...(status ? { status } : {}),
            };

            const res = await vouchersAPI.getAll(currentFilters, currentPage, 50, { showErrors: true });
            const items = Array.isArray(res?.data) ? res.data : [];
            const pagination = res?.pagination || { page: currentPage, pages: 1, total: items.length || 0 };

            const el = document.getElementById('vouchersTableContainer');
            if (!el) return;

            if (items.length === 0) {
                el.innerHTML = '<div class="text-center text-muted py-5">Brak voucherów dla wybranych filtrów.</div>';
                return;
            }

            const pageLinksHtml = Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                const pageNum = i + 1;
                return `
                    <li class="page-item ${pageNum === pagination.page ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="goToPage(${pageNum}); return false;">${pageNum}</a>
                    </li>
                `;
            }).join('');

            const paginationNavHtml =
                pagination.pages > 1
                    ? `
                        <nav>
                            <ul class="pagination mb-0">
                                <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                    <a class="page-link" href="#" onclick="goToPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                </li>
                                ${pageLinksHtml}
                                <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                    <a class="page-link" href="#" onclick="goToPage(${pagination.page + 1}); return false;">Następna</a>
                                </li>
                            </ul>
                        </nav>
                    `
                    : '';

            const paginationHtml = `
                <div class="d-flex justify-content-between align-items-center mt-3">
                    <div class="text-muted">
                        Strona ${pagination.page} z ${pagination.pages} (${pagination.total} voucherów)
                    </div>
                    ${paginationNavHtml}
                </div>
            `;

            el.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-hover align-middle">
                        <thead>
                            <tr>
                                <th>Kod</th>
                                <th>Promocja</th>
                                <th>Wydany</th>
                                <th>Ważny do</th>
                                <th>Użyty</th>
                                <th>Status</th>
                                <th class="text-end">Pliki</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${items
                                .map((v) => {
                                    const promo = promoById.get(String(v.promotion_id));
                                    const canDownload = Boolean(v?.is_valid);
                                    const disabledAttrs = canDownload ? '' : 'disabled aria-disabled="true"';
                                    const title = canDownload
                                        ? 'Pobierz pliki dla tego vouchera'
                                        : 'Dostępne tylko dla ważnych (niewykorzystanych) voucherów';

                                    return `
                                        <tr>
                                            <td style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;">
                                                ${escapeHtml(v.code || '')}
                                            </td>
                                            <td>${escapeHtml(promo?.promo_type || v.promotion_id)}</td>
                                            <td>${escapeHtml(formatDateTime(v.issued_at))}</td>
                                            <td>${escapeHtml(formatDateTime(v.expires_at))}</td>
                                            <td>${escapeHtml(formatDateTime(v.used_at))}</td>
                                            <td>${statusBadge(v)}</td>
                                            <td class="text-end">
                                                <div class="btn-group btn-group-sm">
                                                    <button class="btn btn-outline-success" data-action="voucher-pdf" data-id="${v.id}" title="${escapeHtml(title)}" ${disabledAttrs}>
                                                        PDF
                                                    </button>
                                                    <button class="btn btn-outline-secondary" data-action="voucher-png" data-id="${v.id}" title="${escapeHtml(title)}" ${disabledAttrs}>
                                                        PNG
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    `;
                                })
                                .join('')}
                        </tbody>
                    </table>
                </div>
                ${paginationHtml}
            `;

            el.querySelectorAll('button[data-action="voucher-pdf"]').forEach((btn) => {
                btn.addEventListener('click', async () => {
                    const id = btn.getAttribute('data-id');
                    if (!id || btn.hasAttribute('disabled')) return;
                    try {
                        const downloadResult = await vouchersAPI.downloadSinglePdf(id, { showErrors: true });
                        await triggerDownload(downloadResult);
                    } catch (e) {
                        console.error(e);
                    }
                });
            });

            el.querySelectorAll('button[data-action="voucher-png"]').forEach((btn) => {
                btn.addEventListener('click', async () => {
                    const id = btn.getAttribute('data-id');
                    if (!id || btn.hasAttribute('disabled')) return;
                    try {
                        const downloadResult = await vouchersAPI.downloadSinglePng(id, { showErrors: true });
                        await triggerDownload(downloadResult);
                    } catch (e) {
                        console.error(e);
                    }
                });
            });
        }

        // Global for inline pagination handlers (SPA pattern)
        window.goToPage = (page) => {
            currentPage = page;
            loadVouchers();
        };

        document.getElementById('refreshVouchersBtn')?.addEventListener('click', async () => {
            try {
                await loadVouchers();
            } catch (e) {
                console.error(e);
            }
        });

        document.getElementById('filterPromotionId')?.addEventListener('change', () => {
            currentPage = 1;
            loadVouchers();
        });
        document.getElementById('filterStatus')?.addEventListener('change', () => {
            currentPage = 1;
            loadVouchers();
        });

        document.getElementById('generateVouchersBtn')?.addEventListener('click', async () => {
            const promotionIdEl = document.getElementById('voucherPromotionId');
            const countEl = document.getElementById('voucherCount');

            const promotion_id = parseInt(promotionIdEl?.value || '0', 10);
            const count = parseInt(countEl?.value || '0', 10);

            if (!promotion_id) {
                showToast('Wybierz promocję', 'warning');
                return;
            }
            if (!Number.isFinite(count) || count <= 0 || count > 200) {
                showToast('Podaj poprawną ilość (1-200)', 'warning');
                return;
            }

            const btn = document.getElementById('generateVouchersBtn');
            if (btn) btn.disabled = true;

            try {
                const downloadResult = await vouchersAPI.generatePdf(promotion_id, count, { showErrors: true });
                await triggerDownload(downloadResult);
                currentPage = 1;
                await loadVouchers();
            } catch (e) {
                console.error(e);
            } finally {
                if (btn) btn.disabled = false;
            }
        });

        currentPage = 1;
        await loadVouchers();
    } catch (error) {
        console.error(error);
        showToast('Błąd ładowania voucherów', 'danger');
    }
}

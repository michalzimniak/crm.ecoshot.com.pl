/**
 * Settings View - Ustawienia systemu
 */

import { settingsAPI, jobsAPI, promotionsAPI } from '../api.js';
import { showToast } from '../toasts.js';
import { confirmDialog } from '../confirm.js';
import { validateRequiredFields, requireEmail, requireValue, wireClearOnInput } from '../forms.js';
import { applyBranding } from '../branding.js';

let cachedOffers = [];
let cachedPromotions = [];

const SETTINGS_ACTIVE_TAB_KEY = 'ecoshot_settings_active_tab';

const DB_RESTORE_CONFIRM_PHRASE = 'PRZYWRÓĆ';
const PURGE_CONFIRM_PHRASE = 'USUŃ DANE';

const PL_BANK_CODE_TO_NAME = {
    // Key = 4-digit bank code (first 4 digits of the 8-digit clearing number).
    '1020': 'PKO Bank Polski',
    '1030': 'Bank Handlowy (Citi Handlowy)',
    '1050': 'ING Bank Śląski',
    '1090': 'Santander Bank Polska',
    '1130': 'Bank Gospodarstwa Krajowego',
    '1140': 'mBank',
    '1160': 'Bank Millennium',
    '1240': 'Bank Pekao',
    '1280': 'HSBC',
    '1320': 'Bank Pocztowy',
    '1540': 'BOŚ Bank',
    '1580': 'Mercedes-Benz Bank Polska',
    '1610': 'SGB-Bank',
    '1670': 'RBS Bank (Polska)',
    '1680': 'Plus Bank',
    '1840': 'Societe Generale',
    '1870': 'Nest Bank',
    '1930': 'Bank Polskiej Spółdzielczości',
    '1940': 'Credit Agricole Bank Polska',
    '2030': 'BNP Paribas Bank Polska',
    '2120': 'Santander Consumer Bank',
    '2160': 'Toyota Bank',
    '2190': 'DNB Bank Polska',
    '2480': 'Getin Noble Bank',
    '2490': 'Alior Bank',
};

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function renderBoolBadge(ok) {
    return ok
        ? '<span class="badge bg-success">OK</span>'
        : '<span class="badge bg-secondary">Brak</span>';
}

function renderValue(value) {
    const v = value === null || value === undefined || value === '' ? '-' : String(value);
    return `<span class="text-body">${escapeHtml(v)}</span>`;
}

function sortByOrderThenName(a, b) {
    const aOrder = Number.isFinite(Number(a?.display_order)) ? Number(a.display_order) : 0;
    const bOrder = Number.isFinite(Number(b?.display_order)) ? Number(b.display_order) : 0;
    if (aOrder !== bOrder) return aOrder - bOrder;
    const aName = (a?.name || '').toString();
    const bName = (b?.name || '').toString();
    return aName.localeCompare(bName, 'pl');
}

function guessBankNameFromAccountNumber(accountNumberRaw) {
    if (!accountNumberRaw) return null;

    // Accept: NRB (26 digits), or IBAN "PL" + 26 digits, with optional spaces.
    const upper = String(accountNumberRaw).trim().toUpperCase();
    const withoutPrefix = upper.startsWith('PL') ? upper.slice(2) : upper;
    const digits = withoutPrefix.replaceAll(/\D/g, '');
    if (digits.length !== 26) return null;

    // Polish NRB: KK BBBB BBBB CCCC CCCC CCCC CCCC
    // We use first 4 digits of BBBB BBBB as the bank code.
    const bankCode = digits.slice(2, 6);
    return PL_BANK_CODE_TO_NAME[bankCode] || null;
}

export async function renderSettings() {
    const container = document.getElementById('viewContainer');

    const desiredTabId = localStorage.getItem(SETTINGS_ACTIVE_TAB_KEY) || 'settingsMainTab';

    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-gear"></i> Ustawienia</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const [settingsRes, offersRes, promotionsRes] = await Promise.all([
            settingsAPI.get({ showErrors: true }),
            jobsAPI.getOffers({ active_only: false }),
            promotionsAPI.getAll({}, { showErrors: true }),
        ]);

        const data = settingsRes?.data || {};
        const company = data.company || {};
        const invoice = data.invoice || {};
        const branding = data.branding || {};
        const watermark = data.watermark || {};
        const uploads = data.uploads || {};
        const integrations = data.integrations || {};
        const google = integrations.google_maps || {};
        const payu = integrations.payu || {};
        const canva = integrations.canva || {};

        cachedOffers = Array.isArray(offersRes?.data) ? offersRes.data.slice() : [];
        cachedOffers.sort(sortByOrderThenName);

        cachedPromotions = Array.isArray(promotionsRes?.data) ? promotionsRes.data.slice() : [];
        cachedPromotions.sort((a, b) => {
            const aType = (a?.promo_type || '').toString();
            const bType = (b?.promo_type || '').toString();
            const t = aType.localeCompare(bType, 'pl');
            if (t !== 0) return t;
            const aCreated = a?.created_at ? new Date(a.created_at).getTime() : 0;
            const bCreated = b?.created_at ? new Date(b.created_at).getTime() : 0;
            return bCreated - aCreated;
        });

        const allAddons = cachedOffers
            .flatMap((o) => (o.addons || []).map((a) => ({
                ...a,
                offer: { id: o.id, name: o.name },
            })))
            .sort(sortByOrderThenName);

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-gear"></i> Ustawienia</h1>
                    <p class="text-muted mb-0">Dane firmy i faktur zapisywane są w bazie (nadpisują config).</p>
                </div>
            </div>

            <ul class="nav nav-tabs" id="settingsTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="settingsMainTab" data-bs-toggle="tab" data-bs-target="#settingsMainPane" type="button" role="tab" aria-controls="settingsMainPane" aria-selected="true">Główne</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="settingsOffersTab" data-bs-toggle="tab" data-bs-target="#settingsOffersPane" type="button" role="tab" aria-controls="settingsOffersPane" aria-selected="false">Oferty i dodatki</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="settingsPromotionsTab" data-bs-toggle="tab" data-bs-target="#settingsPromotionsPane" type="button" role="tab" aria-controls="settingsPromotionsPane" aria-selected="false">Promocje</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="settingsMaintenanceTab" data-bs-toggle="tab" data-bs-target="#settingsMaintenancePane" type="button" role="tab" aria-controls="settingsMaintenancePane" aria-selected="false">Backup i dane</button>
                </li>
            </ul>

            <div class="tab-content pt-4">
                <div class="tab-pane fade show active" id="settingsMainPane" role="tabpanel" aria-labelledby="settingsMainTab" tabindex="0">
                    <div class="row g-4">
                        <div class="col-lg-6">
                            <div class="card">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <strong>Dane firmy</strong>
                                </div>
                                <div class="card-body">
                                    <form id="settingsForm" class="needs-validation" novalidate>
                                        <div class="mb-3">
                                            <label class="form-label">Nazwa</label>
                                            <input id="settingsCompanyName" class="form-control" required value="${escapeHtml(company.name || '')}" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">Adres</label>
                                            <input id="settingsCompanyAddress" class="form-control" required value="${escapeHtml(company.address || '')}" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">NIP</label>
                                            <input id="settingsCompanyNip" class="form-control" required value="${escapeHtml(company.nip || '')}" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">Telefon</label>
                                            <input id="settingsCompanyPhone" class="form-control" value="${escapeHtml(company.phone || '')}" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">Email</label>
                                            <input id="settingsCompanyEmail" type="email" class="form-control" required value="${escapeHtml(company.email || '')}" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">Bank</label>
                                            <input id="settingsCompanyBank" class="form-control" value="${escapeHtml(company.bank || '')}" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">Konto</label>
                                            <input id="settingsCompanyAccount" class="form-control" value="${escapeHtml(company.account || '')}" />
                                        </div>

                                        <hr class="my-4" />

                                        <div class="d-flex gap-2">
                                            <button type="submit" class="btn btn-success" id="settingsSaveBtn">
                                                <i class="bi bi-save"></i> Zapisz
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-6">
                            <div class="card">
                                <div class="card-header"><strong>Faktury</strong></div>
                                <div class="card-body">
                                    <div class="mb-3">
                                        <label class="form-label">Prefix</label>
                                        <input id="settingsInvoicePrefix" class="form-control" form="settingsForm" required value="${escapeHtml(invoice.prefix || '')}" />
                                        <div class="form-text">Wpływa na numer faktury (np. FV/2026/001).</div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Prefix Faktur Zaliczkowych</label>
                                        <input id="settingsInvoiceDepositPrefix" class="form-control" form="settingsForm" required value="${escapeHtml(invoice.deposit_prefix || '')}" />
                                        <div class="form-text">Prefix dla faktur zaliczkowych (np. FZV/2026/001).</div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Prefix Faktur Korygujących</label>
                                        <input id="settingsInvoiceCorrectionPrefix" class="form-control" form="settingsForm" required value="${escapeHtml(invoice.correction_prefix || '')}" />
                                        <div class="form-text">Prefix dla faktur korygujących (np. FKV/2026/001).</div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Format roku</label>
                                        <input id="settingsInvoiceYearFormat" class="form-control" form="settingsForm" required value="${escapeHtml(invoice.year_format || '')}" />
                                        <div class="form-text">Format dla strftime, np. %Y.</div>
                                    </div>

                                    <hr class="my-4" />

                                    <div class="mb-3">
                                        <label class="form-label">VAT</label>
                                        <div class="row g-2 align-items-center">
                                            <div class="col-md-6">
                                                <select id="settingsInvoiceVatRate" class="form-select" form="settingsForm" required>
                                                    ${['23', '8', '5', '0'].map((rate) => `
                                                        <option value="${rate}" ${String(invoice.vat_rate || '23').startsWith(rate) ? 'selected' : ''}>${rate}%</option>
                                                    `).join('')}
                                                </select>
                                                <div class="form-text">Dostępne stawki w PL: 23%, 8%, 5%, 0%.</div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="form-check mt-1">
                                                    <input class="form-check-input" type="checkbox" id="settingsInvoiceVatExempt" form="settingsForm" ${invoice.vat_exempt ? 'checked' : ''}>
                                                    <label class="form-check-label" for="settingsInvoiceVatExempt">Zwolniony (ZW na fakturze) = 0%</label>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-4">
                                <div class="card-header"><strong>Branding</strong></div>
                                <div class="card-body">
                                    <div class="mb-3">
                                        <label class="form-label">Nazwa CRM (title i nagłówek)</label>
                                        <input id="settingsCrmName" class="form-control" form="settingsForm" value="${escapeHtml(branding.name || '')}" />
                                        <div class="form-text">Jeśli puste, użyje domyślnej nazwy.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label">Tekst watermarka</label>
                                        <input id="settingsWatermarkText" class="form-control" form="settingsForm" value="${escapeHtml(watermark.text || '')}" />
                                        <div class="form-text">Tekst jest powtarzany na zdjęciach w galeriach proof/selection (gdy watermark jest włączony).</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label">Logo</label>
                                        <div class="d-flex align-items-center gap-2 mb-2">
                                            ${renderBoolBadge(Boolean(branding.has_logo))}
                                            <small class="text-muted">Dozwolone: PNG/JPG/JPEG/GIF</small>
                                        </div>

                                        <div class="mb-2">
                                            <img
                                                id="settingsLogoPreview"
                                                class="border rounded ${branding.has_logo ? '' : 'd-none'}"
                                                alt="Logo"
                                                src="${branding.logo_url ? escapeHtml(branding.logo_url) : ''}"
                                                style="max-height: 64px; width: auto; background: #fff;" />
                                        </div>

                                        <div class="d-flex flex-wrap gap-2">
                                            <input type="file" class="form-control" id="settingsLogoFile" accept="image/png,image/jpeg,image/gif" style="max-width: 340px;" />
                                            <button type="button" class="btn btn-outline-success" id="settingsUploadLogoBtn">
                                                <i class="bi bi-upload"></i> Wgraj logo
                                            </button>
                                            <button type="button" class="btn btn-outline-danger" id="settingsDeleteLogoBtn" ${branding.has_logo ? '' : 'disabled'}>
                                                <i class="bi bi-trash"></i> Usuń logo
                                            </button>
                                        </div>
                                    </div>

                                    <div class="mb-0">
                                        <label class="form-label">Logo galerii (widok dla klienta)</label>
                                        <div class="d-flex align-items-center gap-2 mb-2">
                                            ${renderBoolBadge(Boolean(branding.has_gallery_logo))}
                                            <small class="text-muted">Dozwolone: PNG/JPG/JPEG/GIF</small>
                                        </div>

                                        <div class="mb-2">
                                            <img
                                                id="settingsGalleryLogoPreview"
                                                class="border rounded ${branding.has_gallery_logo ? '' : 'd-none'}"
                                                alt="Logo galerii"
                                                src="${branding.gallery_logo_url ? escapeHtml(branding.gallery_logo_url) : ''}"
                                                style="max-height: 64px; width: auto; background: #fff;" />
                                        </div>

                                        <div class="d-flex flex-wrap gap-2">
                                            <input type="file" class="form-control" id="settingsGalleryLogoFile" accept="image/png,image/jpeg,image/gif" style="max-width: 340px;" />
                                            <button type="button" class="btn btn-outline-success" id="settingsUploadGalleryLogoBtn">
                                                <i class="bi bi-upload"></i> Wgraj logo galerii
                                            </button>
                                            <button type="button" class="btn btn-outline-danger" id="settingsDeleteGalleryLogoBtn" ${branding.has_gallery_logo ? '' : 'disabled'}>
                                                <i class="bi bi-trash"></i> Usuń logo galerii
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-4">
                                <div class="card-header"><strong>Uploady</strong></div>
                                <div class="card-body">
                                    <div class="row mb-2"><div class="col-4 text-muted">Folder</div><div class="col-8">${renderValue(uploads.upload_folder)}</div></div>
                                    <div class="row mb-2"><div class="col-4 text-muted">Limit</div><div class="col-8">${renderValue(uploads.max_content_length)}</div></div>
                                    <div class="row"><div class="col-4 text-muted">Dozwolone</div><div class="col-8">${escapeHtml((uploads.allowed_extensions || []).join(', ') || '-')}</div></div>
                                </div>
                            </div>
                        </div>

                        <div class="col-12">
                            <div class="card">
                                <div class="card-header"><strong>Integracje</strong></div>
                                <div class="card-body">
                                    <div class="row g-4">
                                        <div class="col-lg-6">
                                            <h6 class="mb-3">Google Maps</h6>
                                            <div class="row mb-2"><div class="col-6 text-muted">API key</div><div class="col-6">${renderBoolBadge(Boolean(google.api_key_set))}</div></div>
                                            <div class="row"><div class="col-6 text-muted">Browser API key</div><div class="col-6">${renderBoolBadge(Boolean(google.browser_api_key_set))}</div></div>
                                        </div>
                                        <div class="col-lg-6">
                                            <h6 class="mb-3">PayU</h6>
                                            <div class="row mb-2"><div class="col-6 text-muted">Środowisko</div><div class="col-6">${renderValue(payu.env)}</div></div>
                                            <div class="row mb-2"><div class="col-6 text-muted">POS ID</div><div class="col-6">${renderBoolBadge(Boolean(payu.pos_id_set))}</div></div>
                                            <div class="row mb-2"><div class="col-6 text-muted">Client ID</div><div class="col-6">${renderBoolBadge(Boolean(payu.client_id_set))}</div></div>
                                            <div class="row mb-2"><div class="col-6 text-muted">Client Secret</div><div class="col-6">${renderBoolBadge(Boolean(payu.client_secret_set))}</div></div>
                                            <div class="row mb-2"><div class="col-6 text-muted">Second Key</div><div class="col-6">${renderBoolBadge(Boolean(payu.second_key_set))}</div></div>
                                            <div class="row"><div class="col-6 text-muted">Notify URL</div><div class="col-6">${renderValue(payu.notify_url)}</div></div>
                                        </div>
                                        <div class="col-12">
                                            <hr class="my-1" />
                                        </div>
                                        <div class="col-lg-6">
                                            <h6 class="mb-3">Canva</h6>
                                            <div class="row mb-2"><div class="col-6 text-muted">Access token</div><div class="col-6">${renderBoolBadge(Boolean(canva.access_token_set))}</div></div>
                                            <div class="row mb-2"><div class="col-6 text-muted">Client ID</div><div class="col-6">${renderBoolBadge(Boolean(canva.client_id_set))}</div></div>
                                            <div class="row mb-3"><div class="col-6 text-muted">Client Secret</div><div class="col-6">${renderBoolBadge(Boolean(canva.client_secret_set))}</div></div>

                                            <div class="mb-2">
                                                <label class="form-label">Ustaw / zmień Access token</label>
                                                <input id="settingsCanvaAccessToken" class="form-control" form="settingsForm" type="password" placeholder="Wklej token (pozostaw puste aby nie zmieniać)" />
                                            </div>
                                            <div class="mb-2">
                                                <label class="form-label">Ustaw / zmień Client ID</label>
                                                <input id="settingsCanvaClientId" class="form-control" form="settingsForm" type="password" placeholder="Client ID (pozostaw puste aby nie zmieniać)" />
                                            </div>
                                            <div class="mb-0">
                                                <label class="form-label">Ustaw / zmień Client Secret</label>
                                                <input id="settingsCanvaClientSecret" class="form-control" form="settingsForm" type="password" placeholder="Client Secret (pozostaw puste aby nie zmieniać)" />
                                                <div class="form-text">Pola są opcjonalne — jeśli puste, nie nadpisują istniejących wartości.</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="tab-pane fade" id="settingsOffersPane" role="tabpanel" aria-labelledby="settingsOffersTab" tabindex="0">
                    <div class="row g-4">
                        <div class="col-12">
                            <div class="card">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <strong>Pakiety (oferty)</strong>
                                    <button class="btn btn-sm btn-success" id="openCreateOfferBtn">
                                        <i class="bi bi-plus-lg"></i> Dodaj pakiet
                                    </button>
                                </div>
                                <div class="card-body">
                                    ${cachedOffers.length === 0 ? `
                                        <div class="text-muted">Brak ofert.</div>
                                    ` : `
                                        <div class="table-responsive">
                                            <table class="table table-hover align-middle">
                                                <thead>
                                                    <tr>
                                                        <th>Nazwa</th>
                                                        <th>Cena</th>
                                                        <th>Godz.</th>
                                                        <th>Zdjęcia</th>
                                                        <th>Wideo</th>
                                                        <th>Status</th>
                                                        <th class="text-end">Akcje</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    ${cachedOffers.map((o) => {
                                                        const status = o.is_active
                                                            ? '<span class="badge bg-success">Aktywna</span>'
                                                            : '<span class="badge bg-secondary">Nieaktywna</span>';
                                                        return `
                                                            <tr>
                                                                <td>
                                                                    <strong>${escapeHtml(o.name || '-')}</strong>
                                                                    <div class="text-muted small">${escapeHtml(o.description || '')}</div>
                                                                </td>
                                                                <td>${escapeHtml((o.base_price ?? '').toString())}</td>
                                                                <td>${escapeHtml((o.hours_included ?? '-').toString())}</td>
                                                                <td>${escapeHtml((o.photos_count ?? '-').toString())}</td>
                                                                <td>${o.video_included ? 'Tak' : 'Nie'}</td>
                                                                <td>${status}</td>
                                                                <td class="text-end">
                                                                    <div class="btn-group btn-group-sm">
                                                                        <button class="btn btn-outline-primary" onclick="window.editOffer(${o.id})" title="Edytuj">
                                                                            <i class="bi bi-pencil"></i>
                                                                        </button>
                                                                        <button class="btn btn-outline-danger" onclick="window.deleteOffer(${o.id})" title="Usuń">
                                                                            <i class="bi bi-trash"></i>
                                                                        </button>
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        `;
                                                    }).join('')}
                                                </tbody>
                                            </table>
                                        </div>
                                    `}
                                </div>
                            </div>
                        </div>

                        <div class="col-12">
                            <div class="card">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <strong>Dodatki (offer_addons)</strong>
                                    <button class="btn btn-sm btn-success" id="openCreateAddonBtn">
                                        <i class="bi bi-plus-lg"></i> Dodaj dodatek
                                    </button>
                                </div>
                                <div class="card-body">
                                    ${allAddons.length === 0 ? `
                                        <div class="text-muted">Brak dodatków.</div>
                                    ` : `
                                        <div class="table-responsive">
                                            <table class="table table-hover align-middle">
                                                <thead>
                                                    <tr>
                                                        <th>Nazwa</th>
                                                        <th>Pakiet</th>
                                                        <th>Cena</th>
                                                        <th>Model</th>
                                                        <th>Kategoria</th>
                                                        <th>Miesiące</th>
                                                        <th>Status</th>
                                                        <th class="text-end">Akcje</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    ${allAddons.map((a) => {
                                                        const status = a.is_available
                                                            ? '<span class="badge bg-success">Dostępny</span>'
                                                            : '<span class="badge bg-secondary">Niedostępny</span>';
                                                        return `
                                                            <tr>
                                                                <td>
                                                                    <strong>${escapeHtml(a.name || '-')}</strong>
                                                                    <div class="text-muted small">${escapeHtml(a.description || '')}</div>
                                                                </td>
                                                                <td>${escapeHtml(a.offer?.name || '-')}</td>
                                                                <td>${escapeHtml((a.price ?? '').toString())}</td>
                                                                <td>${escapeHtml(a.pricing_model || 'fixed')}</td>
                                                                <td>${escapeHtml(a.category || '-')}</td>
                                                                <td>${escapeHtml((a.duration_months ?? '-').toString())}</td>
                                                                <td>${status}</td>
                                                                <td class="text-end">
                                                                    <div class="btn-group btn-group-sm">
                                                                        <button class="btn btn-outline-primary" onclick="window.editOfferAddon(${a.id})" title="Edytuj">
                                                                            <i class="bi bi-pencil"></i>
                                                                        </button>
                                                                        <button class="btn btn-outline-danger" onclick="window.deleteOfferAddon(${a.id})" title="Usuń">
                                                                            <i class="bi bi-trash"></i>
                                                                        </button>
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        `;
                                                    }).join('')}
                                                </tbody>
                                            </table>
                                        </div>
                                    `}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="tab-pane fade" id="settingsPromotionsPane" role="tabpanel" aria-labelledby="settingsPromotionsTab" tabindex="0">
                    <div class="page-header">
                        <div>
                            <h4 class="mb-0"><i class="bi bi-ticket-perforated"></i> Promocje</h4>
                            <p class="text-muted mb-0">Zarządzanie bonami/voucherami. Edycja i usuwanie są dostępne tylko, gdy nie ma aktywnej promocji danego typu.</p>
                        </div>
                        <div>
                            <button class="btn btn-success" id="openCreatePromotionBtn">
                                <i class="bi bi-plus-circle"></i> Nowa promocja
                            </button>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-hover mb-0">
                                    <thead>
                                        <tr>
                                            <th>Typ</th>
                                            <th>Wartość</th>
                                            <th>Czas trwania (dni)</th>
                                            <th>Aktywna do</th>
                                            <th>Status</th>
                                            <th class="text-end">Akcje</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${renderPromotionsRows(cachedPromotions)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="tab-pane fade" id="settingsMaintenancePane" role="tabpanel" aria-labelledby="settingsMaintenanceTab" tabindex="0">
                    <div class="page-header">
                        <div>
                            <h4 class="mb-0"><i class="bi bi-database"></i> Backup i dane</h4>
                            <p class="text-muted mb-0">Operacje administracyjne: backup/restore bazy oraz usuwanie danych wraz z plikami.</p>
                        </div>
                    </div>

                    <div class="row g-4">
                        <div class="col-lg-6">
                            <div class="card">
                                <div class="card-header"><strong>Backup</strong></div>
                                <div class="card-body">
                                    <div class="d-flex flex-wrap gap-2">
                                        <button class="btn btn-outline-success" id="settingsDbBackupBtn" type="button">
                                            <i class="bi bi-download"></i> Backup bazy (SQL)
                                        </button>
                                        <button class="btn btn-success" id="settingsFullBackupBtn" type="button">
                                            <i class="bi bi-hdd"></i> Utwórz pełny backup (DB + pliki)
                                        </button>
                                    </div>
                                    <div class="form-text mt-2">Pełny backup zapisuje się na serwerze (retencja: zawsze 3 najnowsze). Pliki są brane z katalogu uploads.</div>

                                    <hr class="my-3" />

                                    <div class="d-flex align-items-center justify-content-between gap-2">
                                        <strong>Zapisane backupy (DB + pliki)</strong>
                                        <button class="btn btn-outline-secondary btn-sm" id="settingsFullBackupsRefreshBtn" type="button">
                                            <i class="bi bi-arrow-clockwise"></i> Odśwież
                                        </button>
                                    </div>
                                    <div id="settingsFullBackupsList" class="mt-2"></div>

                                    <div class="mt-3">
                                        <label class="form-label">Potwierdzenie (restore pełnego backupu)</label>
                                        <input class="form-control" id="settingsFullRestoreConfirm" placeholder="Wpisz: ${DB_RESTORE_CONFIRM_PHRASE}" />
                                        <div class="form-text">Restore pełnego backupu nadpisuje bazę i pliki w uploads.</div>
                                    </div>
                                </div>
                            </div>

                            <div class="card mt-4">
                                <div class="card-header"><strong>Przywracanie backupu bazy</strong></div>
                                <div class="card-body">
                                    <div class="alert alert-warning mb-3">
                                        <strong>Uwaga:</strong> przywracanie może nadpisać dane w bazie.
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label">Plik SQL</label>
                                        <input class="form-control" type="file" id="settingsDbRestoreFile" accept=".sql" />
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label">Potwierdzenie</label>
                                        <input class="form-control" id="settingsDbRestoreConfirm" placeholder="Wpisz: ${DB_RESTORE_CONFIRM_PHRASE}" />
                                        <div class="form-text">Wymagane, aby uniknąć przypadkowego restore.</div>
                                    </div>

                                    <button class="btn btn-warning" id="settingsDbRestoreBtn" type="button">
                                        <i class="bi bi-arrow-counterclockwise"></i> Przywróć backup
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div class="col-lg-6">
                            <div class="card border-danger">
                                <div class="card-header text-danger"><strong>Strefa niebezpieczna</strong></div>
                                <div class="card-body">
                                    <div class="alert alert-danger mb-3">
                                        <strong>Uwaga:</strong> ta operacja usuwa dane nieodwracalnie.
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label">Co usunąć z bazy?</label>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgeJobs" checked>
                                            <label class="form-check-label" for="purgeJobs">Zlecenia (oraz powiązane: faktury, płatności, umowy, zgody, galerie, zdjęcia)</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgeVouchers">
                                            <label class="form-check-label" for="purgeVouchers">Vouchery (kody + powiązania ze zleceniami)</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgePromotions">
                                            <label class="form-check-label" for="purgePromotions">Promocje (definicje + tła vouchera). Uwaga: usuwa też vouchery.</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgeInvoices">
                                            <label class="form-check-label" for="purgeInvoices">Faktury</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgeContracts">
                                            <label class="form-check-label" for="purgeContracts">Umowy</label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgeConsents">
                                            <label class="form-check-label" for="purgeConsents">Zgody</label>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="purgeDeleteFiles" checked>
                                            <label class="form-check-label" for="purgeDeleteFiles">Usuń też pliki z uploads (np. zdjęcia/PDFy)</label>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label">Potwierdzenie</label>
                                        <input class="form-control" id="purgeConfirm" placeholder="Wpisz: ${PURGE_CONFIRM_PHRASE}" />
                                    </div>

                                    <button class="btn btn-danger" id="purgeRunBtn" type="button">
                                        <i class="bi bi-trash"></i> Usuń wybrane dane
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            ${renderOfferModal()}
            ${renderOfferAddonModal(cachedOffers)}
            ${renderPromotionModal()}
        `;

        // Persist/restore active tab so actions don't jump back to "Główne".
        container.querySelectorAll('#settingsTabs button[data-bs-toggle="tab"]').forEach((btn) => {
            btn.addEventListener('shown.bs.tab', (e) => {
                if (e?.target?.id) localStorage.setItem(SETTINGS_ACTIVE_TAB_KEY, e.target.id);
            });
        });

        const restoreBtn = container.querySelector(`#${CSS.escape(desiredTabId)}`);
        if (restoreBtn) {
            try {
                new bootstrap.Tab(restoreBtn).show();
            } catch (_) {
                // ignore
            }
        }

        const formEl = container.querySelector('#settingsForm');
        const saveBtn = container.querySelector('#settingsSaveBtn');
        const invoiceVatRateEl = container.querySelector('#settingsInvoiceVatRate');
        const invoiceVatExemptEl = container.querySelector('#settingsInvoiceVatExempt');

        const companyBankEl = container.querySelector('#settingsCompanyBank');
        const companyAccountEl = container.querySelector('#settingsCompanyAccount');

        const syncBankFromAccount = () => {
            const guessed = guessBankNameFromAccountNumber(companyAccountEl?.value);
            if (!guessed) return;

            // Only auto-fill when bank is empty or was previously auto-filled.
            const current = (companyBankEl?.value || '').trim();
            const mayOverwrite = !current || companyBankEl?.dataset?.autofilled === '1';
            if (!mayOverwrite) return;

            companyBankEl.value = guessed;
            companyBankEl.dataset.autofilled = '1';
        };

        companyAccountEl?.addEventListener('input', syncBankFromAccount);
        companyAccountEl?.addEventListener('blur', syncBankFromAccount);

        companyBankEl?.addEventListener('input', () => {
            // User manually edited the bank field -> stop overwriting.
            if (!companyBankEl) return;
            companyBankEl.dataset.autofilled = '0';
        });

        // Initial sync (pre-filled account from backend)
        syncBankFromAccount();

        const triggerDownload = (blob, filename) => {
            if (!blob) return;
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename || 'download';
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
        };

        // Maintenance tab actions
        const dbBackupBtn = container.querySelector('#settingsDbBackupBtn');
        const fullBackupBtn = container.querySelector('#settingsFullBackupBtn');
        const fullBackupsRefreshBtn = container.querySelector('#settingsFullBackupsRefreshBtn');
        const fullBackupsList = container.querySelector('#settingsFullBackupsList');
        const fullRestoreConfirm = container.querySelector('#settingsFullRestoreConfirm');
        const dbRestoreBtn = container.querySelector('#settingsDbRestoreBtn');
        const dbRestoreFile = container.querySelector('#settingsDbRestoreFile');
        const dbRestoreConfirm = container.querySelector('#settingsDbRestoreConfirm');

        const purgeRunBtn = container.querySelector('#purgeRunBtn');
        const purgeJobs = container.querySelector('#purgeJobs');
        const purgeVouchers = container.querySelector('#purgeVouchers');
        const purgePromotions = container.querySelector('#purgePromotions');
        const purgeInvoices = container.querySelector('#purgeInvoices');
        const purgeContracts = container.querySelector('#purgeContracts');
        const purgeConsents = container.querySelector('#purgeConsents');
        const purgeDeleteFiles = container.querySelector('#purgeDeleteFiles');
        const purgeConfirm = container.querySelector('#purgeConfirm');

        dbBackupBtn?.addEventListener('click', async () => {
            try {
                const res = await settingsAPI.downloadDbBackup({ showErrors: true, showLoading: true });
                if (!res) return;
                triggerDownload(res.blob, res.filename || 'db_backup.sql');
                showToast('Backup bazy pobrany', 'success');
            } catch (_) {
                // apiDownload already shows errors
            }
        });

        fullBackupBtn?.addEventListener('click', async () => {
            try {
                const created = await settingsAPI.createFullBackupPersisted({ showLoading: true, showErrors: true });
                const name = created?.data?.name;
                if (name) {
                    await refreshFullBackups();
                    // Best-effort: download the freshly created backup.
                    try {
                        const res = await settingsAPI.downloadStoredFullBackup(name, { showErrors: true, showLoading: true });
                        if (res) triggerDownload(res.blob, res.filename || name);
                    } catch (_) {
                        // ignore
                    }
                }
                showToast('Pełny backup zapisany na serwerze', 'success');
            } catch (_) {
                // apiRequest already shows errors
            }
        });

        function formatBytes(bytes) {
            const n = Number(bytes || 0);
            if (!Number.isFinite(n) || n <= 0) return '0 B';
            const units = ['B', 'KB', 'MB', 'GB', 'TB'];
            let idx = 0;
            let v = n;
            while (v >= 1024 && idx < units.length - 1) {
                v /= 1024;
                idx += 1;
            }
            const digits = idx === 0 ? 0 : idx === 1 ? 0 : 1;
            return `${v.toFixed(digits)} ${units[idx]}`;
        }

        function renderFullBackups(items) {
            if (!Array.isArray(items) || items.length === 0) {
                return '<div class="text-muted">Brak zapisanych backupów.</div>';
            }

            return `
                <div class="table-responsive">
                    <table class="table table-sm table-hover align-middle mb-0">
                        <thead>
                            <tr>
                                <th>Nazwa</th>
                                <th>Utworzono</th>
                                <th class="text-end">Rozmiar</th>
                                <th class="text-end">Akcje</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${items.map((b) => {
                                const createdAt = b?.created_at ? new Date(b.created_at) : null;
                                const createdLabel = createdAt && !Number.isNaN(createdAt.getTime())
                                    ? createdAt.toLocaleString('pl-PL')
                                    : '-';
                                const safeName = encodeURIComponent(b?.name || '');
                                return `
                                    <tr>
                                        <td class="text-break"><code>${escapeHtml(b?.name || '')}</code></td>
                                        <td>${escapeHtml(createdLabel)}</td>
                                        <td class="text-end">${escapeHtml(formatBytes(b?.size || 0))}</td>
                                        <td class="text-end">
                                            <div class="btn-group btn-group-sm" role="group">
                                                <button class="btn btn-outline-success" type="button" data-action="download" data-name="${safeName}">
                                                    Pobierz
                                                </button>
                                                <button class="btn btn-outline-warning" type="button" data-action="restore" data-name="${safeName}">
                                                    Przywróć
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        async function refreshFullBackups() {
            if (!fullBackupsList) return;
            fullBackupsList.innerHTML = '<div class="text-muted">Ładowanie…</div>';
            try {
                const res = await settingsAPI.listFullBackups({ showErrors: false });
                const items = res?.data || [];
                fullBackupsList.innerHTML = renderFullBackups(items);
            } catch (_) {
                fullBackupsList.innerHTML = '<div class="text-muted">Nie udało się pobrać listy backupów.</div>';
            }
        }

        fullBackupsRefreshBtn?.addEventListener('click', refreshFullBackups);
        refreshFullBackups();

        fullBackupsList?.addEventListener('click', async (e) => {
            const btn = e?.target?.closest?.('button[data-action]');
            if (!btn) return;
            const action = btn.getAttribute('data-action');
            const nameEncoded = btn.getAttribute('data-name');
            if (!nameEncoded) return;
            const name = decodeURIComponent(nameEncoded);

            if (action === 'download') {
                try {
                    const res = await settingsAPI.downloadStoredFullBackup(name, { showErrors: true, showLoading: true });
                    if (!res) return;
                    triggerDownload(res.blob, res.filename || name);
                } catch (_) {
                    // apiDownload already shows errors
                }
                return;
            }

            if (action === 'restore') {
                const confirm = (fullRestoreConfirm?.value || '').trim();
                if (confirm !== DB_RESTORE_CONFIRM_PHRASE) {
                    showToast(`Aby przywrócić wpisz: ${DB_RESTORE_CONFIRM_PHRASE}`, 'warning');
                    return;
                }

                try {
                    await settingsAPI.restoreStoredFullBackup(name, confirm, { showLoading: true, showErrors: true });
                    showToast('Pełny backup przywrócony', 'success');
                } catch (_) {
                    // apiRequest already shows errors
                }
            }
        });

        dbRestoreBtn?.addEventListener('click', async () => {
            const file = dbRestoreFile?.files?.[0];
            const confirm = (dbRestoreConfirm?.value || '').trim();

            if (!file) {
                showToast('Wybierz plik SQL', 'warning');
                return;
            }
            if (confirm !== DB_RESTORE_CONFIRM_PHRASE) {
                showToast(`Aby przywrócić wpisz: ${DB_RESTORE_CONFIRM_PHRASE}`, 'warning');
                return;
            }

            try {
                await settingsAPI.restoreDbBackup(file, confirm, { showLoading: true, showErrors: true });
                showToast('Backup bazy przywrócony', 'success');
            } catch (_) {
                // apiRequest already shows errors
            }
        });

        purgeRunBtn?.addEventListener('click', async () => {
            const confirm = (purgeConfirm?.value || '').trim();
            if (confirm !== PURGE_CONFIRM_PHRASE) {
                showToast(`Aby usunąć dane wpisz: ${PURGE_CONFIRM_PHRASE}`, 'warning');
                return;
            }

            const targets = [];
            if (purgeJobs?.checked) targets.push('jobs');
            if (purgeVouchers?.checked) targets.push('vouchers');
            if (purgePromotions?.checked) targets.push('promotions');
            if (purgeInvoices?.checked) targets.push('invoices');
            if (purgeContracts?.checked) targets.push('contracts');
            if (purgeConsents?.checked) targets.push('consents');

            if (targets.length === 0) {
                showToast('Wybierz co najmniej jedną opcję', 'warning');
                return;
            }

            try {
                await settingsAPI.purgeData({
                    targets,
                    delete_files: Boolean(purgeDeleteFiles?.checked),
                    confirm,
                }, { showLoading: true, showErrors: true });

                showToast('Dane usunięte', 'success');
                // Refresh the view to update any dependent UI counts.
                renderSettings();
            } catch (_) {
                // apiRequest already shows errors
            }
        });

        const syncVatDisabled = () => {
            const exempt = Boolean(invoiceVatExemptEl?.checked);
            if (invoiceVatRateEl) {
                invoiceVatRateEl.disabled = exempt;
                if (exempt) invoiceVatRateEl.value = '0';
            }
        };
        invoiceVatExemptEl?.addEventListener('change', syncVatDisabled);
        syncVatDisabled();

        if (formEl) {
            wireClearOnInput(formEl);
            formEl.addEventListener('submit', async (e) => {
                e.preventDefault();

                const companyNameEl = formEl.querySelector('#settingsCompanyName');
                const companyAddressEl = formEl.querySelector('#settingsCompanyAddress');
                const companyNipEl = formEl.querySelector('#settingsCompanyNip');
                const companyEmailEl = formEl.querySelector('#settingsCompanyEmail');
                const invoicePrefixEl = container.querySelector('#settingsInvoicePrefix');
                const invoiceDepositPrefixEl = container.querySelector('#settingsInvoiceDepositPrefix');
                const invoiceCorrectionPrefixEl = container.querySelector('#settingsInvoiceCorrectionPrefix');
                const invoiceYearFormatEl = container.querySelector('#settingsInvoiceYearFormat');
                const canvaAccessTokenEl = container.querySelector('#settingsCanvaAccessToken');
                const canvaClientIdEl = container.querySelector('#settingsCanvaClientId');
                const canvaClientSecretEl = container.querySelector('#settingsCanvaClientSecret');

                let ok = validateRequiredFields(formEl);
                ok = requireEmail(companyEmailEl) && ok;
                ok = requireValue(invoicePrefixEl, 'Wpisz prefix') && ok;
                ok = requireValue(invoiceDepositPrefixEl, 'Wpisz prefix faktur zaliczkowych') && ok;
                ok = requireValue(invoiceCorrectionPrefixEl, 'Wpisz prefix faktur korygujących') && ok;
                ok = requireValue(invoiceYearFormatEl, 'Wpisz format roku') && ok;
                ok = requireValue(invoiceVatRateEl, 'Wybierz VAT') && ok;
                ok = requireValue(companyNameEl, 'Wpisz nazwę firmy') && ok;
                ok = requireValue(companyAddressEl, 'Wpisz adres') && ok;
                ok = requireValue(companyNipEl, 'Wpisz NIP') && ok;
                if (!ok) return;

                const payload = {
                    company: {
                        name: (companyNameEl?.value || '').trim(),
                        address: (companyAddressEl?.value || '').trim(),
                        nip: (companyNipEl?.value || '').trim(),
                        phone: (formEl.querySelector('#settingsCompanyPhone')?.value || '').trim(),
                        email: (companyEmailEl?.value || '').trim(),
                        bank: (formEl.querySelector('#settingsCompanyBank')?.value || '').trim(),
                        account: (formEl.querySelector('#settingsCompanyAccount')?.value || '').trim(),
                    },
                    invoice: {
                        prefix: (invoicePrefixEl?.value || '').trim(),
                        deposit_prefix: (invoiceDepositPrefixEl?.value || '').trim(),
                        correction_prefix: (invoiceCorrectionPrefixEl?.value || '').trim(),
                        year_format: (invoiceYearFormatEl?.value || '').trim(),
                        vat_rate: (invoiceVatRateEl?.value || '').trim(),
                        vat_exempt: Boolean(invoiceVatExemptEl?.checked),
                    },
                    branding: {
                        name: (container.querySelector('#settingsCrmName')?.value || '').trim(),
                    },
                    watermark: {
                        text: (container.querySelector('#settingsWatermarkText')?.value || '').trim(),
                    },
                };

                // Canva credentials are sensitive; only send when filled.
                const canvaAccessToken = (canvaAccessTokenEl?.value || '').trim();
                const canvaClientId = (canvaClientIdEl?.value || '').trim();
                const canvaClientSecret = (canvaClientSecretEl?.value || '').trim();
                const canvaPatch = {
                    ...(canvaAccessToken ? { access_token: canvaAccessToken } : {}),
                    ...(canvaClientId ? { client_id: canvaClientId } : {}),
                    ...(canvaClientSecret ? { client_secret: canvaClientSecret } : {}),
                };
                if (Object.keys(canvaPatch).length > 0) {
                    payload.integrations = { canva: canvaPatch };
                }

                try {
                    if (saveBtn) saveBtn.disabled = true;
                    await settingsAPI.update(payload, { showLoading: true });
                    // Apply new name/title/logo state (name) without reload.
                    applyBranding({ force: true }).catch(() => {});
                } catch (err) {
                    console.error(err);
                    showToast('Nie udało się zapisać ustawień', 'danger');
                } finally {
                    if (saveBtn) saveBtn.disabled = false;
                }
            });
        }

        // Logo upload/delete
        const uploadBtn = container.querySelector('#settingsUploadLogoBtn');
        const deleteBtn = container.querySelector('#settingsDeleteLogoBtn');
        const fileInput = container.querySelector('#settingsLogoFile');

        uploadBtn?.addEventListener('click', async () => {
            const file = fileInput?.files?.[0];
            if (!file) {
                showToast('Wybierz plik logo', 'warning');
                return;
            }
            try {
                uploadBtn.disabled = true;
                await settingsAPI.uploadLogo(file);
                await applyBranding({ force: true });
                await renderSettings();
            } catch (e) {
                console.error(e);
            } finally {
                uploadBtn.disabled = false;
            }
        });

        deleteBtn?.addEventListener('click', async () => {
            const ok = await confirmDialog({
                title: 'Usuń logo',
                message: 'Czy na pewno chcesz usunąć logo?',
                confirmText: 'Usuń',
                cancelText: 'Anuluj',
                danger: true,
            });
            if (!ok) return;
            try {
                deleteBtn.disabled = true;
                await settingsAPI.deleteLogo();
                await applyBranding({ force: true });
                await renderSettings();
            } catch (e) {
                console.error(e);
            } finally {
                deleteBtn.disabled = false;
            }
        });

        // Gallery logo upload/delete
        const uploadGalleryLogoBtn = container.querySelector('#settingsUploadGalleryLogoBtn');
        const deleteGalleryLogoBtn = container.querySelector('#settingsDeleteGalleryLogoBtn');
        const galleryLogoFileInput = container.querySelector('#settingsGalleryLogoFile');

        uploadGalleryLogoBtn?.addEventListener('click', async () => {
            const file = galleryLogoFileInput?.files?.[0];
            if (!file) {
                showToast('Wybierz plik logo galerii', 'warning');
                return;
            }
            try {
                uploadGalleryLogoBtn.disabled = true;
                await settingsAPI.uploadGalleryLogo(file);
                await applyBranding({ force: true });
                await renderSettings();
            } catch (e) {
                console.error(e);
            } finally {
                uploadGalleryLogoBtn.disabled = false;
            }
        });

        deleteGalleryLogoBtn?.addEventListener('click', async () => {
            const ok = await confirmDialog({
                title: 'Usuń logo galerii',
                message: 'Czy na pewno chcesz usunąć logo galerii (widok dla klienta)?',
                confirmText: 'Usuń',
                cancelText: 'Anuluj',
                danger: true,
            });
            if (!ok) return;
            try {
                deleteGalleryLogoBtn.disabled = true;
                await settingsAPI.deleteGalleryLogo();
                await applyBranding({ force: true });
                await renderSettings();
            } catch (e) {
                console.error(e);
            } finally {
                deleteGalleryLogoBtn.disabled = false;
            }
        });

        // Offers/addons buttons
        container.querySelector('#openCreateOfferBtn')?.addEventListener('click', () => openOfferModal({ mode: 'create' }));
        container.querySelector('#openCreateAddonBtn')?.addEventListener('click', () => openOfferAddonModal({ mode: 'create' }));

        // Promotions button
        container.querySelector('#openCreatePromotionBtn')?.addEventListener('click', () => openPromotionModal({ mode: 'create' }));

        // Expose edit/delete handlers
        window.editOffer = (id) => openOfferModal({ mode: 'edit', offerId: id });
        window.deleteOffer = async (id) => {
            const offer = cachedOffers.find((o) => o.id === id);
            const ok = await confirmDialog({
                title: 'Usuń pakiet',
                message: `Czy na pewno chcesz usunąć pakiet "${offer?.name || id}"? (zostanie dezaktywowany)`,
                confirmText: 'Usuń',
                cancelText: 'Anuluj',
                danger: true,
            });
            if (!ok) return;
            try {
                await jobsAPI.deleteOffer(id);
                await renderSettings();
            } catch (err) {
                console.error(err);
            }
        };

        window.editOfferAddon = (id) => openOfferAddonModal({ mode: 'edit', addonId: id });
        window.deleteOfferAddon = async (id) => {
            const addon = cachedOffers.flatMap((o) => o.addons || []).find((a) => a.id === id);
            const ok = await confirmDialog({
                title: 'Usuń dodatek',
                message: `Czy na pewno chcesz usunąć dodatek "${addon?.name || id}"? (zostanie ukryty)`,
                confirmText: 'Usuń',
                cancelText: 'Anuluj',
                danger: true,
            });
            if (!ok) return;
            try {
                await jobsAPI.deleteOfferAddon(id);
                await renderSettings();
            } catch (err) {
                console.error(err);
            }
        };

        // Promotions handlers
        window.editPromotion = (id) => openPromotionModal({ mode: 'edit', promotionId: id });
        window.deletePromotion = async (id) => {
            const promo = cachedPromotions.find((p) => p.id === id);
            const ok = await confirmDialog({
                title: 'Usuń promocję',
                message: `Czy na pewno chcesz usunąć promocję typu "${promo?.promo_type || id}"?`,
                confirmText: 'Usuń',
                cancelText: 'Anuluj',
                danger: true,
            });
            if (!ok) return;
            try {
                await promotionsAPI.delete(id);
                await renderSettings();
            } catch (err) {
                console.error(err);
            }
        };

    } catch (err) {
        console.error(err);
        showToast('Błąd ładowania ustawień', 'danger');
    }
}

function formatDateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleString('pl-PL');
}

function renderPromotionsRows(promotions) {
    if (!promotions || promotions.length === 0) {
        return `
            <tr>
                <td colspan="6" class="text-center py-5 text-muted">
                    <i class="bi bi-inbox display-6"></i>
                    <div class="mt-2">Brak promocji</div>
                </td>
            </tr>
        `;
    }

    const hasActiveByType = {};
    for (const p of promotions) {
        if (!p?.promo_type) continue;
        if (p?.is_active) hasActiveByType[p.promo_type] = true;
    }

    return promotions.map((p) => {
        const type = p?.promo_type || '-';
        const isActive = Boolean(p?.is_active);
        const status = isActive
            ? '<span class="badge bg-success">Aktywna</span>'
            : '<span class="badge bg-secondary">Nieaktywna</span>';

        const locked = Boolean(hasActiveByType[type]);
        const disabledAttrs = locked ? 'disabled aria-disabled="true"' : '';
        const title = locked
            ? 'Edycja/usuwanie niedostępne: istnieje aktywna promocja tego typu'
            : 'Edytuj/Usuń';

        return `
            <tr>
                <td><strong>${escapeHtml(type)}</strong></td>
                <td>${escapeHtml((p?.value ?? '').toString())}</td>
                <td>${escapeHtml((p?.duration_days ?? '-').toString())}</td>
                <td>${escapeHtml(formatDateTime(p?.active_until))}</td>
                <td>${status}</td>
                <td class="text-end">
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="window.editPromotion(${p.id})" title="${escapeHtml(title)}" ${disabledAttrs}>
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="window.deletePromotion(${p.id})" title="${escapeHtml(title)}" ${disabledAttrs}>
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function renderPromotionModal() {
    return `
        <div class="modal fade" id="promotionModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="promotionModalTitle">Promocja</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="promotionForm" novalidate>
                            <input type="hidden" id="promotionId" />
                            <div class="row g-3">
                                <div class="col-md-4">
                                    <label class="form-label">Typ *</label>
                                    <input class="form-control" id="promotionType" required placeholder="np. voucher" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Wartość (PLN) *</label>
                                    <input class="form-control" id="promotionValue" required placeholder="np. 200.00" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Czas trwania (dni) *</label>
                                    <input class="form-control" id="promotionDurationDays" type="number" min="1" required />
                                </div>
                                <div class="col-12">
                                    <label class="form-label">Canva project URL</label>
                                    <input class="form-control" id="promotionCanvaProjectUrl" placeholder="https://www.canva.com/design/..." />
                                    <div class="form-text">Opcjonalne: link referencyjny do projektu w Canvie (CRM nie personalizuje szablonu w Canvie).</div>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Tło vouchera (przód) PNG/JPG</label>
                                    <input class="form-control" id="promotionVoucherFront" type="file" accept="image/png,image/jpeg" />
                                    <div class="form-text" id="promotionVoucherFrontExisting"></div>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Tło vouchera (tył) PNG/JPG</label>
                                    <input class="form-control" id="promotionVoucherBack" type="file" accept="image/png,image/jpeg" />
                                    <div class="form-text" id="promotionVoucherBackExisting"></div>
                                </div>

                                <div class="col-12"><hr class="my-2"/></div>
                                <div class="col-12">
                                    <label class="form-label">Układ PDF vouchera (pozycje w px)</label>
                                    <div class="form-text">Współrzędne X/Y liczone od lewego-górnego rogu strony A4. Tekst to tylko „Bon ważny do …”, a QR zawiera kod vouchera.</div>
                                </div>
                                <div class="col-md-3">
                                    <label class="form-label">Tekst X (px)</label>
                                    <input class="form-control" id="promotionVoucherTextX" type="number" step="1" placeholder="np. 76" />
                                </div>
                                <div class="col-md-3">
                                    <label class="form-label">Tekst Y (px)</label>
                                    <input class="form-control" id="promotionVoucherTextY" type="number" step="1" placeholder="np. 76" />
                                </div>
                                <div class="col-md-3">
                                    <label class="form-label">QR X (px)</label>
                                    <input class="form-control" id="promotionVoucherQrX" type="number" step="1" placeholder="np. 605" />
                                </div>
                                <div class="col-md-3">
                                    <label class="form-label">QR Y (px)</label>
                                    <input class="form-control" id="promotionVoucherQrY" type="number" step="1" placeholder="np. 76" />
                                </div>
                                <div class="col-md-8">
                                    <label class="form-label">Czcionka (font-family)</label>
                                    <input class="form-control" id="promotionVoucherFontFamily" placeholder="np. DejaVu Sans" />
                                    <div class="form-text">Opcjonalne. Musi być dostępna w systemie na serwerze (WeasyPrint/Pango).</div>
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Rozmiar czcionki (pt)</label>
                                    <input class="form-control" id="promotionVoucherFontSize" type="number" step="0.5" placeholder="np. 12" />
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="button" class="btn btn-success" id="savePromotionBtn">
                            <i class="bi bi-check2"></i> Zapisz
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function openPromotionModal({ mode, promotionId = null }) {
    const modalEl = document.getElementById('promotionModal');
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);

    const titleEl = document.getElementById('promotionModalTitle');
    const form = document.getElementById('promotionForm');

    const idEl = document.getElementById('promotionId');
    const typeEl = document.getElementById('promotionType');
    const valueEl = document.getElementById('promotionValue');
    const durationEl = document.getElementById('promotionDurationDays');
    const canvaUrlEl = document.getElementById('promotionCanvaProjectUrl');
    const frontEl = document.getElementById('promotionVoucherFront');
    const backEl = document.getElementById('promotionVoucherBack');
    const textXEl = document.getElementById('promotionVoucherTextX');
    const textYEl = document.getElementById('promotionVoucherTextY');
    const qrXEl = document.getElementById('promotionVoucherQrX');
    const qrYEl = document.getElementById('promotionVoucherQrY');
    const fontFamilyEl = document.getElementById('promotionVoucherFontFamily');
    const fontSizeEl = document.getElementById('promotionVoucherFontSize');
    const frontExistingEl = document.getElementById('promotionVoucherFrontExisting');
    const backExistingEl = document.getElementById('promotionVoucherBackExisting');
    const saveBtn = document.getElementById('savePromotionBtn');

    const clearPreviewObjectUrl = (el) => {
        if (!el) return;
        const prev = el.dataset.objectUrl;
        if (prev) {
            try { URL.revokeObjectURL(prev); } catch (_) { /* ignore */ }
            delete el.dataset.objectUrl;
        }
    };

    const setPreviewHtml = (el, html) => {
        if (!el) return;
        clearPreviewObjectUrl(el);
        el.innerHTML = html || '';
    };

    const renderExistingTemplatePreview = (el, promotionId, side, relPath) => {
        if (!el) return;
        if (!relPath) {
            setPreviewHtml(el, '<span class="text-muted">Aktualnie: brak</span>');
            return;
        }
        // Use API endpoint for safe preview.
        const src = `#/`; // dummy to avoid accidental navigation
        // Build absolute URL (works with SPA hash routing)
        const url = `/api/promotions/${promotionId}/voucher-template/${side}`;
        setPreviewHtml(
            el,
            `<div class="d-flex align-items-center gap-2">`
            + `<span class="text-muted">Aktualnie:</span>`
            + `<img src="${url}" alt="${side}" class="img-thumbnail" style="max-height:120px; max-width:100%; object-fit:contain;"/>`
            + `</div>`
        );
    };

    const renderSelectedFilePreview = (el, file) => {
        if (!el) return;
        if (!file) {
            setPreviewHtml(el, '');
            return;
        }
        if (!String(file.type || '').startsWith('image/')) {
            setPreviewHtml(el, `<span class="text-muted">Wybrano plik: ${escapeHtml(file.name || '')}</span>`);
            return;
        }
        const objectUrl = URL.createObjectURL(file);
        el.dataset.objectUrl = objectUrl;
        el.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <span class="text-muted">Wybrano:</span>
                <img src="${objectUrl}" alt="preview" class="img-thumbnail" style="max-height:120px; max-width:100%; object-fit:contain;"/>
            </div>
        `;
    };

    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    const isCreate = mode === 'create';
    if (titleEl) titleEl.textContent = isCreate ? 'Nowa promocja' : 'Edytuj promocję';

    form?.reset?.();
    idEl.value = '';
    if (frontEl) frontEl.value = '';
    if (backEl) backEl.value = '';
    if (frontExistingEl) setPreviewHtml(frontExistingEl, '');
    if (backExistingEl) setPreviewHtml(backExistingEl, '');

    if (!isCreate) {
        const promo = cachedPromotions.find((p) => p.id === promotionId);
        if (!promo) {
            showToast('Nie znaleziono promocji', 'danger');
            return;
        }
        idEl.value = String(promo.id);
        typeEl.value = promo.promo_type || '';
        valueEl.value = (promo.value ?? '').toString();
        durationEl.value = (promo.duration_days ?? '').toString();
        if (canvaUrlEl) canvaUrlEl.value = promo.canva_project_url || '';
        renderExistingTemplatePreview(frontExistingEl, promo.id, 'front', promo.voucher_bg_front_path);
        renderExistingTemplatePreview(backExistingEl, promo.id, 'back', promo.voucher_bg_back_path);

        if (textXEl) textXEl.value = promo.voucher_text_x_px ?? '';
        if (textYEl) textYEl.value = promo.voucher_text_y_px ?? '';
        if (qrXEl) qrXEl.value = promo.voucher_qr_x_px ?? '';
        if (qrYEl) qrYEl.value = promo.voucher_qr_y_px ?? '';
        if (fontFamilyEl) fontFamilyEl.value = promo.voucher_text_font_family || '';
        if (fontSizeEl) fontSizeEl.value = promo.voucher_text_font_size_pt ?? '';
    } else {
        if (canvaUrlEl) canvaUrlEl.value = '';
        if (frontExistingEl) setPreviewHtml(frontExistingEl, '');
        if (backExistingEl) setPreviewHtml(backExistingEl, '');

        if (textXEl) textXEl.value = '';
        if (textYEl) textYEl.value = '';
        if (qrXEl) qrXEl.value = '';
        if (qrYEl) qrYEl.value = '';
        if (fontFamilyEl) fontFamilyEl.value = '';
        if (fontSizeEl) fontSizeEl.value = '';
    }

    // Live preview for newly selected files.
    if (frontEl) {
        frontEl.onchange = () => {
            const f = frontEl.files?.[0] || null;
            if (f) {
                renderSelectedFilePreview(frontExistingEl, f);
            }
        };
    }
    if (backEl) {
        backEl.onchange = () => {
            const f = backEl.files?.[0] || null;
            if (f) {
                renderSelectedFilePreview(backExistingEl, f);
            }
        };
    }

    saveBtn.onclick = async () => {
        let ok = validateRequiredFields(form);
        ok = requireValue(typeEl, 'Wpisz typ') && ok;
        ok = requireValue(valueEl, 'Wpisz wartość') && ok;
        ok = requireValue(durationEl, 'Wpisz czas trwania') && ok;
        if (!ok) return;

        const payload = {
            promo_type: (typeEl.value || '').trim(),
            value: (valueEl.value || '').trim(),
            duration_days: parseInt(durationEl.value || '0', 10),
            canva_project_url: (canvaUrlEl?.value || '').trim() || null,
            voucher_text_x_px: (textXEl?.value || '').trim() || null,
            voucher_text_y_px: (textYEl?.value || '').trim() || null,
            voucher_qr_x_px: (qrXEl?.value || '').trim() || null,
            voucher_qr_y_px: (qrYEl?.value || '').trim() || null,
            voucher_text_font_family: (fontFamilyEl?.value || '').trim() || null,
            voucher_text_font_size_pt: (fontSizeEl?.value || '').trim() || null,
        };

        const frontFile = frontEl?.files?.[0] || null;
        const backFile = backEl?.files?.[0] || null;

        try {
            saveBtn.disabled = true;
            if (isCreate) {
                const created = await promotionsAPI.create(payload);
                const newId = created?.data?.id;
                if (newId && (frontFile || backFile)) {
                    const fd = new FormData();
                    if (payload.canva_project_url) fd.append('canva_project_url', payload.canva_project_url);
                    if (frontFile) fd.append('front', frontFile);
                    if (backFile) fd.append('back', backFile);
                    await promotionsAPI.uploadVoucherTemplate(newId, fd, { showErrors: true });
                }
            } else {
                const id = parseInt(idEl.value, 10);
                await promotionsAPI.update(id, payload);
                if (id && (frontFile || backFile)) {
                    const fd = new FormData();
                    if (payload.canva_project_url) fd.append('canva_project_url', payload.canva_project_url);
                    if (frontFile) fd.append('front', frontFile);
                    if (backFile) fd.append('back', backFile);
                    await promotionsAPI.uploadVoucherTemplate(id, fd, { showErrors: true });
                }
            }
            modal.hide();
            await renderSettings();
        } catch (err) {
            console.error(err);
        } finally {
            saveBtn.disabled = false;
        }
    };

    modal.show();
}

function renderOfferModal() {
    return `
        <div class="modal fade" id="offerModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="offerModalTitle">Pakiet</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="offerForm" novalidate>
                            <input type="hidden" id="offerId" />
                            <div class="row g-3">
                                <div class="col-12">
                                    <label class="form-label">Nazwa *</label>
                                    <input class="form-control" id="offerName" required />
                                </div>
                                <div class="col-12">
                                    <label class="form-label">Opis</label>
                                    <textarea class="form-control" id="offerDescription" rows="2"></textarea>
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Cena bazowa *</label>
                                    <input class="form-control" id="offerBasePrice" required />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Godziny</label>
                                    <input class="form-control" id="offerHours" type="number" min="0" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Liczba zdjęć</label>
                                    <input class="form-control" id="offerPhotos" type="number" min="0" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Wideo</label>
                                    <select class="form-select" id="offerVideo">
                                        <option value="false">Nie</option>
                                        <option value="true">Tak</option>
                                    </select>
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Kolejność</label>
                                    <input class="form-control" id="offerOrder" type="number" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Status</label>
                                    <select class="form-select" id="offerActive">
                                        <option value="true">Aktywna</option>
                                        <option value="false">Nieaktywna</option>
                                    </select>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="button" class="btn btn-success" id="saveOfferBtn">
                            <i class="bi bi-check2"></i> Zapisz
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderOfferAddonModal(offers) {
    return `
        <div class="modal fade" id="offerAddonModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="offerAddonModalTitle">Dodatek</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="offerAddonForm" novalidate>
                            <input type="hidden" id="offerAddonId" />
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Pakiet *</label>
                                    <select class="form-select" id="offerAddonOfferId" required>
                                        <option value="">Wybierz...</option>
                                        ${(offers || []).map((o) => `<option value="${o.id}">${escapeHtml(o.name || '')}</option>`).join('')}
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Nazwa *</label>
                                    <input class="form-control" id="offerAddonName" required />
                                </div>
                                <div class="col-12">
                                    <label class="form-label">Opis</label>
                                    <textarea class="form-control" id="offerAddonDescription" rows="2"></textarea>
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Cena *</label>
                                    <input class="form-control" id="offerAddonPrice" required />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Model</label>
                                    <select class="form-select" id="offerAddonPricingModel">
                                        <option value="fixed">fixed</option>
                                        <option value="per_unit">per_unit</option>
                                    </select>
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Kategoria</label>
                                    <input class="form-control" id="offerAddonCategory" placeholder="addon" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Miesiące (opc.)</label>
                                    <input class="form-control" id="offerAddonDurationMonths" type="number" min="0" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Kolejność</label>
                                    <input class="form-control" id="offerAddonOrder" type="number" />
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label">Status</label>
                                    <select class="form-select" id="offerAddonAvailable">
                                        <option value="true">Dostępny</option>
                                        <option value="false">Niedostępny</option>
                                    </select>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="button" class="btn btn-success" id="saveOfferAddonBtn">
                            <i class="bi bi-check2"></i> Zapisz
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function openOfferModal({ mode, offerId = null }) {
    const modalEl = document.getElementById('offerModal');
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);

    const titleEl = document.getElementById('offerModalTitle');
    const form = document.getElementById('offerForm');

    const idEl = document.getElementById('offerId');
    const nameEl = document.getElementById('offerName');
    const descEl = document.getElementById('offerDescription');
    const basePriceEl = document.getElementById('offerBasePrice');
    const hoursEl = document.getElementById('offerHours');
    const photosEl = document.getElementById('offerPhotos');
    const videoEl = document.getElementById('offerVideo');
    const orderEl = document.getElementById('offerOrder');
    const activeEl = document.getElementById('offerActive');
    const saveBtn = document.getElementById('saveOfferBtn');

    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    const isCreate = mode === 'create';
    if (titleEl) titleEl.textContent = isCreate ? 'Nowy pakiet' : 'Edytuj pakiet';

    form?.reset?.();
    idEl.value = '';

    if (!isCreate) {
        const offer = cachedOffers.find((o) => o.id === offerId);
        if (!offer) {
            showToast('Nie znaleziono pakietu', 'danger');
            return;
        }
        idEl.value = String(offer.id);
        nameEl.value = offer.name || '';
        descEl.value = offer.description || '';
        basePriceEl.value = (offer.base_price ?? '').toString();
        hoursEl.value = offer.hours_included ?? '';
        photosEl.value = offer.photos_count ?? '';
        videoEl.value = String(Boolean(offer.video_included));
        orderEl.value = offer.display_order ?? 0;
        activeEl.value = String(Boolean(offer.is_active));
    } else {
        activeEl.value = 'true';
        videoEl.value = 'false';
        orderEl.value = '0';
    }

    saveBtn.onclick = async () => {
        let ok = validateRequiredFields(form);
        ok = requireValue(nameEl, 'Wpisz nazwę') && ok;
        ok = requireValue(basePriceEl, 'Wpisz cenę') && ok;
        if (!ok) return;

        const payload = {
            name: (nameEl.value || '').trim(),
            description: (descEl.value || '').trim() || null,
            base_price: (basePriceEl.value || '').trim(),
            hours_included: hoursEl.value === '' ? null : parseInt(hoursEl.value, 10),
            photos_count: photosEl.value === '' ? null : parseInt(photosEl.value, 10),
            video_included: videoEl.value === 'true',
            display_order: parseInt(orderEl.value || '0', 10) || 0,
            is_active: activeEl.value === 'true',
        };

        try {
            saveBtn.disabled = true;
            if (isCreate) {
                await jobsAPI.createOffer(payload);
            } else {
                await jobsAPI.updateOffer(parseInt(idEl.value, 10), payload);
            }
            modal.hide();
            await renderSettings();
        } catch (err) {
            console.error(err);
        } finally {
            saveBtn.disabled = false;
        }
    };

    modal.show();
}

function openOfferAddonModal({ mode, addonId = null }) {
    const modalEl = document.getElementById('offerAddonModal');
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);

    const titleEl = document.getElementById('offerAddonModalTitle');
    const form = document.getElementById('offerAddonForm');

    const idEl = document.getElementById('offerAddonId');
    const offerIdEl = document.getElementById('offerAddonOfferId');
    const nameEl = document.getElementById('offerAddonName');
    const descEl = document.getElementById('offerAddonDescription');
    const priceEl = document.getElementById('offerAddonPrice');
    const pricingModelEl = document.getElementById('offerAddonPricingModel');
    const categoryEl = document.getElementById('offerAddonCategory');
    const durationEl = document.getElementById('offerAddonDurationMonths');
    const orderEl = document.getElementById('offerAddonOrder');
    const availableEl = document.getElementById('offerAddonAvailable');
    const saveBtn = document.getElementById('saveOfferAddonBtn');

    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    const isCreate = mode === 'create';
    if (titleEl) titleEl.textContent = isCreate ? 'Nowy dodatek' : 'Edytuj dodatek';

    form?.reset?.();
    idEl.value = '';

    if (!isCreate) {
        const addon = cachedOffers.flatMap((o) => o.addons || []).find((a) => a.id === addonId);
        if (!addon) {
            showToast('Nie znaleziono dodatku', 'danger');
            return;
        }
        idEl.value = String(addon.id);
        offerIdEl.value = String(addon.offer_id);
        nameEl.value = addon.name || '';
        descEl.value = addon.description || '';
        priceEl.value = (addon.price ?? '').toString();
        pricingModelEl.value = addon.pricing_model || 'fixed';
        categoryEl.value = addon.category || '';
        durationEl.value = addon.duration_months ?? '';
        orderEl.value = addon.display_order ?? 0;
        availableEl.value = String(Boolean(addon.is_available));
    } else {
        pricingModelEl.value = 'fixed';
        availableEl.value = 'true';
        orderEl.value = '0';
        categoryEl.value = 'addon';
    }

    saveBtn.onclick = async () => {
        let ok = validateRequiredFields(form);
        ok = requireValue(offerIdEl, 'Wybierz pakiet') && ok;
        ok = requireValue(nameEl, 'Wpisz nazwę') && ok;
        ok = requireValue(priceEl, 'Wpisz cenę') && ok;
        if (!ok) return;

        const payload = {
            offer_id: parseInt(offerIdEl.value, 10),
            name: (nameEl.value || '').trim(),
            description: (descEl.value || '').trim() || null,
            price: (priceEl.value || '').trim(),
            pricing_model: pricingModelEl.value,
            category: (categoryEl.value || '').trim() || 'addon',
            duration_months: durationEl.value === '' ? null : parseInt(durationEl.value, 10),
            display_order: parseInt(orderEl.value || '0', 10) || 0,
            is_available: availableEl.value === 'true',
        };

        try {
            saveBtn.disabled = true;
            if (isCreate) {
                await jobsAPI.createOfferAddon(payload);
            } else {
                await jobsAPI.updateOfferAddon(parseInt(idEl.value, 10), payload);
            }
            modal.hide();
            await renderSettings();
        } catch (err) {
            console.error(err);
        } finally {
            saveBtn.disabled = false;
        }
    };

    modal.show();
}

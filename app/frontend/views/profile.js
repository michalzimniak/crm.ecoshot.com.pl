/**
 * Profile View - Profil użytkownika
 */

import { authAPI, getCurrentUser, scheduleLoginRedirect } from '../api.js';
import { showToast } from '../toasts.js';
import { validateRequiredFields, setFieldError, wireClearOnInput } from '../forms.js';

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
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleString('pl-PL');
}

function isStrongPassword(password) {
    if (!password || password.length < 8) return false;
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasDigit = /\d/.test(password);
    return hasUpper && hasLower && hasDigit;
}

export async function renderProfile() {
    const container = document.getElementById('viewContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-person"></i> Profil</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    const user = await getCurrentUser();
    if (!user) {
        showToast('Sesja wygasła. Zaloguj się ponownie.', 'warning');
        scheduleLoginRedirect(2500);
        return;
    }

    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-person"></i> Profil</h1>
                <p class="text-muted mb-0">Twoje dane i bezpieczeństwo konta</p>
            </div>
        </div>

        <div class="row g-4">
            <div class="col-lg-6">
                <div class="card">
                    <div class="card-header"><strong>Dane konta</strong></div>
                    <div class="card-body">
                        <div class="row mb-2"><div class="col-4 text-muted">Login</div><div class="col-8">${escapeHtml(user.username || '-')}</div></div>
                        <div class="row mb-2"><div class="col-4 text-muted">Imię i nazwisko</div><div class="col-8">${escapeHtml(user.full_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || '-')}</div></div>
                        <div class="row mb-2"><div class="col-4 text-muted">Email</div><div class="col-8">${escapeHtml(user.email || '-')}</div></div>
                        <div class="row mb-2"><div class="col-4 text-muted">Telefon</div><div class="col-8">${escapeHtml(user.phone || '-')}</div></div>
                        <div class="row mb-2"><div class="col-4 text-muted">Rola</div><div class="col-8">${escapeHtml(user.role || '-')}</div></div>
                        <div class="row"><div class="col-4 text-muted">Ostatnie logowanie</div><div class="col-8">${formatDateTime(user.last_login)}</div></div>
                    </div>
                </div>
            </div>

            <div class="col-lg-6">
                <div class="card">
                    <div class="card-header"><strong>Zmiana hasła</strong></div>
                    <div class="card-body">
                        <form id="changePasswordForm" novalidate>
                            <div class="mb-3">
                                <label class="form-label">Aktualne hasło *</label>
                                <input type="password" class="form-control" id="oldPassword" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Nowe hasło *</label>
                                <input type="password" class="form-control" id="newPassword" required>
                                <div class="form-text">Min. 8 znaków, wielka i mała litera oraz cyfra.</div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Powtórz nowe hasło *</label>
                                <input type="password" class="form-control" id="newPassword2" required>
                            </div>
                            <button class="btn btn-success" type="submit">
                                <i class="bi bi-shield-lock"></i> Zmień hasło
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;

    const form = document.getElementById('changePasswordForm');
    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    form.onsubmit = async (e) => {
        e.preventDefault();

        if (!validateRequiredFields(form)) {
            return;
        }

        const oldEl = document.getElementById('oldPassword');
        const newEl = document.getElementById('newPassword');
        const new2El = document.getElementById('newPassword2');

        const oldPwd = oldEl.value;
        const newPwd = newEl.value;
        const newPwd2 = new2El.value;

        if (!isStrongPassword(newPwd)) {
            setFieldError(newEl, 'Hasło zbyt słabe (min. 8 znaków, duża/mała litera i cyfra)');
            newEl?.focus?.();
            return;
        }

        if (newPwd !== newPwd2) {
            setFieldError(new2El, 'Hasła nie są takie same');
            new2El?.focus?.();
            return;
        }

        try {
            await authAPI.changePassword(oldPwd, newPwd);

            oldEl.value = '';
            newEl.value = '';
            new2El.value = '';
        } catch (err) {
            console.error(err);
        }
    };
}

/**
 * Users View - Zarządzanie użytkownikami
 */

import { usersAPI, getCurrentUser } from '../api.js';
import { showToast } from '../toasts.js';
import { validateRequiredFields, requireEmail, setFieldError, wireClearOnInput } from '../forms.js';
import { confirmDialog } from '../confirm.js';

let currentFilters = {};
let cachedUsers = [];
let currentUserId = null;

const ROLE_LABELS = {
    admin: 'Admin',
    photographer: 'Fotograf',
    accountant: 'Księgowość',
    viewer: 'Podgląd',
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

export async function renderUsers() {
    const container = document.getElementById('viewContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-person-gear"></i> Użytkownicy</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;

    try {
        const [me, response] = await Promise.all([
            getCurrentUser(),
            usersAPI.getAll(currentFilters),
        ]);

        currentUserId = me?.id ?? null;
        cachedUsers = response?.data || [];

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-person-gear"></i> Użytkownicy</h1>
                    <p class="text-muted mb-0">Zarządzanie kontami w systemie</p>
                </div>
                <div>
                    <button class="btn btn-success" id="openCreateUserBtn">
                        <i class="bi bi-person-plus"></i> Nowy użytkownik
                    </button>
                </div>
            </div>

            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <input type="text" class="form-control" id="usersSearch" placeholder="Szukaj (login, email, imię/nazwisko)...">
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="usersRoleFilter">
                                <option value="">Wszystkie role</option>
                                <option value="admin">Admin</option>
                                <option value="photographer">Fotograf</option>
                                <option value="accountant">Księgowość</option>
                                <option value="viewer">Podgląd</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="usersActiveFilter">
                                <option value="">Aktywni i nieaktywni</option>
                                <option value="true">Tylko aktywni</option>
                                <option value="false">Tylko nieaktywni</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Użytkownik</th>
                                    <th>Email</th>
                                    <th>Telefon</th>
                                    <th>Rola</th>
                                    <th>Ostatnie logowanie</th>
                                    <th>Status</th>
                                    <th>Akcje</th>
                                </tr>
                            </thead>
                            <tbody id="usersTbody">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            ${renderUserModal()}
        `;

        document.getElementById('openCreateUserBtn')?.addEventListener('click', () => openUserModal({ mode: 'create' }));

        // Init filters
        const roleEl = document.getElementById('usersRoleFilter');
        const activeEl = document.getElementById('usersActiveFilter');
        if (roleEl) roleEl.value = currentFilters.role || '';
        if (activeEl) activeEl.value = (currentFilters.is_active ?? '');

        setupUserFilters();
        renderUsersTable(cachedUsers);

    } catch (error) {
        console.error('Failed to load users:', error);
        showToast('Błąd ładowania użytkowników', 'danger');
    }
}

function setupUserFilters() {
    const searchEl = document.getElementById('usersSearch');
    const roleEl = document.getElementById('usersRoleFilter');
    const activeEl = document.getElementById('usersActiveFilter');

    let searchTimeout;
    searchEl?.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            const term = (e.target.value || '').trim().toLowerCase();
            const filtered = filterUsersLocally(term);
            renderUsersTable(filtered);
        }, 250);
    });

    roleEl?.addEventListener('change', async (e) => {
        currentFilters.role = e.target.value || undefined;
        if (!currentFilters.role) delete currentFilters.role;
        await renderUsers();
    });

    activeEl?.addEventListener('change', async (e) => {
        const value = e.target.value;
        if (value === '') {
            delete currentFilters.is_active;
        } else {
            currentFilters.is_active = value;
        }
        await renderUsers();
    });
}

function filterUsersLocally(term) {
    if (!term) return cachedUsers;
    return cachedUsers.filter(u => {
        const haystack = [u.username, u.email, u.first_name, u.last_name, u.full_name, u.phone]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();
        return haystack.includes(term);
    });
}

function renderUsersTable(users) {
    const tbody = document.getElementById('usersTbody');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5 text-muted">
                    <i class="bi bi-inbox display-6"></i>
                    <div class="mt-2">Brak użytkowników</div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = users.map(u => {
        const roleLabel = ROLE_LABELS[u.role] || u.role || '-';
        const statusBadge = u.is_active
            ? '<span class="badge bg-success">Aktywny</span>'
            : '<span class="badge bg-secondary">Nieaktywny</span>';

        const isSelf = currentUserId !== null && Number(u.id) === Number(currentUserId);

        const toggleBtn = u.is_active
            ? (isSelf
                ? `<button class="btn btn-outline-warning" disabled aria-disabled="true" title="Nie możesz dezaktywować aktualnie zalogowanego użytkownika">
                        <i class="bi bi-person-x"></i>
                   </button>`
                : `<button class="btn btn-outline-warning" onclick="window.deactivateUser(${u.id})" title="Dezaktywuj">
                        <i class="bi bi-person-x"></i>
                   </button>`)
            : `<button class="btn btn-outline-success" onclick="window.activateUser(${u.id})" title="Aktywuj">
                    <i class="bi bi-person-check"></i>
               </button>`;

        return `
            <tr>
                <td>#${u.id}</td>
                <td>
                    <strong>${escapeHtml(u.username || '-')}</strong>
                    <br>
                    <small class="text-muted">${escapeHtml(u.full_name || `${u.first_name || ''} ${u.last_name || ''}`.trim() || '-')}</small>
                </td>
                <td>${escapeHtml(u.email || '-')}</td>
                <td>${escapeHtml(u.phone || '-')}</td>
                <td><span class="badge bg-primary">${escapeHtml(roleLabel)}</span></td>
                <td>${formatDateTime(u.last_login)}</td>
                <td>${statusBadge}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="window.editUser(${u.id})" title="Edytuj">
                            <i class="bi bi-pencil"></i>
                        </button>
                        ${toggleBtn}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function renderUserModal() {
    return `
        <div class="modal fade" id="userModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="userModalTitle">Użytkownik</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="userForm" novalidate>
                            <input type="hidden" id="userId" />

                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Login *</label>
                                    <input class="form-control" id="userUsername" name="username" required />
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Email *</label>
                                    <input type="email" class="form-control" id="userEmail" name="email" required />
                                </div>

                                <div class="col-md-6">
                                    <label class="form-label">Imię *</label>
                                    <input class="form-control" id="userFirstName" name="first_name" required />
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Nazwisko *</label>
                                    <input class="form-control" id="userLastName" name="last_name" required />
                                </div>

                                <div class="col-md-6">
                                    <label class="form-label">Telefon</label>
                                    <input class="form-control" id="userPhone" name="phone" />
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Rola *</label>
                                    <select class="form-select" id="userRole" name="role" required>
                                        <option value="">Wybierz...</option>
                                        <option value="admin">Admin</option>
                                        <option value="photographer">Fotograf</option>
                                        <option value="accountant">Księgowość</option>
                                        <option value="viewer">Podgląd</option>
                                    </select>
                                </div>

                                <div class="col-12" id="passwordRow">
                                    <label class="form-label">Hasło *</label>
                                    <input type="password" class="form-control" id="userPassword" name="password" required />
                                    <div class="form-text">Min. 8 znaków, wielka i mała litera oraz cyfra.</div>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Anuluj</button>
                        <button type="button" class="btn btn-success" id="saveUserBtn">
                            <i class="bi bi-check2"></i> Zapisz
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function openUserModal({ mode, userId = null }) {
    const modalEl = document.getElementById('userModal');
    if (!modalEl) return;

    const modal = new bootstrap.Modal(modalEl);
    const titleEl = document.getElementById('userModalTitle');

    const form = document.getElementById('userForm');
    const idEl = document.getElementById('userId');
    const usernameEl = document.getElementById('userUsername');
    const emailEl = document.getElementById('userEmail');
    const firstNameEl = document.getElementById('userFirstName');
    const lastNameEl = document.getElementById('userLastName');
    const phoneEl = document.getElementById('userPhone');
    const roleEl = document.getElementById('userRole');
    const passwordRow = document.getElementById('passwordRow');
    const passwordEl = document.getElementById('userPassword');
    const saveBtn = document.getElementById('saveUserBtn');

    if (form && form.dataset.wireClearOnInput !== '1') {
        wireClearOnInput(form);
        form.dataset.wireClearOnInput = '1';
    }

    const isCreate = mode === 'create';
    if (titleEl) titleEl.textContent = isCreate ? 'Nowy użytkownik' : 'Edytuj użytkownika';

    // Reset form
    form?.reset?.();
    idEl.value = '';

    // Username editable only on create
    usernameEl.disabled = !isCreate;

    // Password required only on create
    if (passwordRow) passwordRow.style.display = isCreate ? '' : 'none';
    if (passwordEl) passwordEl.required = isCreate;

    if (!isCreate) {
        const user = cachedUsers.find(u => u.id === userId);
        if (!user) {
            showToast('Nie znaleziono użytkownika', 'danger');
            return;
        }

        idEl.value = String(user.id);
        usernameEl.value = user.username || '';
        emailEl.value = user.email || '';
        firstNameEl.value = user.first_name || '';
        lastNameEl.value = user.last_name || '';
        phoneEl.value = user.phone || '';
        roleEl.value = user.role || '';
    } else {
        roleEl.value = 'viewer';
    }

    saveBtn.onclick = async () => {
        const isValid = validateRequiredFields(form);
        if (!isValid) return;

        if (!requireEmail(emailEl)) {
            return;
        }

        if (isCreate) {
            const pwd = passwordEl.value;
            if (!isStrongPassword(pwd)) {
                setFieldError(passwordEl, 'Hasło zbyt słabe (min. 8 znaków, duża/mała litera i cyfra)');
                passwordEl?.focus?.();
                return;
            }
        }

        const payload = {
            username: usernameEl.value.trim(),
            email: emailEl.value.trim(),
            first_name: firstNameEl.value.trim(),
            last_name: lastNameEl.value.trim(),
            phone: phoneEl.value.trim() || undefined,
            role: roleEl.value,
        };

        try {
            if (isCreate) {
                payload.password = passwordEl.value;
                await usersAPI.create(payload);
            } else {
                const id = parseInt(idEl.value, 10);
                await usersAPI.update(id, payload);
            }

            modal.hide();
            await renderUsers();
        } catch (err) {
            console.error(err);
        }
    };

    modal.show();
}

window.editUser = (id) => openUserModal({ mode: 'edit', userId: id });

window.deactivateUser = async (id) => {
    if (currentUserId !== null && Number(id) === Number(currentUserId)) {
        showToast('Nie możesz dezaktywować aktualnie zalogowanego użytkownika', 'warning');
        return;
    }
    const ok = await confirmDialog({
        title: 'Dezaktywuj użytkownika',
        message: 'Czy na pewno chcesz dezaktywować tego użytkownika?',
        confirmText: 'Dezaktywuj',
        cancelText: 'Anuluj',
        danger: true,
    });
    if (!ok) return;
    try {
        await usersAPI.deactivate(id);
        await renderUsers();
    } catch (err) {
        console.error(err);
    }
};

window.activateUser = async (id) => {
    const ok = await confirmDialog({
        title: 'Aktywuj użytkownika',
        message: 'Czy na pewno chcesz aktywować tego użytkownika?',
        confirmText: 'Aktywuj',
        cancelText: 'Anuluj',
        danger: false,
    });
    if (!ok) return;
    try {
        await usersAPI.update(id, { is_active: true }, { successMessage: 'Użytkownik aktywowany' });
        await renderUsers();
    } catch (err) {
        console.error(err);
    }
};

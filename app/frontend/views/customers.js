/**
 * Customers View - Zarządzanie klientami
 */

import { customersAPI } from '../api.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { openAddressPicker } from '../address_picker.js';
import { validateRequiredFields, requireEmail, setFieldError, wireClearOnInput } from '../forms.js';
import { confirmDialog } from '../confirm.js';

let currentPage = 1;
let currentFilters = {};

export async function renderCustomers(params) {
    const container = document.getElementById('viewContainer');
    
    // Check if editing specific customer
    if (params && params[0]) {
        if (params[0] === 'new') {
            return renderCustomerForm(null);
        } else {
            return renderCustomerForm(parseInt(params[0]));
        }
    }
    
    // Show loading
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-people"></i> Klienci</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        const response = await customersAPI.getAll(currentFilters, currentPage);
        const customers = response.data || [];
        const pagination = response.pagination || { page: 1, pages: 1, total: 0 };
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-people"></i> Klienci</h1>
                    <p class="text-muted mb-0">Zarządzanie bazą klientów</p>
                </div>
                <div>
                    <button class="btn btn-success" onclick="window.location.hash='#/customers/new'">
                        <i class="bi bi-person-plus"></i> Nowy klient
                    </button>
                </div>
            </div>
            
            <!-- Filters -->
            <div class="card mb-4">
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-4">
                            <input type="text" class="form-control" id="searchInput" 
                                   placeholder="Szukaj (nazwa, email, telefon)..."
                                   value="${currentFilters.search || ''}">
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="customerTypeFilter">
                                <option value="">Wszyscy klienci</option>
                                <option value="person" ${currentFilters.customer_type === 'person' ? 'selected' : ''}>Osoba fizyczna</option>
                                <option value="company" ${currentFilters.customer_type === 'company' ? 'selected' : ''}>Firma</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <select class="form-select" id="activeFilter">
                                <option value="">Aktywni i nieaktywni</option>
                                <option value="true" ${currentFilters.is_active === 'true' ? 'selected' : ''}>Tylko aktywni</option>
                                <option value="false" ${currentFilters.is_active === 'false' ? 'selected' : ''}>Tylko nieaktywni</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <button class="btn btn-outline-secondary w-100" id="resetFiltersBtn">
                                <i class="bi bi-x-circle"></i> Wyczyść
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Customers Table -->
            <div class="card">
                <div class="card-body p-0">
                    ${customers.length === 0 ? `
                        <div class="text-center py-5">
                            <i class="bi bi-inbox display-1 text-muted"></i>
                            <p class="text-muted mt-3">Brak klientów</p>
                            <button class="btn btn-success" onclick="window.location.hash='#/customers/new'">
                                <i class="bi bi-person-plus"></i> Dodaj pierwszego klienta
                            </button>
                        </div>
                    ` : `
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Nazwa</th>
                                        <th>Typ</th>
                                        <th>Email</th>
                                        <th>Telefon</th>
                                        <th>NIP</th>
                                        <th>Status</th>
                                        <th>Akcje</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${customers.map(customer => `
                                        <tr>
                                            <td>#${customer.id}</td>
                                            <td>
                                                <strong>${customer.display_name || customer.full_name}</strong>
                                                ${customer.company_name ? `<br><small class="text-muted">${customer.company_name}</small>` : ''}
                                            </td>
                                            <td>
                                                <span class="badge bg-${customer.customer_type === 'company' ? 'primary' : 'secondary'}">
                                                    ${customer.customer_type === 'company' ? 'Firma' : 'Osoba'}
                                                </span>
                                            </td>
                                            <td>${customer.email || '-'}</td>
                                            <td>${customer.phone || '-'}</td>
                                            <td>${customer.nip || '-'}</td>
                                            <td>
                                                <span class="badge bg-${customer.is_active ? 'success' : 'secondary'}">
                                                    ${customer.is_active ? 'Aktywny' : 'Nieaktywny'}
                                                </span>
                                            </td>
                                            <td>
                                                <div class="btn-group btn-group-sm">
                                                    <button class="btn btn-outline-primary" onclick="window.location.hash='#/customers/${customer.id}'" title="Edytuj">
                                                        <i class="bi bi-pencil"></i>
                                                    </button>
                                                    <button class="btn btn-outline-danger" onclick="deleteCustomer(${customer.id})" title="Usuń">
                                                        <i class="bi bi-trash"></i>
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                        
                        <!-- Pagination (footer always visible) -->
                        <div class="card-footer">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="text-muted">
                                    Strona ${pagination.page} z ${pagination.pages} (${pagination.total} klientów)
                                </div>
                                ${pagination.pages > 1 ? `
                                    <nav>
                                        <ul class="pagination mb-0">
                                            <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
                                                <a class="page-link" href="#" onclick="goToPage(${pagination.page - 1}); return false;">Poprzednia</a>
                                            </li>
                                            ${Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                                                const pageNum = i + 1;
                                                return `
                                                    <li class="page-item ${pageNum === pagination.page ? 'active' : ''}">
                                                        <a class="page-link" href="#" onclick="goToPage(${pageNum}); return false;">${pageNum}</a>
                                                    </li>
                                                `;
                                            }).join('')}
                                            <li class="page-item ${pagination.page === pagination.pages ? 'disabled' : ''}">
                                                <a class="page-link" href="#" onclick="goToPage(${pagination.page + 1}); return false;">Następna</a>
                                            </li>
                                        </ul>
                                    </nav>
                                ` : ''}
                            </div>
                        </div>
                    `}
                </div>
            </div>
        `;
        
        // Setup event listeners
        setupCustomersListeners();
        
    } catch (error) {
        console.error('Failed to load customers:', error);
        showToast('Błąd ładowania klientów', 'danger');
    }
}

function setupCustomersListeners() {
    // Search
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentFilters.search = e.target.value;
                currentPage = 1;
                renderCustomers();
            }, 500);
        });
    }
    
    // Filters
    document.getElementById('customerTypeFilter')?.addEventListener('change', (e) => {
        currentFilters.customer_type = e.target.value;
        currentPage = 1;
        renderCustomers();
    });
    
    document.getElementById('activeFilter')?.addEventListener('change', (e) => {
        currentFilters.is_active = e.target.value;
        currentPage = 1;
        renderCustomers();
    });
    
    document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
        currentFilters = {};
        currentPage = 1;
        renderCustomers();
    });
}

// Global functions for inline handlers
window.goToPage = (page) => {
    currentPage = page;
    renderCustomers();
};

window.deleteCustomer = async (id) => {
    const ok = await confirmDialog({
        title: 'Usuń klienta',
        message: 'Czy na pewno chcesz usunąć tego klienta?',
        confirmText: 'Usuń',
        cancelText: 'Anuluj',
        danger: true,
    });
    if (!ok) {
        return;
    }
    
    try {
        await customersAPI.delete(id);
        renderCustomers();
    } catch (error) {
        console.error('Failed to delete customer:', error);
    }
};

async function renderCustomerForm(customerId) {
    const container = document.getElementById('viewContainer');
    const isEdit = customerId !== null;
    
    let customer = null;
    
    if (isEdit) {
        try {
            const response = await customersAPI.getById(customerId);
            customer = response.data;
        } catch (error) {
            showToast('Nie znaleziono klienta', 'danger');
            navigate('/customers');
            return;
        }
    }
    
    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-${isEdit ? 'pencil' : 'person-plus'}"></i> ${isEdit ? 'Edytuj klienta' : 'Nowy klient'}</h1>
            </div>
            <div>
                <button class="btn btn-outline-secondary" onclick="window.location.hash='#/customers'">
                    <i class="bi bi-arrow-left"></i> Powrót
                </button>
            </div>
        </div>
        
        <div class="row">
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-body">
                        <form id="customerForm" novalidate>
                            <!-- Customer Type -->
                            <div class="mb-4">
                                <label class="form-label">Typ klienta *</label>
                                <div class="btn-group w-100" role="group">
                                    <input type="radio" class="btn-check" name="customer_type" id="typePerson" value="person" 
                                           ${!customer || customer.customer_type === 'person' ? 'checked' : ''}>
                                    <label class="btn btn-outline-primary" for="typePerson">
                                        <i class="bi bi-person"></i> Osoba fizyczna
                                    </label>
                                    
                                    <input type="radio" class="btn-check" name="customer_type" id="typeCompany" value="company"
                                           ${customer && customer.customer_type === 'company' ? 'checked' : ''}>
                                    <label class="btn btn-outline-primary" for="typeCompany">
                                        <i class="bi bi-building"></i> Firma
                                    </label>
                                </div>
                            </div>
                            
                            <!-- Person Fields -->
                            <div id="personFields">
                                <div class="row mb-3">
                                    <div class="col-md-6">
                                        <label for="firstName" class="form-label">Imię *</label>
                                        <input type="text" class="form-control" id="firstName" name="first_name" 
                                               value="${customer?.first_name || ''}" required>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="lastName" class="form-label">Nazwisko *</label>
                                        <input type="text" class="form-control" id="lastName" name="last_name"
                                               value="${customer?.last_name || ''}" required>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Company Fields -->
                            <div id="companyFields" class="d-none">
                                <div class="mb-3">
                                    <label for="companyName" class="form-label">Nazwa firmy *</label>
                                    <input type="text" class="form-control" id="companyName" name="company_name"
                                           value="${customer?.company_name || ''}">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="nip" class="form-label">NIP *</label>
                                    <input type="text" class="form-control" id="nip" name="nip"
                                           value="${customer?.nip || ''}" placeholder="1234567890" maxlength="10">
                                    <div class="form-text">10 cyfr bez kresek</div>
                                </div>
                            </div>
                            
                            <!-- Contact -->
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label for="email" class="form-label">Email *</label>
                                    <input type="email" class="form-control" id="email" name="email"
                                           value="${customer?.email || ''}" required>
                                </div>
                                <div class="col-md-6">
                                    <label for="phone" class="form-label">Telefon *</label>
                                    <input type="tel" class="form-control" id="phone" name="phone"
                                           value="${customer?.phone || ''}" required placeholder="+48 123 456 789">
                                </div>
                            </div>
                            
                            <!-- Address -->
                            <div class="mb-3">
                                <label for="street" class="form-label">Ulica i numer</label>
                                <div class="input-group">
                                    <input type="text" class="form-control" id="street" name="street"
                                           value="${customer?.street || ''}">
                                    <button class="btn btn-outline-secondary" type="button" id="pickCustomerAddressBtn" title="Wybierz z Google Maps">
                                        <i class="bi bi-geo-alt"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="row mb-3">
                                <div class="col-md-4">
                                    <label for="postalCode" class="form-label">Kod pocztowy</label>
                                    <input type="text" class="form-control" id="postalCode" name="postal_code"
                                           value="${customer?.postal_code || ''}" placeholder="00-000">
                                </div>
                                <div class="col-md-8">
                                    <label for="city" class="form-label">Miasto</label>
                                    <input type="text" class="form-control" id="city" name="city"
                                           value="${customer?.city || ''}">
                                </div>
                            </div>
                            
                            <!-- Notes -->
                            <div class="mb-3">
                                <label for="notes" class="form-label">Notatki</label>
                                <textarea class="form-control" id="notes" name="notes" rows="3">${customer?.notes || ''}</textarea>
                            </div>
                            
                            <!-- Active Status -->
                            <div class="form-check mb-4">
                                <input class="form-check-input" type="checkbox" id="isActive" name="is_active"
                                       ${!customer || customer.is_active ? 'checked' : ''}>
                                <label class="form-check-label" for="isActive">
                                    Klient aktywny
                                </label>
                            </div>
                            
                            <!-- Submit -->
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-success">
                                    <i class="bi bi-check-lg"></i> ${isEdit ? 'Zapisz zmiany' : 'Utwórz klienta'}
                                </button>
                                <button type="button" class="btn btn-outline-secondary" onclick="window.location.hash='#/customers'">
                                    Anuluj
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Setup form handlers
    setupCustomerFormListeners(customerId);
}

function setupCustomerFormListeners(customerId) {
    const form = document.getElementById('customerForm');
    const typeInputs = form.querySelectorAll('input[name="customer_type"]');
    const personFields = document.getElementById('personFields');
    const companyFields = document.getElementById('companyFields');
    
    // Toggle fields based on customer type
    function updateFieldsVisibility() {
        const selectedType = form.querySelector('input[name="customer_type"]:checked').value;
        
        if (selectedType === 'person') {
            personFields.classList.remove('d-none');
            companyFields.classList.add('d-none');
            companyFields.querySelectorAll('input').forEach(input => input.required = false);
            personFields.querySelectorAll('input').forEach(input => {
                if (input.id === 'firstName' || input.id === 'lastName') {
                    input.required = true;
                }
            });
        } else {
            personFields.classList.add('d-none');
            companyFields.classList.remove('d-none');
            personFields.querySelectorAll('input').forEach(input => input.required = false);
            companyFields.querySelectorAll('input').forEach(input => {
                if (input.id === 'companyName' || input.id === 'nip') {
                    input.required = true;
                }
            });
        }
    }
    
    typeInputs.forEach(input => {
        input.addEventListener('change', updateFieldsVisibility);
    });
    
    // Initial visibility
    updateFieldsVisibility();

    // Clear inline errors while typing
    wireClearOnInput(form);

    // Address picker
    document.getElementById('pickCustomerAddressBtn')?.addEventListener('click', () => {
        openAddressPicker({
            title: 'Wybierz adres klienta',
            initialQuery: document.getElementById('street')?.value || '',
            onSelect: (details) => {
                if (details?.street) document.getElementById('street').value = details.street;
                if (details?.postal_code) document.getElementById('postalCode').value = details.postal_code;
                if (details?.city) document.getElementById('city').value = details.city;
            }
        });
    });
    
    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!validateRequiredFields(form)) {
            return;
        }

        const emailEl = document.getElementById('email');
        if (!requireEmail(emailEl)) {
            return;
        }

        const selectedType = form.querySelector('input[name="customer_type"]:checked')?.value;
        if (selectedType === 'company') {
            const nipEl = document.getElementById('nip');
            const nip = (nipEl?.value || '').trim();
            if (nip && !/^\d{10}$/.test(nip)) {
                setFieldError(nipEl, 'NIP musi mieć 10 cyfr');
                nipEl?.focus?.();
                return;
            }
        }
        
        const formData = new FormData(form);
        const data = {
            customer_type: formData.get('customer_type'),
            email: formData.get('email'),
            phone: formData.get('phone'),
            street: formData.get('street') || null,
            postal_code: formData.get('postal_code') || null,
            city: formData.get('city') || null,
            notes: formData.get('notes') || null,
            is_active: formData.get('is_active') === 'on',
        };
        
        if (data.customer_type === 'person') {
            data.first_name = formData.get('first_name');
            data.last_name = formData.get('last_name');
        } else {
            data.company_name = formData.get('company_name');
            data.nip = formData.get('nip');
        }
        
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Zapisywanie...';
        
        try {
            if (customerId) {
                await customersAPI.update(customerId, data);
            } else {
                await customersAPI.create(data);
            }
            
            navigate('/customers');
            
        } catch (error) {
            console.error('Failed to save customer:', error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<i class="bi bi-check-lg"></i> ${customerId ? 'Zapisz zmiany' : 'Utwórz klienta'}`;
        }
    });
}

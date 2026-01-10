/**
 * API Client - Wrapper for Fetch API with JWT authentication
 */

import { showToast } from './toasts.js';
import { showLoading, hideLoading } from './app.js';

const API_BASE_URL = '/api';
const AUTH_STORAGE_KEY = 'ecoshot_auth';

let loginRedirectTimer = null;

export function scheduleLoginRedirect(delayMs = 2500) {
    // Avoid redirect loops if already on login
    const currentHash = window.location.hash || '';
    if (currentHash.startsWith('#/login')) {
        return;
    }

    if (loginRedirectTimer) {
        return;
    }

    loginRedirectTimer = window.setTimeout(() => {
        loginRedirectTimer = null;
        window.location.hash = '#/login';
    }, delayMs);
}

// Storage helpers
export function storeAuth(authData) {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authData));
}

export function getStoredAuth() {
    const data = localStorage.getItem(AUTH_STORAGE_KEY);
    return data ? JSON.parse(data) : null;
}

export function clearAuth() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
}

// File download helper (e.g. PDFs). Links can't attach Authorization header.
export async function apiDownload(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const auth = getStoredAuth();

    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

    const config = {
        method: options.method || 'GET',
        headers: {
            ...options.headers,
        },
    };

    if (options.signal) {
        config.signal = options.signal;
    }

    if (auth && auth.access_token && !options.skipAuth) {
        config.headers['Authorization'] = `Bearer ${auth.access_token}`;
    }

    // Allow POST/PUT/PATCH downloads (e.g. generating PDFs).
    if (options.body && ['POST', 'PUT', 'PATCH'].includes(config.method)) {
        if (!isFormData && !config.headers['Content-Type']) {
            config.headers['Content-Type'] = 'application/json';
        }
        config.body = isFormData ? options.body : JSON.stringify(options.body);
    }

    if (options.showLoading) {
        showLoading();
    }

    try {
        const response = await fetch(url, config);

        if ((response.status === 401 || response.status === 422) && !options.skipAuth) {
            clearAuth();
            showToast('Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.', 'warning');
            scheduleLoginRedirect(2500);
            return null;
        }

        if (!response.ok) {
            // Try to parse JSON error; fall back to status.
            let errorMessage = `Błąd ${response.status}`;
            try {
                const data = await response.json();
                errorMessage = data?.error || data?.message || errorMessage;
            } catch (_) {
                // ignore
            }

            if (options.showErrors !== false) {
                showToast(errorMessage, 'danger');
            }

            const apiError = new Error(errorMessage);
            apiError.isApiError = true;
            apiError.status = response.status;
            throw apiError;
        }

        const blob = await response.blob();
        const contentDisposition = response.headers.get('Content-Disposition') || '';

        // Best-effort filename parsing.
        let filename = null;
        const match = contentDisposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
        if (match) {
            filename = decodeURIComponent(match[1] || match[2]);
        }

        return { blob, filename };

    } catch (error) {
        console.error('API Download failed:', error);

        if (options.showErrors !== false && !error?.isApiError) {
            showToast('Błąd połączenia z serwerem', 'danger');
        }

        throw error;
    } finally {
        if (options.showLoading) {
            hideLoading();
        }
    }
}

// HTTP Methods
export async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const auth = getStoredAuth();

    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
    
    const config = {
        method: options.method || 'GET',
        headers: {
            ...options.headers,
        },
    };

    if (options.signal) {
        config.signal = options.signal;
    }

    // For JSON requests set Content-Type; for FormData let the browser set boundary.
    if (!isFormData && !config.headers['Content-Type']) {
        config.headers['Content-Type'] = 'application/json';
    }
    
    // Add JWT token if authenticated
    if (auth && auth.access_token && !options.skipAuth) {
        config.headers['Authorization'] = `Bearer ${auth.access_token}`;
    }
    
    // Add body for POST/PUT/PATCH
    if (options.body && ['POST', 'PUT', 'PATCH'].includes(config.method)) {
        config.body = isFormData ? options.body : JSON.stringify(options.body);
    }
    
    // Show loading indicator if requested
    if (options.showLoading) {
        showLoading();
    }
    
    try {
        const response = await fetch(url, config);
        
        // Handle auth failures (401/422) - expired/invalid token
        if ((response.status === 401 || response.status === 422) && !options.skipAuth) {
            clearAuth();
            showToast('Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.', 'warning');
            scheduleLoginRedirect(2500);
            return null;
        }
        
        // Parse JSON response
        const data = await response.json();
        
        // Handle error responses
        if (!response.ok) {
            const errorMessage = data.error || data.message || `Błąd ${response.status}`;

            if (options.showErrors !== false) {
                showToast(errorMessage, 'danger');
            }

            // Mark as an API (HTTP) error so the catch block won't show a fake
            // "connection error" toast.
            const apiError = new Error(errorMessage);
            apiError.isApiError = true;
            apiError.status = response.status;
            apiError.payload = data;
            throw apiError;
        }
        
        // Show success message if provided
        if (options.successMessage) {
            showToast(options.successMessage, 'success');
        }
        
        return data;
        
    } catch (error) {
        console.error('API Request failed:', error);

        // Only show connection toast for genuine network/parsing failures.
        if (options.showErrors !== false && !error?.isApiError) {
            showToast('Błąd połączenia z serwerem', 'danger');
        }
        
        throw error;
        
    } finally {
        if (options.showLoading) {
            hideLoading();
        }
    }
}

// Convenience methods
export const api = {
    get: (endpoint, options = {}) => apiRequest(endpoint, { ...options, method: 'GET' }),
    post: (endpoint, body, options = {}) => apiRequest(endpoint, { ...options, method: 'POST', body }),
    put: (endpoint, body, options = {}) => apiRequest(endpoint, { ...options, method: 'PUT', body }),
    patch: (endpoint, body, options = {}) => apiRequest(endpoint, { ...options, method: 'PATCH', body }),
    delete: (endpoint, options = {}) => apiRequest(endpoint, { ...options, method: 'DELETE' }),
};

// Authentication API
export async function login(username, password) {
    const data = await apiRequest('/auth/login', {
        method: 'POST',
        body: { username, password },
        skipAuth: true,
        showLoading: true,
        showErrors: false,
    });
    
    if (data && data.success) {
        storeAuth(data.data);
        return data.data;
    }
    
    throw new Error('Nieprawidłowy login lub hasło');
}

export async function getCurrentUser() {
    const data = await apiRequest('/auth/me', {
        showErrors: false,
    });
    
    return data?.data || null;
}

export const authAPI = {
    changePassword: (old_password, new_password, options = {}) => api.post(
        '/auth/change-password',
        { old_password, new_password },
        { successMessage: 'Hasło zmienione', ...options }
    ),
};

export const usersAPI = {
    getAll: (filters = {}) => api.get(`/auth/users?${new URLSearchParams({ ...filters })}`),
    getById: (id) => api.get(`/auth/users/${id}`),
    create: (data, options = {}) => api.post('/auth/users', data, { successMessage: 'Użytkownik utworzony', ...options }),
    update: (id, data, options = {}) => api.put(`/auth/users/${id}`, data, { successMessage: 'Użytkownik zaktualizowany', ...options }),
    deactivate: (id, options = {}) => api.delete(`/auth/users/${id}`, { successMessage: 'Użytkownik dezaktywowany', ...options }),
};

export const settingsAPI = {
    get: (options = {}) => api.get('/settings', { ...options }),
    update: (data, options = {}) => api.put('/settings', data, { successMessage: 'Ustawienia zapisane', ...options }),
    getBrandingPublic: () => apiRequest('/settings/branding', { skipAuth: true, showErrors: false }),
    uploadLogo: (file) => {
        const formData = new FormData();
        formData.append('logo', file);
        return apiRequest('/settings/branding/logo', { method: 'POST', body: formData, showErrors: true });
    },
    deleteLogo: () => apiRequest('/settings/branding/logo', { method: 'DELETE', showErrors: true }),

    uploadGalleryLogo: (file) => {
        const formData = new FormData();
        formData.append('logo', file);
        return apiRequest('/settings/branding/gallery-logo', { method: 'POST', body: formData, showErrors: true });
    },
    deleteGalleryLogo: () => apiRequest('/settings/branding/gallery-logo', { method: 'DELETE', showErrors: true }),

    // Maintenance / backups (admin)
    downloadDbBackup: (options = {}) => apiDownload('/settings/maintenance/backup/db', { showLoading: true, ...options }),
    downloadFullBackup: (options = {}) => apiDownload('/settings/maintenance/backup/full', { showLoading: true, ...options }),

    listFullBackups: (options = {}) => api.get('/settings/maintenance/backups/full', { showErrors: true, ...options }),
    createFullBackupPersisted: (options = {}) => apiRequest('/settings/maintenance/backups/full', { method: 'POST', body: {}, showErrors: true, ...options }),
    downloadStoredFullBackup: (name, options = {}) => apiDownload(`/settings/maintenance/backups/full/${encodeURIComponent(name)}`, { showLoading: true, ...options }),
    restoreStoredFullBackup: (name, confirm, options = {}) => api.post(
        `/settings/maintenance/backups/full/${encodeURIComponent(name)}/restore`,
        { confirm: confirm || '' },
        { showErrors: true, ...options }
    ),
    restoreDbBackup: (file, confirm, options = {}) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('confirm', confirm || '');
        return apiRequest('/settings/maintenance/restore/db', { method: 'POST', body: formData, showErrors: true, ...options });
    },
    purgeData: (payload, options = {}) => api.post('/settings/maintenance/purge', payload, { showErrors: true, ...options }),
};

export const promotionsAPI = {
    getAll: (filters = {}, options = {}) => api.get(`/promotions?${new URLSearchParams({ ...filters })}`, options),
    create: (data, options = {}) => api.post('/promotions', data, { successMessage: 'Promocja utworzona', ...options }),
    update: (id, data, options = {}) => api.put(`/promotions/${id}`, data, { successMessage: 'Promocja zaktualizowana', ...options }),
    delete: (id, options = {}) => api.delete(`/promotions/${id}`, { successMessage: 'Promocja usunięta', ...options }),
    uploadVoucherTemplate: (id, formData, options = {}) => apiRequest(
        `/promotions/${id}/voucher-template`,
        { method: 'POST', body: formData, successMessage: 'Szablon vouchera zapisany', ...options }
    ),
};

export const vouchersAPI = {
    getAll: (filters = {}, page = 1, per_page = 50, options = {}) => api.get(`/vouchers?${new URLSearchParams({ ...filters, page, per_page })}`, options),
    generatePdf: (promotion_id, count, options = {}) => apiDownload(
        '/vouchers/generate',
        { method: 'POST', body: { promotion_id, count }, showLoading: true, ...options }
    ),
    downloadSinglePdf: (voucherId, options = {}) => apiDownload(`/vouchers/${encodeURIComponent(voucherId)}/pdf`, { showLoading: true, ...options }),
    downloadSinglePng: (voucherId, options = {}) => apiDownload(`/vouchers/${encodeURIComponent(voucherId)}/png`, { showLoading: true, ...options }),
    validate: (code, { job_id = null, total = null } = {}, options = {}) => {
        const params = new URLSearchParams();
        if (code) params.set('code', code);
        if (job_id) params.set('job_id', String(job_id));
        if (total !== null && total !== undefined) params.set('total', String(total));
        return api.get(`/vouchers/validate?${params.toString()}`, options);
    },
};

// Resource API helpers
export const customersAPI = {
    getAll: (filters = {}, page = 1) => api.get(`/customers?${new URLSearchParams({ ...filters, page })}`),
    getById: (id) => api.get(`/customers/${id}`),
    create: (data) => api.post('/customers', data, { successMessage: 'Klient utworzony' }),
    update: (id, data) => api.put(`/customers/${id}`, data, { successMessage: 'Klient zaktualizowany' }),
    delete: (id) => api.delete(`/customers/${id}`, { successMessage: 'Klient usunięty' }),
};

export const jobsAPI = {
    getAll: (filters = {}, page = 1) => api.get(`/jobs?${new URLSearchParams({ ...filters, page })}`),
    getById: (id) => api.get(`/jobs/${id}`),
    create: (data) => api.post('/jobs', data, { successMessage: 'Zlecenie utworzone' }),
    update: (id, data) => api.put(`/jobs/${id}`, data, { successMessage: 'Zlecenie zaktualizowane' }),
    updateStatus: (id, status) => api.put(`/jobs/${id}/status`, { status }, { successMessage: 'Status zmieniony' }),
    delete: (id) => api.delete(`/jobs/${id}`, { successMessage: 'Zlecenie anulowane' }),
    getOffers: ({ active_only = true } = {}) => api.get(`/jobs/offers?${new URLSearchParams({ active_only: String(Boolean(active_only)) })}`),
    createOffer: (data, options = {}) => api.post('/jobs/offers', data, { successMessage: 'Oferta utworzona', ...options }),
    updateOffer: (id, data, options = {}) => api.put(`/jobs/offers/${id}`, data, { successMessage: 'Oferta zaktualizowana', ...options }),
    deleteOffer: (id, options = {}) => api.delete(`/jobs/offers/${id}`, { successMessage: 'Oferta usunięta', ...options }),
    createOfferAddon: (data, options = {}) => api.post('/jobs/offers/addons', data, { successMessage: 'Dodatek utworzony', ...options }),
    updateOfferAddon: (id, data, options = {}) => api.put(`/jobs/offers/addons/${id}`, data, { successMessage: 'Dodatek zaktualizowany', ...options }),
    deleteOfferAddon: (id, options = {}) => api.delete(`/jobs/offers/addons/${id}`, { successMessage: 'Dodatek usunięty', ...options }),
    getCalendar: (fromIso, toIso) => api.get(`/jobs/calendar?${new URLSearchParams({ from: fromIso, to: toIso })}`),
};

export const contractsAPI = {
    getAll: (filters = {}, page = 1, per_page = 50, options = {}) => api.get(`/contracts?${new URLSearchParams({ ...filters, page, per_page })}`, options),
    getById: (id, options = {}) => api.get(`/contracts/${id}`, options),
    getByJobId: (jobId, options = {}) => api.get(`/contracts/job/${jobId}`, options),
    create: (data, options = {}) => api.post('/contracts', data, { successMessage: 'Umowa utworzona', ...options }),
    update: (id, data, options = {}) => api.put(`/contracts/${id}`, data, { successMessage: 'Umowa zaktualizowana', ...options }),
    send: (id, options = {}) => api.post(`/contracts/${id}/send`, {}, { successMessage: 'Umowa wysłana do klienta', ...options }),
    updateStatus: (id, status, options = {}) => api.put(
        `/contracts/${id}/status`,
        { status },
        {
            successMessage: status === 'signed' ? 'Umowa oznaczona jako podpisana' : 'Status zaktualizowany',
            ...options,
        }
    ),
    uploadSignedScan: (id, formData, options = {}) => apiRequest(`/contracts/${id}/signed-scan`, { method: 'POST', body: formData, successMessage: options.successMessage ?? 'Skan zapisany', ...options }),
};

export const invoicesAPI = {
    getAll: (filters = {}, page = 1) => api.get(`/invoices?${new URLSearchParams({ ...filters, page })}`),
    getById: (id) => api.get(`/invoices/${id}`),
    create: (data, options = {}) => api.post('/invoices', data, { successMessage: 'Faktura utworzona', ...options }),
    send: (id, options = {}) => api.post(`/invoices/${id}/send`, {}, { successMessage: 'Faktura wysłana', ...options }),
    delete: (id, options = {}) => api.delete(`/invoices/${id}`, { successMessage: 'Faktura usunięta', ...options }),
};

export const paymentsAPI = {
    getAll: (filters = {}, page = 1, per_page = 50) => api.get(`/payments?${new URLSearchParams({ ...filters, page, per_page })}`),
    getById: (id) => api.get(`/payments/${id}`),
    create: (data, options = {}) => api.post('/payments', data, { successMessage: 'Płatność utworzona', ...options }),
    complete: (id, transaction_id, options = {}) => api.post(`/payments/${id}/complete`, { transaction_id }, { successMessage: 'Płatność potwierdzona', ...options }),
    refund: (id, reason, options = {}) => api.post(`/payments/${id}/refund`, { reason }, { successMessage: 'Zwrot zrealizowany', ...options }),
    delete: (id, options = {}) => api.delete(`/payments/${id}`, { successMessage: 'Płatność usunięta', ...options }),
    payuCreateOrder: (data, options = {}) => api.post('/payments/payu/orders', data, { successMessage: 'Utworzono płatność PayU', ...options }),
};

export const galleriesAPI = {
    getAll: (filters = {}, page = 1, per_page = 25, options = {}) => api.get(`/galleries?${new URLSearchParams({ ...filters, page, per_page })}`, options),
    getById: (id) => api.get(`/galleries/${id}`),
    create: (data, options = {}) => api.post('/galleries', data, { successMessage: 'Galeria utworzona', ...options }),
    update: (id, data, options = {}) => api.put(`/galleries/${id}`, data, { successMessage: 'Galeria zaktualizowana', ...options }),
    publish: (id, options = {}) => api.post(`/galleries/${id}/publish`, {}, { successMessage: 'Galeria opublikowana', ...options }),
    send: (id, options = {}) => api.post(`/galleries/${id}/send`, {}, { successMessage: 'Link wysłany do klienta', ...options }),
    sendAccess: (id, options = {}) => api.post(`/galleries/${id}/send-access`, {}, options),
    patchType: (id, gallery_type, options = {}) => api.patch(`/galleries/${id}/type`, { gallery_type }, options),
    patchSettings: (id, settings, options = {}) => api.patch(`/galleries/${id}/settings`, settings, options),
};

export const consentsAPI = {
    getAll: (filters = {}, page = 1, per_page = 50, options = {}) => api.get(`/consents?${new URLSearchParams({ ...filters, page, per_page })}`, options),
    getById: (id, options = {}) => api.get(`/consents/${id}`, options),
    getByJobId: (jobId, options = {}) => api.get(`/consents/job/${jobId}`, options),
    getTemplate: (consentType, paramsOrOptions = {}, maybeOptions = {}) => {
        // Back-compat: previously signature was (consentType, options).
        const looksLikeOptions = (obj) => {
            if (!obj || typeof obj !== 'object') return false;
            return (
                'showErrors' in obj
                || 'showLoading' in obj
                || 'skipAuth' in obj
                || 'successMessage' in obj
                || 'headers' in obj
                || 'signal' in obj
            );
        };

        const params = looksLikeOptions(paramsOrOptions) ? {} : (paramsOrOptions || {});
        const options = looksLikeOptions(paramsOrOptions) ? (paramsOrOptions || {}) : (maybeOptions || {});

        const qs = new URLSearchParams({ ...params }).toString();
        const endpoint = `/consents/templates/${encodeURIComponent(consentType)}${qs ? `?${qs}` : ''}`;
        return api.get(endpoint, options);
    },
    create: (data, options = {}) => api.post('/consents', data, { successMessage: 'Zgoda utworzona', ...options }),
    send: (id, options = {}) => api.post(`/consents/${id}/send`, {}, { successMessage: 'Zgoda wysłana', ...options }),
    uploadSignedScan: (id, formData, options = {}) => apiRequest(`/consents/${id}/signed-scan`, { method: 'POST', body: formData, successMessage: 'Skan podpisanej zgody zapisany', ...options }),
};

export const financeAPI = {
    // Reports page
    getStats: () => api.get('/finance/stats'),
    getOutstanding: () => api.get('/finance/outstanding'),
    getRevenue: ({ period } = {}) => api.get(`/finance/revenue?${new URLSearchParams({ period: period || 'month' })}`),

    getRevenueSummary: (startDate, endDate) => api.get(`/finance/revenue/summary?start_date=${startDate}&end_date=${endDate}`),
    getMonthlyRevenue: (year) => api.get(`/finance/revenue/monthly?year=${year}`),
    getDashboardStats: () => api.get('/finance/dashboard'),
};

export const photosAPI = {
    getAll: (filters = {}) => api.get(`/photos?${new URLSearchParams(filters)}`),
    getById: (id) => api.get(`/photos/${id}`),
    upload: (formData) => apiRequest('/photos/upload', { method: 'POST', body: formData, showErrors: true }),
    update: (id, data) => api.put(`/photos/${id}`, data, { successMessage: 'Zdjęcie zaktualizowane' }),
    toggleSelection: (id, is_selected) => api.post(`/photos/${id}/toggle-selection`, { is_selected }),
    batchUpdate: (photo_ids, action) => api.put('/photos/batch-update', { photo_ids, action }),
    reorder: (photo_orders) => api.put('/photos/reorder', { photo_orders }),
    delete: (id) => api.delete(`/photos/${id}`),
    downloadUrl: (id, version = 'watermarked') => `${API_BASE_URL}/photos/${id}/download?version=${encodeURIComponent(version)}`,
};

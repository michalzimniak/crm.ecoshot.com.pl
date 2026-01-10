/**
 * Toast Notifications - Bootstrap 5 Toasts
 */

let toastCounter = 0;

// Dedupe / rate-limit repeated toasts (e.g. many parallel API calls failing).
const activeToasts = new Map(); // key -> { element, toast }
const lastShownAt = new Map(); // key -> timestamp (ms)

function toastKey(message, type) {
    const msg = String(message ?? '');

    // Collapse common "many parallel loads failed" messages into one.
    // We keep the original message in the UI; this only affects dedupe behavior.
    let keyMessage = msg;
    if (type === 'danger' && msg.startsWith('Błąd ładowania ')) {
        keyMessage = 'Błąd ładowania danych';
    }

    return `${type}::${keyMessage}`;
}

function shouldDedupe(key, ttlMs) {
    const now = Date.now();

    // If an identical toast is already visible, don't duplicate it.
    if (activeToasts.has(key)) return true;

    const last = lastShownAt.get(key);
    if (last && now - last < ttlMs) return true;

    lastShownAt.set(key, now);
    return false;
}

export function showToast(message, type = 'info', duration = 5000) {
    const key = toastKey(message, type);

    // Default TTL: suppress repeats for a short window.
    // For connection errors we suppress longer to avoid spam.
    const msg = String(message ?? '');
    const ttl = (type === 'danger' && msg.includes('Błąd połączenia z serwerem'))
        ? 10000
        : (type === 'danger' && msg.startsWith('Błąd ładowania '))
            ? 6000
            : 2500;
    if (shouldDedupe(key, ttl)) {
        return;
    }

    const toastId = `toast-${++toastCounter}`;
    const container = document.getElementById('toastContainer');
    
    if (!container) {
        console.error('Toast container not found');
        return;
    }
    
    // Map types to Bootstrap variants
    const variants = {
        success: { icon: 'check-circle-fill', class: 'text-success', title: 'Sukces' },
        danger: { icon: 'exclamation-triangle-fill', class: 'text-danger', title: 'Błąd' },
        warning: { icon: 'exclamation-circle-fill', class: 'text-warning', title: 'Ostrzeżenie' },
        info: { icon: 'info-circle-fill', class: 'text-info', title: 'Informacja' },
    };
    
    const variant = variants[type] || variants.info;
    
    // Create toast element
    const toastHTML = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="bi bi-${variant.icon} ${variant.class} me-2"></i>
                <strong class="me-auto">${variant.title}</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Zamknij"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // Add to container
    container.insertAdjacentHTML('beforeend', toastHTML);
    
    // Initialize and show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: duration,
    });
    
    toast.show();

    // Track active toast to dedupe while visible.
    activeToasts.set(key, { element: toastElement, toast });
    
    // Remove element after hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        activeToasts.delete(key);
        toastElement.remove();
    });
}

export function showSuccess(message) {
    showToast(message, 'success');
}

export function showError(message) {
    showToast(message, 'danger');
}

export function showWarning(message) {
    showToast(message, 'warning');
}

export function showInfo(message) {
    showToast(message, 'info');
}

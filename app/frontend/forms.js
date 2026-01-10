/**
 * Lightweight form validation helpers (Bootstrap 5 friendly)
 */

export function clearFieldError(inputEl) {
    if (!inputEl) return;
    inputEl.classList.remove('is-invalid');

    const feedback = findInvalidFeedback(inputEl);
    if (feedback) feedback.textContent = '';
}

export function setFieldError(inputEl, message) {
    if (!inputEl) return;
    inputEl.classList.add('is-invalid');

    const feedback = ensureInvalidFeedback(inputEl);
    if (feedback) feedback.textContent = message || '';
}

export function clearFormErrors(formEl) {
    if (!formEl) return;
    formEl.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    formEl.querySelectorAll('.invalid-feedback').forEach(el => { el.textContent = ''; });
}

export function wireClearOnInput(formEl) {
    if (!formEl) return;
    formEl.addEventListener('input', (e) => {
        const target = e.target;
        if (target && (target.matches('input') || target.matches('textarea') || target.matches('select'))) {
            clearFieldError(target);
        }
    });
    formEl.addEventListener('change', (e) => {
        const target = e.target;
        if (target && target.matches('select')) {
            clearFieldError(target);
        }
    });
}

export function requireValue(inputEl, message) {
    const value = (inputEl?.value ?? '').toString().trim();
    if (!value) {
        setFieldError(inputEl, message);
        return false;
    }
    clearFieldError(inputEl);
    return true;
}

export function requireEmail(inputEl, message = 'Wpisz poprawny email') {
    const value = (inputEl?.value ?? '').toString().trim();
    if (!value) {
        setFieldError(inputEl, 'Wpisz email');
        return false;
    }
    // Simple, pragmatic check (not RFC-perfect).
    const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    if (!ok) {
        setFieldError(inputEl, message);
        return false;
    }
    clearFieldError(inputEl);
    return true;
}

export function requireNumberMin(inputEl, minValue, message) {
    const raw = (inputEl?.value ?? '').toString().trim();
    const num = Number(raw);
    if (!raw || !Number.isFinite(num) || num < minValue) {
        setFieldError(inputEl, message || `Wpisz liczbę ≥ ${minValue}`);
        return false;
    }
    clearFieldError(inputEl);
    return true;
}

export function validateRequiredFields(formEl, message = 'To pole jest wymagane') {
    if (!formEl) return true;

    clearFormErrors(formEl);

    // Handle radio groups: group by name.
    const requiredRadios = Array.from(formEl.querySelectorAll('input[type="radio"][required]'))
        .filter(r => !r.disabled && isElementVisible(r));
    const radioNames = new Set(requiredRadios.map(r => r.name).filter(Boolean));
    for (const name of radioNames) {
        const group = Array.from(formEl.querySelectorAll(`input[type="radio"][name="${cssEscape(name)}"]`))
            .filter(r => !r.disabled && isElementVisible(r));
        if (group.length && !group.some(r => r.checked)) {
            // Mark the first radio in the group.
            setFieldError(group[0], message);
        }
    }

    const requiredFields = Array.from(formEl.querySelectorAll('input[required], textarea[required], select[required]'))
        .filter(el => !el.disabled && isElementVisible(el));

    for (const el of requiredFields) {
        // Skip radios here (handled above)
        if (el.matches('input[type="radio"]')) continue;

        const value = (el.value ?? '').toString().trim();
        if (!value) {
            setFieldError(el, message);
        }
    }

    const firstInvalid = formEl.querySelector('.is-invalid');
    if (firstInvalid) {
        firstInvalid.focus?.();
        return false;
    }

    return true;
}

function ensureInvalidFeedback(inputEl) {
    // Try to find existing feedback first.
    const existing = findInvalidFeedback(inputEl);
    if (existing) return existing;

    // Create missing feedback in the best spot.
    const feedback = document.createElement('div');
    feedback.className = 'invalid-feedback';
    feedback.textContent = '';

    const inputGroup = inputEl.closest('.input-group');
    if (inputGroup && inputGroup.parentElement) {
        inputGroup.insertAdjacentElement('afterend', feedback);
        return feedback;
    }

    inputEl.insertAdjacentElement('afterend', feedback);
    return feedback;
}

function findInvalidFeedback(inputEl) {
    // Common patterns:
    // - input-group: feedback placed as sibling after .input-group
    // - normal: feedback placed right after input
    // We search within the nearest container for the first .invalid-feedback.
    const container = inputEl.closest('.mb-3, .mb-4, .col, .col-12, .col-md-6, .col-md-4, .row') || inputEl.parentElement;
    if (!container) return null;

    // Prefer feedback that is the next sibling of input OR within same field block.
    const directSibling = inputEl.nextElementSibling;
    if (directSibling && directSibling.classList?.contains('invalid-feedback')) return directSibling;

    const inGroup = container.querySelector('.invalid-feedback');
    return inGroup || null;
}

function isElementVisible(el) {
    // Skip elements that are not displayed (e.g. hidden rows in modals).
    if (!el) return false;
    if (el.offsetParent === null) return false;
    return true;
}

function cssEscape(value) {
    // Minimal escape for attribute selectors.
    return String(value).replaceAll('\\', '\\\\').replaceAll('"', '\\"');
}

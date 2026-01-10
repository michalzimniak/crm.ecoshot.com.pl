/**
 * Bootstrap confirm modal helper (replaces native window.confirm).
 *
 * Usage:
 *   const ok = await confirmDialog({ title: 'Potwierdź', message: 'Na pewno?', danger: true });
 */

let modalEl = null;
let modalInstance = null;
let resolveCurrent = null;

function ensureModal() {
    if (modalEl && modalInstance) return;

    modalEl = document.createElement('div');
    modalEl.className = 'modal fade';
    modalEl.id = 'appConfirmModal';
    modalEl.tabIndex = -1;
    modalEl.setAttribute('aria-hidden', 'true');

    modalEl.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="appConfirmModalTitle">Potwierdź</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" id="appConfirmModalBody"></div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal" id="appConfirmCancelBtn">Anuluj</button>
                    <button type="button" class="btn btn-danger" id="appConfirmOkBtn">OK</button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modalEl);
    modalInstance = new bootstrap.Modal(modalEl);

    const cancelBtn = modalEl.querySelector('#appConfirmCancelBtn');
    const okBtn = modalEl.querySelector('#appConfirmOkBtn');

    cancelBtn.addEventListener('click', () => finish(false));
    okBtn.addEventListener('click', () => {
        // Resolve first, then hide. The hidden handler won't fire because resolveCurrent is cleared.
        finish(true);
        try {
            modalInstance.hide();
        } catch (_) {
            // ignore
        }
    });

    // If user closes via X / backdrop / escape -> treat as cancel.
    modalEl.addEventListener('hidden.bs.modal', () => {
        if (resolveCurrent) {
            finish(false);
        }
    });
}

function finish(result) {
    if (!resolveCurrent) return;
    const resolve = resolveCurrent;
    resolveCurrent = null;
    resolve(Boolean(result));
}

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

/**
 * @param {Object} opts
 * @param {string} [opts.title]
 * @param {string} [opts.message] - plain text (newlines supported)
 * @param {string} [opts.confirmText]
 * @param {string} [opts.cancelText]
 * @param {boolean} [opts.danger] - red confirm button
 */
export function confirmDialog(opts = {}) {
    ensureModal();

    const title = opts.title || 'Potwierdź';
    const message = opts.message || '';
    const confirmText = opts.confirmText || 'OK';
    const cancelText = opts.cancelText || 'Anuluj';
    const danger = opts.danger !== false;

    const titleEl = modalEl.querySelector('#appConfirmModalTitle');
    const bodyEl = modalEl.querySelector('#appConfirmModalBody');
    const cancelBtn = modalEl.querySelector('#appConfirmCancelBtn');
    const okBtn = modalEl.querySelector('#appConfirmOkBtn');

    titleEl.textContent = title;
    bodyEl.innerHTML = `<div style="white-space: pre-line">${escapeHtml(message)}</div>`;

    cancelBtn.textContent = cancelText;
    okBtn.textContent = confirmText;

    okBtn.classList.toggle('btn-danger', Boolean(danger));
    okBtn.classList.toggle('btn-success', !danger);

    return new Promise((resolve) => {
        resolveCurrent = resolve;
        modalInstance.show();
    });
}

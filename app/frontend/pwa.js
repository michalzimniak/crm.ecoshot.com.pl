export function initPwa() {
    if (!('serviceWorker' in navigator)) return;

    // Register after load to avoid blocking first paint.
    window.addEventListener('load', async () => {
        try {
            await navigator.serviceWorker.register('/sw.js', { scope: '/' });
        } catch (err) {
            // Silent best-effort; PWA is optional.
            console.warn('Service worker registration failed:', err);
        }
    });

    // Setup banner handlers early so we can capture beforeinstallprompt,
    // but don't show the banner until the authenticated app UI is visible.
    initInstallBanner({ allowShow: false });
}

// Call this after login / once the main app UI is visible.
export function enablePwaInstallBanner() {
    _allowBannerShow = true;
    _maybeShowBannerSoon();
}

let _allowBannerShow = false;
let _deferredPrompt = null;
let _bannerInitialized = false;
let _bannerEls = null;
let _lastMaybeShowTimer = null;

function initInstallBanner({ allowShow }) {
    if (_bannerInitialized) return;
    _bannerInitialized = true;

    _allowBannerShow = Boolean(allowShow);

    const bannerEl = document.getElementById('pwaInstallBanner');
    const installBtn = document.getElementById('pwaInstallBtn');
    const closeBtn = document.getElementById('pwaInstallCloseBtn');
    if (!bannerEl || !installBtn || !closeBtn) return;

    _bannerEls = { bannerEl, installBtn, closeBtn };

    const DISMISS_UNTIL_KEY = 'ecoshot_pwa_install_banner_dismissed_until';
    const LAST_SHOWN_AT_KEY = 'ecoshot_pwa_install_banner_last_shown_at';

    const isMobile = () => window.matchMedia?.('(max-width: 767.98px)')?.matches ?? false;
    const isStandalone = () =>
        window.matchMedia?.('(display-mode: standalone)')?.matches
        || window.navigator?.standalone === true;

    const isIos = () => {
        const ua = navigator.userAgent || '';
        return /iPad|iPhone|iPod/i.test(ua) && !window.MSStream;
    };

    const isSafari = () => {
        const ua = navigator.userAgent || '';
        // Rough safari detection (exclude chrome/ios webviews)
        return /Safari/i.test(ua) && !/Chrome|CriOS|Edg|FxiOS/i.test(ua);
    };

    const now = () => Date.now();
    const readNumber = (key) => {
        const v = Number(localStorage.getItem(key));
        return Number.isFinite(v) ? v : 0;
    };

    const isDismissedNow = () => readNumber(DISMISS_UNTIL_KEY) > now();
    const wasShownRecently = () => {
        const last = readNumber(LAST_SHOWN_AT_KEY);
        // Don't nag too often.
        return last > 0 && (now() - last) < 24 * 60 * 60 * 1000;
    };

    const hide = () => {
        bannerEl.classList.add('d-none');
        document.body.classList.remove('has-pwa-banner');
    };

    const show = ({ mode }) => {
        if (!_allowBannerShow) return;
        if (!isMobile()) return;
        if (isStandalone()) return;
        if (isDismissedNow()) return;
        if (wasShownRecently()) return;

        const textMuted = bannerEl.querySelector('.text-muted');
        if (textMuted) {
            textMuted.textContent = mode === 'ios'
                ? 'W Safari: Udostępnij → „Do ekranu początkowego”.'
                : 'Dodaj EcoShot CRM do ekranu głównego.';
        }

        installBtn.textContent = mode === 'ios' ? 'Jak zainstalować' : 'Zainstaluj';
        bannerEl.classList.remove('d-none');
        document.body.classList.add('has-pwa-banner');
        try {
            localStorage.setItem(LAST_SHOWN_AT_KEY, String(now()));
        } catch (_) {
            // ignore
        }
    };

    closeBtn.addEventListener('click', () => {
        // Dismiss for 14 days (so it can reappear later if still useful).
        try {
            localStorage.setItem(DISMISS_UNTIL_KEY, String(now() + 14 * 24 * 60 * 60 * 1000));
        } catch (_) {
            // ignore
        }
        hide();
    });

    window.addEventListener('appinstalled', () => {
        hide();
    });

    // Android/Chromium flow
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent mini-infobar
        e.preventDefault();
        _deferredPrompt = e;
        show({ mode: 'prompt' });
    });

    installBtn.addEventListener('click', async () => {
        if (isIos() && isSafari()) {
            // iOS: no prompt. Keep banner, just update text.
            show({ mode: 'ios' });
            return;
        }

        if (!_deferredPrompt) return;

        try {
            _deferredPrompt.prompt();
            const choice = await _deferredPrompt.userChoice;
            _deferredPrompt = null;
            if (choice?.outcome === 'accepted') {
                hide();
            }
        } catch (err) {
            console.warn('PWA install prompt failed:', err);
        }
    });

    const maybeShowNow = () => {
        if (!_allowBannerShow) return;
        if (!isMobile()) {
            hide();
            return;
        }
        if (isStandalone()) {
            hide();
            return;
        }

        // iOS/Safari fallback: show guidance even without beforeinstallprompt.
        if (isIos() && isSafari()) {
            show({ mode: 'ios' });
            return;
        }

        // Chromium: only show if we have a deferred prompt.
        if (_deferredPrompt) {
            show({ mode: 'prompt' });
        }
    };

    _maybeShowBannerSoon = () => {
        if (_lastMaybeShowTimer) window.clearTimeout(_lastMaybeShowTimer);
        // Delay a bit so it doesn't fight with initial layout/toasts.
        _lastMaybeShowTimer = window.setTimeout(maybeShowNow, 1200);
    };

    // React to viewport changes.
    window.addEventListener('resize', () => _maybeShowBannerSoon());
}

function _maybeShowBannerSoon() {
    // replaced at runtime by initInstallBanner
}

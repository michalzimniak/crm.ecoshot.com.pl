/**
 * Main application initialization
 */

import { initRouter } from './router.js';
import { initSidebar } from './sidebar.js';
import { showToast } from './toasts.js';
import { getStoredAuth, clearAuth } from './api.js';
import { applyBranding } from './branding.js';

export function initApp() {
    // Best-effort branding (title + logo/name). Public endpoint.
    applyBranding().catch(() => {});

    console.log('🚀 Initializing CRM...');
    
    // Check authentication
    const auth = getStoredAuth();
    
    if (auth && auth.access_token) {
        // User is logged in - show app
        showApp();
        initSidebar();
        initRouter();

        // Setup mini (icons-only) sidebar toggle (desktop)
        initMiniSidebarToggle();
        
        // Setup logout handler
        document.getElementById('logoutBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
        
        // Setup sidebar toggle for mobile
        initMobileSidebar();
        
    } else {
        // User is not logged in - show login
        showLogin();
        initRouter();
    }
}

function initMobileSidebar() {
    const sidebar = document.getElementById('appSidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const backdrop = document.getElementById('sidebarBackdrop');
    const nav = document.getElementById('sidebarNav');

    if (!sidebar || !toggleBtn) return;

    const open = () => {
        sidebar.classList.add('show');
        backdrop?.classList.add('show');
        document.body.classList.add('sidebar-mobile-open');
    };

    const close = () => {
        sidebar.classList.remove('show');
        backdrop?.classList.remove('show');
        document.body.classList.remove('sidebar-mobile-open');
    };

    // Align with Bootstrap breakpoints: md starts at 768px.
    // Treat <768px as "mobile" for sidebar overlay behaviors.
    const isMobile = () => window.matchMedia('(max-width: 767.98px)').matches;

    toggleBtn.addEventListener('click', () => {
        if (!isMobile()) return;
        if (sidebar.classList.contains('show')) close();
        else open();
    });

    backdrop?.addEventListener('click', close);

    // Close after navigation (tap on any sidebar link)
    nav?.addEventListener('click', (e) => {
        const target = e.target;
        const link = target?.closest?.('a.nav-link');
        if (!link) return;
        if (isMobile()) close();
    });

    // Close on route changes
    window.addEventListener('hashchange', () => {
        if (isMobile()) close();
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isMobile()) close();
    });

    // If viewport changes to desktop, ensure mobile state is cleared
    window.addEventListener('resize', () => {
        if (!isMobile()) close();
    });
}

function initMiniSidebarToggle() {
    const STORAGE_KEY = 'ecoshot_sidebar_mini';
    const btn = document.getElementById('sidebarMiniToggle');
    if (!btn) return;

    const icon = btn.querySelector('i');

    // Align with Bootstrap breakpoints: md starts at 768px.
    // The mini toggle button is visible from md upwards.
    const isDesktop = () => window.matchMedia('(min-width: 768px)').matches;

    const applyState = (isMini) => {
        // Never apply mini mode on mobile.
        if (!isDesktop()) {
            document.body.classList.remove('sidebar-mini');
        } else {
            document.body.classList.toggle('sidebar-mini', Boolean(isMini));
        }
        if (icon) {
            const actuallyMini = document.body.classList.contains('sidebar-mini');
            icon.className = actuallyMini ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
        }
    };

    const initial = localStorage.getItem(STORAGE_KEY) === '1';
    applyState(initial);

    btn.addEventListener('click', () => {
        if (!isDesktop()) return;
        const next = !document.body.classList.contains('sidebar-mini');
        applyState(next);
        try {
            localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
        } catch (_) {
            // ignore
        }
    });

    // If viewport changes, re-apply stored preference (desktop) or clear it (mobile).
    window.addEventListener('resize', () => {
        const pref = localStorage.getItem(STORAGE_KEY) === '1';
        applyState(pref);
    });
}

export function showApp() {
    document.getElementById('loginContainer').classList.add('d-none');
    document.getElementById('appContainer').classList.remove('d-none');
}

export function showLogin() {
    document.getElementById('appContainer').classList.add('d-none');
    document.getElementById('loginContainer').classList.remove('d-none');
}

export function logout() {
    clearAuth();
    showToast('Wylogowano pomyślnie', 'success');
    
    // Reload page to reset state
    setTimeout(() => {
        window.location.href = '#/login';
        window.location.reload();
    }, 500);
}

export function showLoading() {
    document.getElementById('loadingOverlay')?.classList.remove('d-none');
}

export function hideLoading() {
    document.getElementById('loadingOverlay')?.classList.add('d-none');
}

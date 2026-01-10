/**
 * SPA Router - Hash-based navigation
 */

import { renderLogin } from './views/login.js';
import { renderDashboard } from './views/dashboard.js';
import { renderCustomers } from './views/customers.js';
import { renderJobs } from './views/jobs.js';
import { renderCalendar } from './views/calendar.js';
import { renderContracts } from './views/contracts.js';
import { renderInvoices } from './views/invoices.js';
import { renderPayments } from './views/payments.js';
import { renderConsents } from './views/consents.js';
import { renderGalleries } from './views/galleries.js';
import { renderPhotos } from './views/photos.js';
import { renderReports } from './views/reports.js';
import { renderVouchers } from './views/vouchers.js';
import { renderUsers } from './views/users.js';
import { renderSettings } from './views/settings.js';
import { renderProfile } from './views/profile.js';
import { renderGalleryAccess, renderPublicGallery } from './views/gallery_access.js';
import { showToast } from './toasts.js';
import { getStoredAuth } from './api.js';

const routes = {};
let currentRoute = null;

export function registerRoute(path, handler) {
    routes[path] = handler;
}

export function initRouter() {
    // Register routes
    registerRoute('/login', renderLogin);
    registerRoute('/dashboard', renderDashboard);
    registerRoute('/customers', renderCustomers);
    registerRoute('/jobs', renderJobs);
    registerRoute('/calendar', renderCalendar);
    registerRoute('/contracts', renderContracts);
    registerRoute('/invoices', renderInvoices);
    registerRoute('/payments', renderPayments);
    registerRoute('/consents', renderConsents);
    registerRoute('/galleries', renderGalleries);
    registerRoute('/photos', renderPhotos);
    registerRoute('/gallery-access', renderGalleryAccess);
    registerRoute('/g', renderPublicGallery);
    registerRoute('/reports', renderReports);
    registerRoute('/vouchers', renderVouchers);
    
    // Placeholder routes for not yet implemented views
    registerRoute('/users', renderUsers);
    registerRoute('/settings', renderSettings);
    registerRoute('/profile', renderProfile);
    registerRoute('/404', () => showError('Nie znaleziono strony'));
    
    // Handle initial route
    handleRoute();
    
    // Listen for hash changes
    window.addEventListener('hashchange', handleRoute);
    
    // Intercept link clicks
    document.addEventListener('click', (e) => {
        if (e.target.matches('a[href^="#/"]') || e.target.closest('a[href^="#/"]')) {
            const link = e.target.matches('a') ? e.target : e.target.closest('a');
            const hash = link.getAttribute('href');
            
            if (hash && hash.startsWith('#/')) {
                e.preventDefault();
                window.location.hash = hash;
            }
        }
    });
}

function handleRoute() {
    const auth = getStoredAuth();
    const isLoggedIn = Boolean(auth && auth.access_token);

    const defaultRoute = isLoggedIn ? '/dashboard' : '/login';
    const hash = window.location.hash.slice(1) || defaultRoute;
    
    // Remove query string for route matching
    const pathWithoutQuery = hash.split('?')[0];
    const [, basePath, ...params] = pathWithoutQuery.split('/');
    const fullPath = '/' + (basePath || 'login');
    
    console.log(`📍 Navigating to: ${fullPath}`, params);
    
    currentRoute = fullPath;

    // If user is logged in, never render /login into the hidden login container.
    // This otherwise results in a seemingly blank main view while the app shell is visible.
    if (isLoggedIn && fullPath === '/login') {
        if (window.location.hash !== '#/dashboard') {
            window.location.hash = '#/dashboard';
        }
        return;
    }
    
    // Find matching route
    const handler = routes[fullPath] || routes['/404'];
    
    if (handler) {
        try {
            handler(params);
        } catch (error) {
            console.error('Route handler error:', error);
            showError('Błąd ładowania strony');
        }
    } else {
        console.warn(`No handler for route: ${fullPath}`);
        showError('Nie znaleziono strony');
    }
}

export function navigate(path) {
    window.location.hash = `#${path}`;
}

export function getCurrentRoute() {
    return currentRoute;
}

function showError(message) {
    const container = document.getElementById('viewContainer') || document.getElementById('loginContainer');
    if (container) {
        container.innerHTML = `
            <div class="page-header">
                <h1>Wystąpił błąd</h1>
            </div>
            <div class="card">
                <div class="card-body">
                    <p class="mb-0">${message}</p>
                </div>
            </div>
        `;
    }

    // PROMPT.md: brak flash/alert -> używamy toastów
    showToast(message, 'danger');
}

function showPlaceholder(title) {
    const container = document.getElementById('viewContainer');
    if (container) {
        container.innerHTML = `
            <div class="page-header">
                <h1>${title}</h1>
            </div>
            <div class="card">
                <div class="card-body">
                    Widok <strong>${title}</strong> jest w trakcie implementacji.
                </div>
            </div>
        `;
    }

    showToast(`Widok ${title} jest w trakcie implementacji.`, 'info');
}

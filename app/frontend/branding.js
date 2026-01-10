/**
 * Branding helper (public).
 * Controls: document.title, header brand, login brand.
 */

import { apiRequest } from './api.js';

let cachedBranding = null;
let cacheTs = 0;

export function getDefaultBrandName() {
    return 'EcoShot CRM';
}

export async function fetchBranding({ force = false } = {}) {
    const now = Date.now();
    if (!force && cachedBranding && (now - cacheTs) < 30_000) {
        return cachedBranding;
    }

    try {
        const res = await apiRequest('/settings/branding', { skipAuth: true, showErrors: false });
        cachedBranding = res?.data || null;
        cacheTs = now;
        return cachedBranding;
    } catch (_) {
        return cachedBranding;
    }
}

function applyTitle(brandName) {
    document.title = brandName || getDefaultBrandName();
}

function applyBrandElements({ prefix = '' } = {}, branding) {
    const name = (branding?.name || '').trim() || getDefaultBrandName();
    const hasLogo = Boolean(branding?.has_logo && branding?.logo_url);

    const logoEl = document.getElementById(`${prefix}BrandLogo`);
    const iconEl = document.getElementById(`${prefix}BrandIcon`);
    const textEl = document.getElementById(`${prefix}BrandText`);

    if (textEl) textEl.textContent = name;

    // If logo exists, we don't show the text next to it.
    if (textEl) {
        textEl.classList.toggle('d-none', hasLogo);
    }

    if (logoEl) {
        if (hasLogo) {
            logoEl.src = branding.logo_url;
            logoEl.classList.remove('d-none');
        } else {
            logoEl.removeAttribute('src');
            logoEl.classList.add('d-none');
        }
    }

    if (iconEl) {
        iconEl.classList.toggle('d-none', hasLogo);
    }
}

export async function applyBranding({ force = false, context = null } = {}) {
    const branding = await fetchBranding({ force });
    const name = (branding?.name || '').trim() || getDefaultBrandName();

    const galleryBranding = {
        ...(branding || {}),
        has_logo: Boolean(branding?.has_gallery_logo),
        logo_url: branding?.gallery_logo_url || null,
    };

    const loginBranding = (context === 'gallery') ? galleryBranding : branding;

    applyTitle(name);

    // Header
    applyBrandElements({ prefix: 'app' }, branding);

    // Login
    applyBrandElements({ prefix: 'login' }, loginBranding);

    // Footer text on login
    const footer = document.getElementById('loginBrandFooter');
    if (footer) footer.textContent = name;

    return branding;
}

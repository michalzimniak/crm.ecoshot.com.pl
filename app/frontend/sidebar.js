/**
 * Sidebar Navigation - Dynamic menu with permissions
 */

import { getCurrentUser } from './api.js';
import { getCurrentRoute } from './router.js';

// Keep in sync with backend role/permission semantics.
// Backend Permission values are lower snake_case (e.g. "view_contracts").
const ROLE_PERMISSIONS = {
    admin: ['*'],
    photographer: [
        'view_customers',
        'create_customer',
        'edit_customer',
        'view_jobs',
        'create_job',
        'edit_job',
        'change_job_status',
        'view_contracts',
        'create_contract',
        'sign_contract',
        'view_invoices',
        'view_galleries',
        'create_gallery',
        'edit_gallery',
        'publish_gallery',
        'upload_photo',
        'edit_photo',
        'delete_photo',
        'view_consents',
        'manage_consents',
    ],
    accountant: [
        'view_customers',
        'view_jobs',
        'view_contracts',
        'view_invoices',
        'create_invoice',
        'edit_invoice',
        'view_payments',
        'create_payment',
        'edit_payment',
        'view_finance',
        'manage_finance',
    ],
    viewer: [
        'view_customers',
        'view_jobs',
        'view_contracts',
        'view_invoices',
        'view_payments',
        'view_galleries',
        'view_consents',
        'view_finance',
    ]
};

function normalizePermission(permission) {
    if (!permission) return '';
    const trimmed = String(permission).trim();
    if (!trimmed) return '';
    // Accept both styles: "VIEW_CONTRACTS" and "view_contracts".
    return trimmed.toLowerCase();
}

function getUserPermissionSet(user) {
    // If backend ever starts returning user.permissions, prefer that.
    if (Array.isArray(user?.permissions) && user.permissions.length > 0) {
        return new Set(user.permissions.map(normalizePermission).filter(Boolean));
    }

    const role = user?.role;
    const rolePermissions = ROLE_PERMISSIONS[role] || [];
    if (rolePermissions.includes('*')) {
        return new Set(['*']);
    }
    return new Set(rolePermissions);
}

const menuStructure = [
    {
        section: 'Główne',
        items: [
            { path: '/dashboard', icon: 'speedometer2', label: 'Dashboard', permissions: [] },
        ]
    },
    {
        section: 'Klienci i Zlecenia',
        items: [
            { path: '/customers', icon: 'people', label: 'Klienci', permissions: ['view_customers'] },
            { path: '/jobs', icon: 'briefcase', label: 'Zlecenia', permissions: ['view_jobs'] },
            { path: '/calendar', icon: 'calendar3', label: 'Kalendarz', permissions: ['view_jobs'] },
            { path: '/contracts', icon: 'file-earmark-text', label: 'Umowy', permissions: ['view_contracts'] },
            { path: '/consents', icon: 'shield-check', label: 'Zgody', permissions: ['view_consents'] },
        ]
    },
    {
        section: 'Finanse',
        items: [
            { path: '/invoices', icon: 'receipt', label: 'Faktury', permissions: ['view_invoices'] },
            { path: '/payments', icon: 'cash-coin', label: 'Płatności', permissions: ['view_payments'] },
            { path: '/reports', icon: 'graph-up', label: 'Raporty', permissions: ['view_reports'] },
        ]
    },
    {
        section: 'Galerie',
        items: [
            { path: '/galleries', icon: 'images', label: 'Galerie', permissions: ['view_galleries'] },
        ]
    },
    {
        section: 'Administracja',
        items: [
            { path: '/users', icon: 'person-gear', label: 'Użytkownicy', permissions: ['MANAGE_USERS'] },
            { path: '/vouchers', icon: 'qr-code', label: 'Vouchery', permissions: ['manage_settings'] },
            { path: '/settings', icon: 'gear', label: 'Ustawienia', permissions: ['view_settings'] },
        ]
    }
];

export async function initSidebar() {
    const nav = document.getElementById('sidebarNav');
    
    if (!nav) {
        console.warn('Sidebar nav element not found');
        return;
    }
    
    try {
        const user = await getCurrentUser();
        
        if (!user) {
            console.warn('No user data for sidebar');
            return;
        }
        
        // Update user name in header
        const userNameElement = document.getElementById('currentUserName');
        if (userNameElement) {
            userNameElement.textContent = user.full_name || user.username;
        }
        
        // Render menu
        renderMenu(nav, user);
        
        // Listen for route changes to update active state
        window.addEventListener('hashchange', () => {
            updateActiveStates(nav);
        });
        
        // Set initial active state
        updateActiveStates(nav);
        
    } catch (error) {
        console.error('Failed to initialize sidebar:', error);
    }
}

function renderMenu(container, user) {
    let html = '';

    const userPermissions = getUserPermissionSet(user);
    
    for (const section of menuStructure) {
        // Filter items by permissions
        const visibleItems = section.items.filter(item => {
            // If no permissions required, show to everyone
            if (!item.permissions || item.permissions.length === 0) {
                return true;
            }

            // Admin sees everything.
            if (userPermissions.has('*') || user?.role === 'admin') {
                return true;
            }

            // Check if user has at least one of the required permissions.
            const required = item.permissions
                .map(normalizePermission)
                .filter(Boolean);

            return required.some(p => userPermissions.has(p));
        });
        
        if (visibleItems.length > 0) {
            html += `<div class="sidebar-section">${section.section}</div>`;
            
            for (const item of visibleItems) {
                html += `
                    <div class="nav-item">
                        <a href="#${item.path}" class="nav-link" data-path="${item.path}" title="${item.label}" aria-label="${item.label}">
                            <i class="bi bi-${item.icon}"></i>
                            <span>${item.label}</span>
                        </a>
                    </div>
                `;
            }
        }
    }
    
    container.innerHTML = html;
}

function updateActiveStates(container) {
    const currentRoute = getCurrentRoute();
    const links = container.querySelectorAll('.nav-link');
    
    links.forEach(link => {
        const path = link.getAttribute('data-path');
        
        if (path === currentRoute) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

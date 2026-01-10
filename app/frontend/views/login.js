/**
 * Login View
 */

import { login } from '../api.js';
import { showApp, logout } from '../app.js';
import { showToast } from '../toasts.js';
import { navigate } from '../router.js';
import { initSidebar } from '../sidebar.js';
import { clearFormErrors, requireValue, wireClearOnInput } from '../forms.js';
import { applyBranding } from '../branding.js';

export function renderLogin() {
    const container = document.getElementById('loginContainer');
    
    container.innerHTML = `
        <div class="login-container">
            <div class="card login-card shadow-lg">
                <div class="card-body">
                    <div class="brand">
                        <h1 class="d-flex align-items-center justify-content-center gap-2">
                            <img id="loginBrandLogo" class="d-none" alt="Logo" style="height: 42px; width: auto;" />
                            <i id="loginBrandIcon" class="bi bi-camera-fill"></i>
                            <span id="loginBrandText">EcoShot CRM</span>
                        </h1>
                        <!--<p>System Zarządzania Fotografią</p>-->
                    </div>
                    
                    <form id="loginForm" novalidate>
                        <div class="mb-3">
                            <label for="username" class="form-label">Nazwa użytkownika</label>
                            <div class="input-group">
                                <span class="input-group-text"><i class="bi bi-person"></i></span>
                                <input type="text" class="form-control" id="username" name="username" 
                                       placeholder="admin" autocomplete="username" autofocus>
                            </div>
                            <div class="invalid-feedback"></div>
                        </div>
                        
                        <div class="mb-4">
                            <label for="password" class="form-label">Hasło</label>
                            <div class="input-group">
                                <span class="input-group-text"><i class="bi bi-lock"></i></span>
                                <input type="password" class="form-control" id="password" name="password" 
                                       placeholder="********" autocomplete="current-password">
                            </div>
                            <div class="invalid-feedback"></div>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-success btn-lg">
                                <i class="bi bi-box-arrow-in-right"></i> Zaloguj się
                            </button>
                        </div>
                    </form>
                    
                    <div class="mt-4 text-center text-muted small">
                        <p class="mb-0"><span id="loginBrandFooter">EcoShot CRM</span> &copy; 2026</p>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Apply branding (best-effort) after DOM nodes exist.
    applyBranding().catch(() => {});
    
    // Handle form submission
    const form = document.getElementById('loginForm');
    wireClearOnInput(form);
    form.addEventListener('submit', handleLogin);
}

async function handleLogin(e) {
    e.preventDefault();
    
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');

    clearFormErrors(form);

    const usernameOk = requireValue(form.username, 'Wpisz nazwę użytkownika');
    const passwordOk = requireValue(form.password, 'Wpisz hasło');
    if (!usernameOk || !passwordOk) {
        return;
    }

    const username = form.username.value.trim();
    const password = form.password.value;
    
    // Disable submit button
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Logowanie...';
    
    try {
        const authData = await login(username, password);
        
        if (authData) {
            showToast('Zalogowano pomyślnie', 'success');
            
            // Show app and navigate to dashboard
            showApp();
            initSidebar();

            // Setup logout handler
            document.getElementById('logoutBtn')?.addEventListener('click', (ev) => {
                ev.preventDefault();
                logout();
            });

            // Setup sidebar toggle for mobile
            document.getElementById('sidebarToggle')?.addEventListener('click', () => {
                document.getElementById('appSidebar')?.classList.toggle('show');
            });
            navigate('/dashboard');
        }
        
    } catch (error) {
        console.error('Login failed:', error);
        showToast(error.message || 'Nieprawidłowy login lub hasło', 'danger');
        
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> Zaloguj się';
        
        // Clear password field
        form.password.value = '';
        form.password.focus();
    }
}

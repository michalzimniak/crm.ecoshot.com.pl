/**
 * Dashboard View
 */

import { financeAPI, jobsAPI, getCurrentUser } from '../api.js';
import { showToast } from '../toasts.js';

export async function renderDashboard() {
    const container = document.getElementById('viewContainer');
    
    // Show loading state
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-speedometer2"></i> Dashboard</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status">
                <span class="visually-hidden">Ładowanie...</span>
            </div>
        </div>
    `;
    
    try {
        // Fetch dashboard data
        const [user, stats] = await Promise.all([
            getCurrentUser(),
            financeAPI.getDashboardStats(),
        ]);
        
        const dashboardStats = stats.data || {};
        
        // Render dashboard
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-speedometer2"></i> Dashboard</h1>
                    <p class="text-muted mb-0">Witaj, ${user?.full_name || user?.username || 'Użytkowniku'}!</p>
                </div>
                <div>
                    <span class="badge bg-secondary">${new Date().toLocaleDateString('pl-PL', { 
                        weekday: 'long', 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric' 
                    })}</span>
                </div>
            </div>
            
            <!-- Stats Cards -->
            <div class="row mb-4">
                <div class="col-md-3 mb-3">
                    <div class="card border-primary">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <p class="text-muted mb-1 small">Aktywne zlecenia</p>
                                    <h2 class="mb-0">${dashboardStats.active_jobs || 0}</h2>
                                </div>
                                <div class="text-primary">
                                    <i class="bi bi-briefcase fs-1"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3 mb-3">
                    <div class="card border-warning">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <p class="text-muted mb-1 small">Niepłacone faktury</p>
                                    <h2 class="mb-0">${dashboardStats.unpaid_invoices || 0}</h2>
                                </div>
                                <div class="text-warning">
                                    <i class="bi bi-receipt fs-1"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3 mb-3">
                    <div class="card border-info">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <p class="text-muted mb-1 small">Galerie do publikacji</p>
                                    <h2 class="mb-0">${dashboardStats.pending_galleries || 0}</h2>
                                </div>
                                <div class="text-info">
                                    <i class="bi bi-images fs-1"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3 mb-3">
                    <div class="card border-success">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <p class="text-muted mb-1 small">Prognoza miesięczna</p>
                                    <h2 class="mb-0">${formatCurrency(dashboardStats.monthly_revenue || 0)}</h2>
                                </div>
                                <div class="text-success">
                                    <i class="bi bi-cash-coin fs-1"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Recent Activity -->
            <div class="row">
                <div class="col-lg-8 mb-4">
                    <div class="card">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5 class="mb-0"><i class="bi bi-clock-history"></i> Ostatnie zlecenia</h5>
                            <a href="#/jobs" class="btn btn-sm btn-outline-primary">Zobacz wszystkie</a>
                        </div>
                        <div class="card-body">
                            <div id="recentJobsContainer">
                                <div class="text-center py-3">
                                    <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-4 mb-4">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-list-check"></i> Szybkie akcje</h5>
                        </div>
                        <div class="card-body">
                            <div class="d-grid gap-2">
                                <a href="#/customers/new" class="btn btn-outline-success">
                                    <i class="bi bi-person-plus"></i> Nowy klient
                                </a>
                                <a href="#/jobs/new" class="btn btn-outline-primary">
                                    <i class="bi bi-briefcase"></i> Nowe zlecenie
                                </a>
                                <a href="#/calendar" class="btn btn-outline-warning">
                                    <i class="bi bi-calendar3"></i> Kalendarz
                                </a>
                                <a href="#/galleries/new" class="btn btn-outline-info">
                                    <i class="bi bi-images"></i> Nowa galeria
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Load recent jobs
        loadRecentJobs();
        
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showToast('Błąd ładowania dashboardu', 'danger');
        
        container.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="bi bi-exclamation-triangle"></i> Błąd ładowania danych dashboardu
            </div>
        `;
    }
}

async function loadRecentJobs() {
    const container = document.getElementById('recentJobsContainer');
    
    try {
        const response = await jobsAPI.getAll({ per_page: 5 });
        const jobs = response.data || [];
        
        if (jobs.length === 0) {
            container.innerHTML = `
                <p class="text-muted mb-0">Brak ostatnich zleceń</p>
            `;
            return;
        }
        
        container.innerHTML = `
            <div class="list-group list-group-flush">
                ${jobs.map(job => `
                    <a href="#/jobs/${job.id}" class="list-group-item list-group-item-action">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">${job.customer?.full_name || 'Klient'}</h6>
                                <p class="mb-0 small text-muted">${job.offer?.name || 'Zlecenie'}</p>
                            </div>
                            <div class="text-end">
                                <span class="badge bg-${getStatusColor(job.status)}">${job.status}</span>
                                <p class="mb-0 small text-muted mt-1">${formatCurrency(job.final_price)}</p>
                            </div>
                        </div>
                    </a>
                `).join('')}
            </div>
        `;
        
    } catch (error) {
        console.error('Failed to load recent jobs:', error);
        container.innerHTML = `
            <p class="text-danger mb-0">Błąd ładowania zleceń</p>
        `;
    }
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: 'PLN'
    }).format(amount || 0);
}

function getStatusColor(status) {
    const colors = {
        'pending': 'secondary',
        'confirmed': 'primary',
        'in_progress': 'info',
        'completed': 'success',
        'cancelled': 'danger',
    };
    return colors[status] || 'secondary';
}

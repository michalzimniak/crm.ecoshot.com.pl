/**
 * Reports View - Raporty i statystyki finansowe
 */

import { financeAPI, jobsAPI, invoicesAPI, customersAPI } from '../api.js';
import { showToast } from '../toasts.js';

let currentPeriod = 'month';
let revenueChartInstance = null;

export async function renderReports(params) {
    const container = document.getElementById('viewContainer');
    
    // Show loading
    container.innerHTML = `
        <div class="page-header">
            <h1><i class="bi bi-bar-chart"></i> Raporty</h1>
        </div>
        <div class="text-center py-5">
            <div class="spinner-border text-success" role="status"></div>
        </div>
    `;
    
    try {
        // Load stats
        const statsResponse = await financeAPI.getStats();
        const stats = statsResponse.data || {};
        
        // Load outstanding invoices
        const outstandingResponse = await financeAPI.getOutstanding();
        const outstanding = outstandingResponse.data || [];
        
        // Load revenue data
        const revenueResponse = await financeAPI.getRevenue({ period: currentPeriod });
        const revenue = revenueResponse.data || [];
        
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h1><i class="bi bi-bar-chart"></i> Raporty i Statystyki</h1>
                    <p class="text-muted mb-0">Analiza finansowa i biznesowa</p>
                </div>
                <div class="btn-group">
                    <button class="btn ${currentPeriod === 'week' ? 'btn-success' : 'btn-outline-success'}" 
                            onclick="changePeriod('week')">Tydzień</button>
                    <button class="btn ${currentPeriod === 'month' ? 'btn-success' : 'btn-outline-success'}" 
                            onclick="changePeriod('month')">Miesiąc</button>
                    <button class="btn ${currentPeriod === 'year' ? 'btn-success' : 'btn-outline-success'}" 
                            onclick="changePeriod('year')">Rok</button>
                </div>
            </div>
            
            <!-- Summary Cards -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h6 class="text-muted mb-1">Przychód ogółem</h6>
                                    <h3 class="mb-0">${formatCurrency(stats.total_revenue || 0)}</h3>
                                </div>
                                <div class="text-success">
                                    <i class="bi bi-cash-stack" style="font-size: 2rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h6 class="text-muted mb-1">Zaległości</h6>
                                    <h3 class="mb-0 text-danger">${formatCurrency(stats.outstanding || 0)}</h3>
                                </div>
                                <div class="text-danger">
                                    <i class="bi bi-exclamation-triangle" style="font-size: 2rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h6 class="text-muted mb-1">Aktywne zlecenia</h6>
                                    <h3 class="mb-0">${stats.active_jobs || 0}</h3>
                                </div>
                                <div class="text-primary">
                                    <i class="bi bi-briefcase" style="font-size: 2rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-3">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h6 class="text-muted mb-1">Klienci</h6>
                                    <h3 class="mb-0">${stats.total_customers || 0}</h3>
                                </div>
                                <div class="text-info">
                                    <i class="bi bi-people" style="font-size: 2rem;"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <!-- Revenue Chart -->
                <div class="col-lg-8">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-graph-up"></i> Przychody - ${getPeriodLabel(currentPeriod)}</h5>
                        </div>
                        <div class="card-body">
                            ${renderRevenueChart(revenue)}
                        </div>
                    </div>
                </div>
                
                <!-- Outstanding Invoices -->
                <div class="col-lg-4">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-clock-history"></i> Zaległe faktury</h5>
                        </div>
                        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                            ${outstanding.length === 0 ? `
                                <p class="text-center text-muted py-3">Brak zaległych faktur</p>
                            ` : outstanding.map(invoice => `
                                <div class="mb-3 pb-3 border-bottom">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div>
                                            <h6 class="mb-1">
                                                <a href="#/invoices/${invoice.id}">${invoice.invoice_number}</a>
                                            </h6>
                                            <small class="text-muted">${invoice.customer?.display_name || 'Brak klienta'}</small>
                                        </div>
                                        <span class="badge bg-danger">${formatCurrency(invoice.remaining_amount || invoice.total_gross)}</span>
                                    </div>
                                    <small class="text-danger">
                                        <i class="bi bi-calendar-x"></i> Termin: ${formatDate(invoice.due_date)}
                                    </small>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Monthly Summary -->
            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0"><i class="bi bi-calendar3"></i> Podsumowanie miesięczne</h5>
                        </div>
                        <div class="card-body">
                            ${renderMonthlySummary(stats.monthly_summary || [])}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Top Customers -->
            ${stats.top_customers && stats.top_customers.length > 0 ? `
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="bi bi-trophy"></i> Top Klienci</h5>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table">
                                        <thead>
                                            <tr>
                                                <th>#</th>
                                                <th>Klient</th>
                                                <th>Zleceń</th>
                                                <th>Wartość</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${stats.top_customers.map((customer, idx) => `
                                                <tr>
                                                    <td>${idx + 1}</td>
                                                    <td>
                                                        <a href="#/customers/${customer.id}">${customer.display_name}</a>
                                                    </td>
                                                    <td>${customer.job_count}</td>
                                                    <td>${formatCurrency(customer.total_value)}</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            ` : ''}
        `;

        // Post-render: initialize Chart.js chart
        initRevenueChart(revenue);
        
    } catch (error) {
        console.error('Failed to load reports:', error);
        showToast('Błąd ładowania raportów', 'danger');
    }
}

function renderRevenueChart(data) {
    if (!data || data.length === 0) {
        return '<p class="text-center text-muted py-3">Brak danych</p>';
    }
    
    const maxValue = Math.max(...data.map(d => d.revenue || 0));
    if (!isFinite(maxValue) || maxValue <= 0) {
        return '<p class="text-center text-muted py-3">Brak przychodów w wybranym okresie</p>';
    }

    // Canvas placeholder - actual chart is initialized after render.
    // Keep height stable so layout doesn't jump.
    return `
        <div style="position: relative; height: 320px;">
            <canvas id="revenueChartCanvas" aria-label="Wykres przychodów" role="img"></canvas>
        </div>
    `;
}

function initRevenueChart(data) {
    // Clean up previous instance (period switch / rerender).
    if (revenueChartInstance) {
        try { revenueChartInstance.destroy(); } catch (_) {}
        revenueChartInstance = null;
    }

    const canvas = document.getElementById('revenueChartCanvas');
    if (!canvas) return;

    const ChartCtor = window.Chart;
    if (!ChartCtor) {
        // Chart.js not loaded (e.g. CDN blocked) - keep a helpful message.
        canvas.parentElement.innerHTML = '<p class="text-center text-muted py-3">Nie udało się załadować wykresu (Chart.js)</p>';
        return;
    }

    if (!data || data.length === 0) {
        canvas.parentElement.innerHTML = '<p class="text-center text-muted py-3">Brak danych</p>';
        return;
    }

    const maxValue = Math.max(...data.map(d => d.revenue || 0));
    if (!isFinite(maxValue) || maxValue <= 0) {
        canvas.parentElement.innerHTML = '<p class="text-center text-muted py-3">Brak przychodów w wybranym okresie</p>';
        return;
    }

    const labels = data.map(d => formatXAxisLabel(d.label));
    const values = data.map(d => Number(d.revenue || 0));
    const dense = data.length >= 20;

    revenueChartInstance = new ChartCtor(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Przychody',
                    data: values,
                    backgroundColor: '#198754',
                    borderRadius: 4,
                    borderSkipped: false,
                    barPercentage: dense ? 0.9 : 0.8,
                    categoryPercentage: dense ? 0.9 : 0.8,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => items?.[0]?.label || '',
                        label: (ctx) => formatCurrency(ctx.parsed?.y ?? 0),
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        autoSkip: true,
                        maxTicksLimit: dense ? 7 : 14,
                        maxRotation: 0,
                        minRotation: 0,
                    },
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => formatAxisCurrency(value),
                    },
                },
            },
        },
    });
}

function formatAxisCurrency(value) {
    const num = Number(value);
    if (!isFinite(num)) return '';
    try {
        const full = new Intl.NumberFormat('pl-PL', {
            maximumFractionDigits: 0,
            useGrouping: false,
        }).format(num);
        return `${full} zł`;
    } catch (_) {
        return `${Math.round(num)} zł`;
    }
}

function formatXAxisLabel(label) {
    // YYYY-MM-DD -> DD.MM (more compact)
    if (typeof label === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(label)) {
        const [y, m, d] = label.split('-');
        return `${d}.${m}`;
    }
    // YYYY-MM -> MM.YYYY
    if (typeof label === 'string' && /^\d{4}-\d{2}$/.test(label)) {
        const [y, m] = label.split('-');
        return `${m}.${y}`;
    }
    return label ?? '';
}

function renderMonthlySummary(data) {
    if (!data || data.length === 0) {
        return '<p class="text-center text-muted py-3">Brak danych</p>';
    }
    
    return `
        <div class="table-responsive">
            <table class="table">
                <thead>
                    <tr>
                        <th>Miesiąc</th>
                        <th>Przychód</th>
                        <th>Zleceń</th>
                        <th>Faktur</th>
                        <th>Zapłacone</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.map(month => `
                        <tr>
                            <td>${month.month}</td>
                            <td>${formatCurrency(month.revenue || 0)}</td>
                            <td>${month.jobs || 0}</td>
                            <td>${month.invoices || 0}</td>
                            <td>${formatCurrency(month.paid || 0)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

window.changePeriod = (period) => {
    currentPeriod = period;
    renderReports();
};

function getPeriodLabel(period) {
    const labels = {
        'week': 'Ostatnie 7 dni',
        'month': 'Ostatnie 30 dni',
        'year': 'Ostatnie 12 miesięcy'
    };
    return labels[period] || period;
}

function formatCurrency(amount) {
    if (amount === null || amount === undefined) return '0,00 zł';
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: 'PLN'
    }).format(amount);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('pl-PL');
}

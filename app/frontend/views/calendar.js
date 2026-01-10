/**
 * Calendar View - Rezerwacje terminów (zlecenia)
 */

import { jobsAPI } from '../api.js';
import { showToast } from '../toasts.js';

export async function renderCalendar(params) {
    const container = document.getElementById('viewContainer');

    const now = new Date();
    const parsed = parseCalendarParams(params, now);
    const view = parsed.view;
    const focus = parsed.focus;

    const range = getRangeForView(view, focus);
    const rangeStart = range.start;
    const rangeEnd = range.end;

    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1><i class="bi bi-calendar3"></i> Kalendarz</h1>
                <p class="text-muted mb-0">Rezerwacje terminów (zlecenia)</p>
            </div>
            <div class="d-flex gap-2 flex-wrap">
                <div class="btn-group" role="group" aria-label="Widok kalendarza">
                    <button class="btn btn-outline-secondary ${view === 'month' ? 'active' : ''}" id="calViewMonthBtn">Miesiąc</button>
                    <button class="btn btn-outline-secondary ${view === 'week' ? 'active' : ''}" id="calViewWeekBtn">Tydzień</button>
                    <button class="btn btn-outline-secondary ${view === 'day' ? 'active' : ''}" id="calViewDayBtn">Dzień</button>
                </div>
                <div class="btn-group">
                    <button class="btn btn-outline-secondary" id="calPrevBtn"><i class="bi bi-chevron-left"></i></button>
                    <button class="btn btn-outline-secondary" id="calTodayBtn">Dzisiaj</button>
                    <button class="btn btn-outline-secondary" id="calNextBtn"><i class="bi bi-chevron-right"></i></button>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <div class="fw-semibold">${formatTitleForView(view, focus)}</div>
                <div class="text-muted small">Widok tylko do podglądu rezerwacji</div>
            </div>
            <div class="card-body" id="calendarBody">
                <div class="text-center py-5">
                    <div class="spinner-border text-success" role="status"></div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('calViewMonthBtn')?.addEventListener('click', () => {
        window.location.hash = calendarHash('month', focus);
    });
    document.getElementById('calViewWeekBtn')?.addEventListener('click', () => {
        window.location.hash = calendarHash('week', focus);
    });
    document.getElementById('calViewDayBtn')?.addEventListener('click', () => {
        window.location.hash = calendarHash('day', focus);
    });

    document.getElementById('calPrevBtn')?.addEventListener('click', () => {
        window.location.hash = calendarHash(view, shiftFocus(view, focus, -1));
    });
    document.getElementById('calNextBtn')?.addEventListener('click', () => {
        window.location.hash = calendarHash(view, shiftFocus(view, focus, +1));
    });
    document.getElementById('calTodayBtn')?.addEventListener('click', () => {
        window.location.hash = calendarHash(view, new Date());
    });

    try {
        const res = await jobsAPI.getCalendar(rangeStart.toISOString(), rangeEnd.toISOString());
        const jobs = res?.data || [];
        renderCalendarBody(view, jobs, focus);
    } catch (e) {
        console.error('Failed to load calendar', e);
        showToast('Błąd ładowania kalendarza', 'danger');
        const body = document.getElementById('calendarBody');
        if (body) body.innerHTML = '<div class="text-muted">Nie udało się załadować rezerwacji.</div>';
    }
}

function renderCalendarBody(view, jobs, focus) {
    if (view === 'day') return renderDayView(jobs, focus);
    if (view === 'week') return renderWeekView(jobs, focus);
    return renderMonthView(jobs, focus);
}

function renderMonthView(jobs, focus) {
    const body = document.getElementById('calendarBody');
    if (!body) return;

    const monthStart = new Date(focus.getFullYear(), focus.getMonth(), 1, 0, 0, 0);
    const monthEnd = new Date(focus.getFullYear(), focus.getMonth() + 1, 1, 0, 0, 0);
    const gridStart = startOfWeek(monthStart);
    const gridEnd = endOfWeek(new Date(monthEnd.getTime() - 1));

    const byDay = groupJobsByDay(jobs);

    const headers = ['Pon', 'Wto', 'Śro', 'Czw', 'Pią', 'Sob', 'Nie'];
    let html = `
        <div class="table-responsive">
            <table class="table table-bordered align-middle mb-0">
                <thead>
                    <tr>
                        ${headers.map(h => `<th class="text-center small text-muted">${h}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
    `;

    for (let weekStart = new Date(gridStart); weekStart <= gridEnd; weekStart = addDays(weekStart, 7)) {
        html += '<tr>';

        for (let i = 0; i < 7; i++) {
            const day = addDays(weekStart, i);
            const key = dateKey(day);
            const inMonth = day >= monthStart && day < monthEnd;
            const items = (byDay.get(key) || []).sort((a, b) => a.start - b.start);

            html += `
                <td style="vertical-align: top; min-width: 140px;" class="${inMonth ? '' : 'table-light'}">
                    <div class="d-flex justify-content-between align-items-center">
                        <button class="btn btn-link btn-sm p-0 text-decoration-none" data-cal-day="${key}" title="Pokaż dzień">
                            <span class="fw-semibold ${inMonth ? '' : 'text-muted'}">${day.getDate()}</span>
                        </button>
                        <span class="text-muted small">${items.length ? items.length : ''}</span>
                    </div>
                    ${items.length ? `
                        <div class="mt-2">
                            ${items.slice(0, 4).map(({ job, start, end }) => `
                                <div class="small mb-2">
                                    <div class="text-muted">${formatTime(start)}${end ? `–${formatTime(end)}` : ''}</div>
                                    <a href="#/jobs/${job.id}" class="text-decoration-none">#${job.id}</a>
                                    <span class="text-muted">${escapeHtml(job.title || '')}</span>
                                </div>
                            `).join('')}
                            ${items.length > 4 ? `<div class="text-muted small">+${items.length - 4} więcej</div>` : ''}
                        </div>
                    ` : '<div class="text-muted small mt-2">—</div>'}
                </td>
            `;
        }

        html += '</tr>';
    }

    html += `
                </tbody>
            </table>
        </div>
    `;

    body.innerHTML = html;

    body.querySelectorAll('[data-cal-day]')?.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const key = e.currentTarget?.getAttribute('data-cal-day');
            if (!key) return;
            const d = parseDateKey(key);
            if (!d) return;
            window.location.hash = calendarHash('day', d);
        });
    });
}

function renderWeekView(jobs, focus) {
    const body = document.getElementById('calendarBody');
    if (!body) return;

    const weekStart = startOfWeek(focus);
    const byDay = groupJobsByDay(jobs);
    const headers = ['Pon', 'Wto', 'Śro', 'Czw', 'Pią', 'Sob', 'Nie'];

    let html = `
        <div class="table-responsive">
            <table class="table table-bordered align-middle mb-0">
                <thead>
                    <tr>
                        ${headers.map((h, idx) => {
                            const d = addDays(weekStart, idx);
                            return `<th class="text-center small">${h}<div class="text-muted small">${d.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' })}</div></th>`;
                        }).join('')}
                    </tr>
                </thead>
                <tbody>
                    <tr>
    `;

    for (let i = 0; i < 7; i++) {
        const day = addDays(weekStart, i);
        const key = dateKey(day);
        const items = (byDay.get(key) || []).sort((a, b) => a.start - b.start);
        html += `
            <td style="vertical-align: top; min-width: 160px;">
                ${items.length ? items.map(({ job, start, end }) => `
                    <div class="border rounded p-2 mb-2">
                        <div class="small text-muted">${formatTime(start)}${end ? `–${formatTime(end)}` : ''}</div>
                        <div>
                            <a href="#/jobs/${job.id}" class="fw-semibold text-decoration-none">#${job.id}</a>
                            <span class="text-muted">${escapeHtml(job.title || '')}</span>
                        </div>
                        ${job.event_location ? `<div class="small text-muted">${escapeHtml(job.event_location)}</div>` : ''}
                    </div>
                `).join('') : '<div class="text-muted small">Brak</div>'}
            </td>
        `;
    }

    html += `
                    </tr>
                </tbody>
            </table>
        </div>
    `;

    body.innerHTML = html;
}

function renderDayView(jobs, focus) {
    const body = document.getElementById('calendarBody');
    if (!body) return;

    const key = dateKey(focus);
    const byDay = groupJobsByDay(jobs);
    const items = (byDay.get(key) || []).sort((a, b) => a.start - b.start);

    body.innerHTML = `
        <div class="mb-3">
            <div class="fw-semibold">${focus.toLocaleDateString('pl-PL', { weekday: 'long', year: 'numeric', month: 'long', day: '2-digit' })}</div>
            <div class="text-muted small">${items.length ? `${items.length} rezerw.` : 'Brak rezerwacji'}</div>
        </div>
        ${items.length ? `
            <div class="list-group">
                ${items.map(({ job, start, end }) => `
                    <div class="list-group-item">
                        <div class="d-flex justify-content-between align-items-start gap-3">
                            <div>
                                <div class="fw-semibold">
                                    <a href="#/jobs/${job.id}" class="text-decoration-none">#${job.id}</a>
                                    <span class="ms-2">${escapeHtml(job.title || '')}</span>
                                </div>
                                ${job.customer?.display_name ? `<div class="text-muted small">${escapeHtml(job.customer.display_name)}</div>` : ''}
                                ${job.event_location ? `<div class="text-muted small">${escapeHtml(job.event_location)}</div>` : ''}
                            </div>
                            <div class="text-end">
                                <div class="fw-semibold">${formatTime(start)}${end ? `–${formatTime(end)}` : ''}</div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        ` : '<div class="text-muted">Brak rezerwacji na ten dzień.</div>'}
    `;
}

function formatMonthTitle(d) {
    return d.toLocaleString('pl-PL', { year: 'numeric', month: 'long' });
}

function formatDateHeader(d) {
    return d.toLocaleDateString('pl-PL', { weekday: 'long', year: 'numeric', month: '2-digit', day: '2-digit' });
}

function formatTime(d) {
    return d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
    return String(str)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function parseCalendarParams(params, now) {
    const p = Array.isArray(params) ? params : [];
    const view = (p[0] === 'week' || p[0] === 'day' || p[0] === 'month') ? p[0] : 'month';

    // Supported hashes:
    // - #/calendar
    // - #/calendar/<YYYY>/<M>
    // - #/calendar/<view>/<YYYY>/<M>
    // - #/calendar/day/<YYYY>/<M>/<D>
    const offset = (p[0] === 'week' || p[0] === 'day' || p[0] === 'month') ? 1 : 0;
    const y = Number(p[offset + 0]) || now.getFullYear();
    const m = Number(p[offset + 1]) || (now.getMonth() + 1);
    const d = Number(p[offset + 2]) || now.getDate();

    const safeMonth = Math.min(12, Math.max(1, m));
    const safeDay = Math.min(31, Math.max(1, d));
    const focus = new Date(y, safeMonth - 1, safeDay, 0, 0, 0);
    return { view, focus };
}

function calendarHash(view, focus) {
    const y = focus.getFullYear();
    const m = focus.getMonth() + 1;
    const d = focus.getDate();
    if (view === 'day') return `#/calendar/day/${y}/${m}/${d}`;
    if (view === 'week') return `#/calendar/week/${y}/${m}/${d}`;
    return `#/calendar/month/${y}/${m}`;
}

function shiftFocus(view, focus, delta) {
    const d = new Date(focus);
    if (view === 'day') {
        d.setDate(d.getDate() + delta);
        return d;
    }
    if (view === 'week') {
        d.setDate(d.getDate() + delta * 7);
        return d;
    }
    // month
    d.setMonth(d.getMonth() + delta);
    d.setDate(1);
    return d;
}

function getRangeForView(view, focus) {
    if (view === 'day') {
        const start = new Date(focus.getFullYear(), focus.getMonth(), focus.getDate(), 0, 0, 0);
        const end = new Date(focus.getFullYear(), focus.getMonth(), focus.getDate() + 1, 0, 0, 0);
        return { start, end };
    }
    if (view === 'week') {
        const start = startOfWeek(focus);
        const end = addDays(start, 7);
        return { start, end };
    }
    // month
    const monthStart = new Date(focus.getFullYear(), focus.getMonth(), 1, 0, 0, 0);
    const monthEnd = new Date(focus.getFullYear(), focus.getMonth() + 1, 1, 0, 0, 0);
    const start = startOfWeek(monthStart);
    const end = addDays(endOfWeek(new Date(monthEnd.getTime() - 1)), 1);
    return { start, end };
}

function startOfWeek(d) {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0);
    const day = x.getDay();
    // JS: 0=Sun..6=Sat. We want Monday=0.
    const diff = (day === 0 ? -6 : 1 - day);
    x.setDate(x.getDate() + diff);
    return x;
}

function endOfWeek(d) {
    const s = startOfWeek(d);
    const e = addDays(s, 6);
    e.setHours(23, 59, 59, 999);
    return e;
}

function addDays(d, days) {
    const x = new Date(d);
    x.setDate(x.getDate() + days);
    return x;
}

function dateKey(d) {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

function parseDateKey(key) {
    if (!key || typeof key !== 'string') return null;
    const m = key.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const d = Number(m[3]);
    if (!y || !mo || !d) return null;
    return new Date(y, mo - 1, d, 0, 0, 0);
}

function normalizeJobTimes(j) {
    const start = j.event_start
        ? new Date(j.event_start)
        : (j.event_date ? new Date(`${j.event_date}T00:00:00`) : null);
    const end = j.event_end ? new Date(j.event_end) : null;
    if (!start || Number.isNaN(start.getTime())) return null;
    return { job: j, start, end };
}

function groupJobsByDay(jobs) {
    const byDay = new Map();
    for (const j of jobs || []) {
        const item = normalizeJobTimes(j);
        if (!item) continue;
        const key = dateKey(item.start);
        if (!byDay.has(key)) byDay.set(key, []);
        byDay.get(key).push(item);
    }
    return byDay;
}

function formatTitleForView(view, focus) {
    if (view === 'day') {
        return focus.toLocaleDateString('pl-PL', { weekday: 'long', year: 'numeric', month: 'long', day: '2-digit' });
    }
    if (view === 'week') {
        const start = startOfWeek(focus);
        const end = addDays(start, 6);
        const a = start.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const b = end.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' });
        return `Tydzień: ${a} – ${b}`;
    }
    return formatMonthTitle(new Date(focus.getFullYear(), focus.getMonth(), 1));
}

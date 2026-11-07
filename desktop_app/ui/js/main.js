/**
 * main.js — School ERP Desktop App Entry Point (Phase 2 & Phase 3)
 *
 * Coordinates:
 *   - Offline Auth Gate & First-Run Recovery Code Setup (`login-screen.js`)
 *   - Role-Aware Navigation & 5 Daily Command Center Homes (`home.js`, `role-homes.js`)
 *   - Student 360° Profile (`student-profile.js`), Attendance, Fees & Family Ledger, Settings
 *   - Topbar Backup Health Pill, User/Role Menu, and Global Search (Ctrl+K)
 */

import { apiCall, apiPost, onUnauthorized, setSessionToken } from './core/api.js';
import { setBootstrap, getBootstrap, set, get } from './core/state.js';
import { esc, toast, openModal, closeModal, getModalSubmitHandler } from './core/dom.js';
import { icon } from './core/icons.js';
import { formatTime } from './core/format.js';
import { initRouter, registerScreen, buildSidebar, navigateTo } from './core/router.js';
import { injectBilingualCSS } from './core/i18n.js';

import { checkAuthAndGate, showLoginGate } from './screens/login/login-screen.js';
import { renderDashboardScreen } from './screens/dashboard/home.js';
import { renderAttendanceScreen, attachAttendanceEvents } from './screens/attendance/daily-sheet.js';
import { renderStudentsScreen } from './screens/school/students-list.js';
import { renderStudentProfileScreen } from './screens/school/student-profile.js';
import { renderFeesScreen } from './screens/fees/fees-workspace.js';
import { renderSettingsScreen } from './screens/settings/settings-screen.js';

async function loadBootstrapData() {
  set({ loadingBootstrap: true });
  try {
    const data = await apiCall('/api/bootstrap');
    _applyBootstrapData(data);
    return data;
  } catch (err) {
    console.error('[main] Bootstrap failed:', err);
    if (err.status !== 401) {
      toast('Unable to load workspace snapshot — click Refresh', 'error', { duration: 6000 });
    }
    return null;
  }
}

function _applyBootstrapData(data) {
  setBootstrap(data);
  if (window.ERP_LEGACY && typeof window.ERP_LEGACY.setData === 'function') {
    window.ERP_LEGACY.setData(data);
  }
  buildSidebar(data);
  const brandEl = document.getElementById('brand-school-name');
  if (brandEl) brandEl.textContent = get('schoolName') || 'School ERP';
  refreshTopbarStatus();
}

function registerAllScreens() {
  registerScreen('dashboard',  async () => renderDashboardScreen());
  registerScreen('school',     async () => renderStudentsScreen());
  registerScreen('student360', async () => renderStudentProfileScreen());
  registerScreen('fees',       async () => renderFeesScreen());
  registerScreen('settings',   async () => renderSettingsScreen());

  registerScreen('attendance', async () => {
    const html = await renderAttendanceScreen();
    setTimeout(attachAttendanceEvents, 30);
    return html;
  });

  const legacyTabs = ['assignment', 'timetable', 'exam', 'library', 'event', 'hostel', 'transport'];
  for (const tab of legacyTabs) {
    registerScreen(tab, () => {
      if (window.ERP_LEGACY && typeof window.ERP_LEGACY.renderTab === 'function') {
        return window.ERP_LEGACY.renderTab(tab, getBootstrap());
      }
      return `<div class="empty-state"><div class="empty-state-title">${esc(tab)} unavailable</div></div>`;
    });
  }
}

export function refreshTopbarStatus() {
  const bh = get('backupHealth');
  const pill  = document.getElementById('topbar-backup-pill');
  const label = document.getElementById('topbar-backup-label');
  if (pill && label) {
    if (!bh || bh.backup_stale) {
      pill.classList.add('stale');
      label.textContent = bh?.last_backup_at ? 'Backup Stale' : 'Backup Needed';
    } else {
      pill.classList.remove('stale');
      label.textContent = `Backup ${formatTime(bh.last_backup_at)}`;
    }
  }

  const userArea = document.getElementById('topbar-user-area');
  const user = get('user');
  if (userArea && user) {
    userArea.innerHTML = `
      <div class="user-chip">
        <span>${esc(user.full_name || user.username)}</span>
        <span class="user-chip-role">${esc(user.role)}</span>
      </div>
      ${user.id ? `<button type="button" class="topbar-btn" id="btn-logout" title="Sign out" aria-label="Sign out">${icon('logout', 15)}</button>` : ''}
    `;
    document.getElementById('btn-logout')?.addEventListener('click', async () => {
      try { await apiPost('/api/auth/logout', {}, { skipAuthGate: true }); } catch { /* ignore */ }
      setSessionToken('');
      set({ user: null });
      showLoginGate(_handleAuthenticatedUser);
    });
  }
}

function initGlobalSearch() {
  const searchInput = document.getElementById('topbar-search-input');
  if (!searchInput) return;

  let searchTimer = null;
  searchInput.addEventListener('input', e => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    if (!q || q.length < 2) { _hideSearchResults(); return; }
    searchTimer = setTimeout(async () => {
      try {
        const res = await apiCall(`/api/search?q=${encodeURIComponent(q)}`);
        _showSearchResults(res.results || [], q);
      } catch { /* ignore */ }
    }, 200);
  });

  searchInput.addEventListener('blur', () => setTimeout(_hideSearchResults, 200));

  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });
}

function _showSearchResults(results, q) {
  let dropdown = document.getElementById('search-dropdown');
  if (!dropdown) {
    dropdown = document.createElement('div');
    dropdown.id = 'search-dropdown';
    dropdown.style.cssText = `
      position:absolute; top:52px; left:0; right:0;
      background:var(--surface); border:1px solid var(--rule-line);
      border-radius:var(--radius); box-shadow:var(--shadow-md);
      z-index:var(--z-tooltip); max-height:320px; overflow-y:auto;
      margin:0 24px;
    `;
    document.querySelector('.topbar')?.appendChild(dropdown);
  }

  if (!results.length) {
    dropdown.innerHTML = `<div style="padding:16px; color:var(--siyahi-soft); font-size:13px; text-align:center;">
      No matches for "${esc(q)}"</div>`;
    return;
  }

  const iconMap = { student: 'users', teacher: 'user-check', voucher: 'fees' };
  dropdown.innerHTML = results.map(r => `
    <div style="display:flex; align-items:center; gap:10px; padding:10px 16px;
                cursor:pointer; border-bottom:1px solid var(--rule-line);"
         class="search-result-row" data-type="${esc(r.type)}" data-id="${esc(r.id)}">
      <span style="color:var(--siyahi-soft);">${icon(iconMap[r.type] || 'info', 16)}</span>
      <div style="flex:1; min-width:0;">
        <div style="font-size:13.5px; font-weight:500; color:var(--siyahi);" class="truncate">${esc(r.label)}</div>
        <div style="font-size:12px; color:var(--siyahi-soft);">${esc(r.sub || '')} • ${esc(r.meta || '')}</div>
      </div>
      <span style="font-size:11px; color:var(--siyahi-soft); text-transform:uppercase;">${esc(r.type)}</span>
    </div>`).join('');

  dropdown.onclick = e => {
    const row = e.target.closest('.search-result-row');
    if (!row) return;
    _hideSearchResults();
    const inputEl = document.getElementById('topbar-search-input');
    if (inputEl) inputEl.value = '';
    if (row.dataset.type === 'student') {
      navigateTo('student360', { selectedStudentId: parseInt(row.dataset.id, 10) });
    } else if (row.dataset.type === 'voucher') {
      navigateTo('fees');
    } else {
      navigateTo('school');
    }
  };
}

function _hideSearchResults() {
  document.getElementById('search-dropdown')?.remove();
}

function initModalAndBridge() {
  document.getElementById('modal-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const handler = getModalSubmitHandler();
    if (!handler) return;
    try { await handler(); } catch (err) { toast(err.message, 'error'); }
  });

  document.getElementById('modal-cancel')?.addEventListener('click', closeModal);
  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  document.getElementById('btn-refresh')?.addEventListener('click', async () => {
    await loadBootstrapData();
    navigateTo(get('tab') || 'dashboard');
  });

  document.getElementById('topbar-backup-pill')?.addEventListener('click', () => {
    const role = get('role');
    if (role === 'admin' || role === 'principal') navigateTo('settings');
  });

  window.ERP_BRIDGE_OPEN_MODAL = (title, bodyHtml, onSubmit) => openModal(title, bodyHtml, onSubmit);
  window.ERP_ON_LEGACY_BOOTSTRAP = data => {
    _applyBootstrapData(data);
    navigateTo(get('tab') || 'dashboard');
  };

  window.ERP = Object.assign(window.ERP || {}, {
    navigateTo, toast, openModal, closeModal, getBootstrap, refreshTopbarStatus,
    reloadStudents:   () => navigateTo('school'),
    reloadAttendance: () => navigateTo('attendance'),
  });
}

async function _handleAuthenticatedUser(user) {
  set({ user, role: user.role || 'admin' });
  await loadBootstrapData();
  const initialTab = location.hash.slice(1) || 'dashboard';
  navigateTo(initialTab);
}

async function init() {
  injectBilingualCSS();
  initModalAndBridge();
  registerAllScreens();
  initRouter();
  initGlobalSearch();
  onUnauthorized(() => showLoginGate(_handleAuthenticatedUser));

  const user = await checkAuthAndGate(_handleAuthenticatedUser);
  if (user) {
    await _handleAuthenticatedUser(user);
  }
}

init().catch(err => {
  console.error('[ERP] Fatal init error:', err);
  const mainEl = document.getElementById('main-view');
  if (mainEl) {
    mainEl.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${icon('alert', 40)}</div>
      <div class="empty-state-title">Application initialization failed</div>
      <div class="empty-state-desc">${esc(err.message)}</div>
    </div>`;
  }
});

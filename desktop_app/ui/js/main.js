/**
 * main.js — School ERP Desktop App Entry Point (Phase 1)
 *
 * Strangler-fig pattern:
 *   - Dashboard ("Aaj Ka Din"), Students Directory (Paginated), aur Daily Haziri
 *     naye ES modules se render hote hain ("Kaghaz aur Siyahi").
 *   - Baaqi tabs window.ERP_LEGACY bridge se chalte hain.
 */

import { apiCall } from './core/api.js';
import { setBootstrap, getBootstrap, set, get, setBilingual } from './core/state.js';
import { esc, toast, openModal, closeModal, getModalSubmitHandler } from './core/dom.js';
import { initRouter, registerScreen, buildSidebar, navigateTo } from './core/router.js';
import { injectBilingualCSS } from './core/i18n.js';

import { renderDashboardScreen } from './screens/dashboard/home.js';
import { renderAttendanceScreen, attachAttendanceEvents } from './screens/attendance/daily-sheet.js';
import { renderStudentsScreen } from './screens/school/students-list.js';

// ─── Bootstrap ───────────────────────────────────────────────────────────────

async function loadBootstrapData() {
  set({ loadingBootstrap: true });
  try {
    const data = await apiCall('/api/bootstrap');
    _applyBootstrapData(data);
    return data;
  } catch (err) {
    console.error('[main] Bootstrap failed:', err);
    toast('App data load nahi ho saka — Refresh karein', 'error', { duration: 8000 });
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
}

// ─── Screen Registration ──────────────────────────────────────────────────────

function registerAllScreens() {
  registerScreen('dashboard', async () => renderDashboardScreen());
  registerScreen('school',    async () => renderStudentsScreen());

  registerScreen('attendance', async () => {
    const html = await renderAttendanceScreen();
    setTimeout(attachAttendanceEvents, 30);
    return html;
  });

  const legacyTabs = [
    'fees', 'assignment', 'timetable',
    'exam', 'library', 'event', 'hostel', 'transport',
  ];

  for (const tab of legacyTabs) {
    registerScreen(tab, () => {
      if (window.ERP_LEGACY && typeof window.ERP_LEGACY.renderTab === 'function') {
        return window.ERP_LEGACY.renderTab(tab, getBootstrap());
      }
      return `
        <div class="empty-state">
          <div class="empty-state-icon">🚧</div>
          <div class="empty-state-title">${esc(tab)} — Coming soon</div>
          <div class="empty-state-desc">Yeh screen agle phase mein aayegi.</div>
        </div>`;
    });
  }
}

// ─── Global Search ───────────────────────────────────────────────────────────

function initGlobalSearch() {
  const searchInput = document.getElementById('topbar-search-input');
  if (!searchInput) return;

  let searchTimer = null;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    if (!q || q.length < 2) {
      _hideSearchResults();
      return;
    }
    searchTimer = setTimeout(() => _doSearch(q), 220);
  });

  searchInput.addEventListener('blur', () => {
    setTimeout(_hideSearchResults, 200);
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });
}

async function _doSearch(q) {
  try {
    const res = await apiCall(`/api/search?q=${encodeURIComponent(q)}`);
    _showSearchResults(res.results || [], q);
  } catch (err) {
    console.warn('[search]', err.message);
  }
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
      "${esc(q)}" ke liye koi result nahi mila</div>`;
    return;
  }

  const typeIcons = { student: '🎓', teacher: '👨‍🏫', voucher: '💰' };

  dropdown.innerHTML = results.map(r => `
    <div style="display:flex; align-items:center; gap:10px; padding:10px 16px;
                cursor:pointer; border-bottom:1px solid var(--rule-line);"
         class="search-result-row" data-type="${esc(r.type)}" data-id="${esc(r.id)}">
      <span style="font-size:18px;">${typeIcons[r.type] || '•'}</span>
      <div style="flex:1; min-width:0;">
        <div style="font-size:13.5px; font-weight:500; color:var(--siyahi);"
             class="truncate">${esc(r.label)}</div>
        <div style="font-size:12px; color:var(--siyahi-soft);">${esc(r.sub || '')} • ${esc(r.meta || '')}</div>
      </div>
      <span style="font-size:11px; color:var(--siyahi-soft); text-transform:uppercase;">${esc(r.type)}</span>
    </div>`).join('');

  dropdown.onclick = (e) => {
    const row = e.target.closest('.search-result-row');
    if (!row) return;
    _hideSearchResults();
    const inputEl = document.getElementById('topbar-search-input');
    if (inputEl) inputEl.value = '';
    if (row.dataset.type === 'voucher') {
      navigateTo('fees');
    } else {
      navigateTo('school');
    }
  };
}

function _hideSearchResults() {
  document.getElementById('search-dropdown')?.remove();
}

// ─── Modal & Bridge Setup ─────────────────────────────────────────────────────

function initModalAndBridge() {
  const form   = document.getElementById('modal-form');
  const cancel = document.getElementById('modal-cancel');
  const close  = document.getElementById('modal-close');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const handler = getModalSubmitHandler();
    if (handler) {
      try {
        await handler();
        closeModal();
      } catch (err) {
        toast(err.message, 'error');
      }
    }
  });

  cancel?.addEventListener('click', closeModal);
  close?.addEventListener('click',  closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  window.ERP_BRIDGE_OPEN_MODAL = (title, bodyHtml, onSubmit) => {
    openModal(title, bodyHtml, onSubmit);
  };
  window.ERP_ON_LEGACY_BOOTSTRAP = (data) => {
    _applyBootstrapData(data);
    navigateTo(get('tab') || 'dashboard');
  };

  window.ERP = window.ERP || {};
  window.ERP.navigateTo       = navigateTo;
  window.ERP.toast            = toast;
  window.ERP.openModal        = openModal;
  window.ERP.closeModal       = closeModal;
  window.ERP.getBootstrap     = getBootstrap;
  window.ERP.reloadStudents   = () => navigateTo('school');
  window.ERP.reloadAttendance = () => navigateTo('attendance');
}

// ─── App Init ─────────────────────────────────────────────────────────────────

async function init() {
  injectBilingualCSS();
  setBilingual(localStorage.getItem('erp_bilingual') === 'true');

  initModalAndBridge();
  registerAllScreens();
  initRouter();
  await loadBootstrapData();
  initGlobalSearch();

  const initialTab = location.hash.slice(1) || 'dashboard';
  navigateTo(initialTab);
}

init().catch(err => {
  console.error('[ERP] Fatal init error:', err);
  const mainEl = document.getElementById('main-view');
  if (mainEl) {
    mainEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">💥</div>
        <div class="empty-state-title">App shuru nahi ho saka</div>
        <div class="empty-state-desc">${esc(err.message)}</div>
      </div>`;
  }
});

/**
 * router.js — Tab-based router with sidebar navigation
 * Hash-based routing: #dashboard, #attendance, etc.
 * Role-based sidebar items (Phase 2 mein auth se populate hoga).
 */

import { get, set, subscribe } from './state.js';
import { esc } from './dom.js';

// ─── Nav Items Definition ─────────────────────────────────────────────────────
// Icon: Unicode emoji (no external font dependency for now)
// key: tab name (matches Bootstrap data keys)
// roles: kaun dekh sakta hai ('*' = sab)

/** @type {NavItem[]} */
export const NAV_ITEMS = [
  { key: 'dashboard',  label: 'Dashboard',      icon: '🏠', roles: ['*'],     section: null },
  { key: 'school',     label: 'Students',        icon: '🎓', roles: ['*'],     section: 'Academic' },
  { key: 'attendance', label: 'Attendance',      icon: '📋', roles: ['*'],     section: 'Academic' },
  { key: 'fees',       label: 'Fee Management',  icon: '💰', roles: ['*'],     section: 'Finance' },
  { key: 'exam',       label: 'Exams & Results', icon: '📝', roles: ['*'],     section: 'Academic' },
  { key: 'assignment', label: 'Assignments',     icon: '📚', roles: ['*'],     section: 'Academic' },
  { key: 'timetable',  label: 'Timetable',       icon: '🕐', roles: ['*'],     section: 'Academic' },
  { key: 'library',    label: 'Library',         icon: '📖', roles: ['*'],     section: 'Services' },
  { key: 'hostel',     label: 'Hostel',          icon: '🏠', roles: ['admin'], section: 'Services' },
  { key: 'transport',  label: 'Transport',       icon: '🚌', roles: ['*'],     section: 'Services' },
  { key: 'event',      label: 'Events',          icon: '📅', roles: ['*'],     section: 'Services' },
];

// ─── Routing ──────────────────────────────────────────────────────────────────

/** @type {Map<string, Function>} */
const _screenRenderers = new Map();

/**
 * Screen renderer register karo
 * @param {string} tabKey
 * @param {Function} renderFn - async () => HTMLElement | string
 */
export function registerScreen(tabKey, renderFn) {
  _screenRenderers.set(tabKey, renderFn);
}

/**
 * Tab navigate karo
 * @param {string} tab
 */
export function navigateTo(tab) {
  set({ tab, filter: '' });
  history.replaceState(null, '', `#${tab}`);
  _renderActiveScreen();
  _updateSidebarActive(tab);
  _updatePageTitle(tab);
}

/**
 * Active screen render karo
 */
async function _renderActiveScreen() {
  const tab       = get('tab');
  const container = document.getElementById('main-view');
  if (!container) return;

  const renderer = _screenRenderers.get(tab);
  if (!renderer) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🚧</div>
        <div class="empty-state-title">"${esc(tab)}" screen abhi banana baaki hai</div>
        <div class="empty-state-desc">Phase 1 implementation mein yeh screen jald aayegi.</div>
      </div>
    `;
    return;
  }

  // Show skeleton while loading
  container.innerHTML = `<div class="panel"><div class="panel-body">
    <div class="skeleton skeleton-title" style="width:200px"></div>
    <div class="skeleton skeleton-row" style="margin-top:16px"></div>
    <div class="skeleton skeleton-row"></div>
    <div class="skeleton skeleton-row"></div>
  </div></div>`;

  try {
    const result = await renderer();
    if (typeof result === 'string') {
      container.innerHTML = result;
    } else if (result instanceof HTMLElement) {
      container.innerHTML = '';
      container.appendChild(result);
    }
  } catch (err) {
    console.error(`[Router] Screen render error (${tab}):`, err);
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <div class="empty-state-title">Screen load nahi ho saki</div>
        <div class="empty-state-desc">${esc(err.message)}</div>
      </div>
    `;
  }
}

// ─── Sidebar Rendering ────────────────────────────────────────────────────────

/**
 * Sidebar build karo with pill counts
 * @param {object} bootstrapData
 */
export function buildSidebar(bootstrapData) {
  const navEl = document.getElementById('nav-list');
  if (!navEl) return;

  const role      = get('role');
  const pills     = _getPillCounts(bootstrapData);
  let   lastSection = null;

  navEl.innerHTML = NAV_ITEMS
    .filter(item => item.roles.includes('*') || item.roles.includes(role))
    .map(item => {
      let sectionHtml = '';
      if (item.section !== lastSection) {
        lastSection = item.section;
        sectionHtml = item.section
          ? `<li class="sidebar-section-label">${esc(item.section)}</li>`
          : '';
      }
      const count = pills[item.key] ?? '';
      return `${sectionHtml}
        <li>
          <button class="sidebar-nav-item" data-tab="${esc(item.key)}"
                  aria-current="${get('tab') === item.key ? 'page' : 'false'}">
            <span class="sidebar-nav-icon">${item.icon}</span>
            <span class="sidebar-nav-label">${esc(item.label)}</span>
            ${count ? `<span class="sidebar-nav-badge" id="pill-${esc(item.key)}">${count}</span>` : ''}
          </button>
        </li>`;
    })
    .join('');
}

/**
 * Sidebar active state update karo
 * @param {string} activeTab
 */
function _updateSidebarActive(activeTab) {
  document.querySelectorAll('.sidebar-nav-item').forEach(btn => {
    const isActive = btn.dataset.tab === activeTab;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-current', isActive ? 'page' : 'false');
  });
}

/**
 * Page title update karo
 * @param {string} tab
 */
function _updatePageTitle(tab) {
  const item = NAV_ITEMS.find(n => n.key === tab);
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = item?.label ?? 'School ERP';
  document.title = `${item?.label ?? 'ERP'} — ${get('schoolName') || 'School ERP'}`;
}

/**
 * Sidebar pill counts calculate karo from bootstrap data
 * @param {object} d
 * @returns {Record<string, number>}
 */
function _getPillCounts(d) {
  if (!d) return {};
  return {
    school:     (d.school?.students || []).filter(s => s.state === 'done').length,
    fees:       (d.fees?.payslips   || []).filter(p => p.state !== 'paid').length,
    attendance: (d.attendance?.daily || []).filter(a => a.state === 'draft').length,
    assignment: (d.assignment?.student_assignments || []).length,
    timetable:  (d.timetable?.timetables || []).length,
    exam:       (d.exam?.exams || []).length,
    library:    (d.library?.issues || []).filter(i => i.state === 'issue').length,
    event:      (d.event?.events  || []).length,
    hostel:     (d.hostel?.residents || []).length,
    transport:  (d.transport?.participants || []).length,
  };
}

/**
 * Update single pill count (targeted refresh ke baad)
 * @param {string} tab
 * @param {number} count
 */
export function updatePill(tab, count) {
  const el = document.getElementById(`pill-${tab}`);
  if (el) el.textContent = count > 0 ? String(count) : '';
}

// ─── Initialization ───────────────────────────────────────────────────────────

/**
 * Router initialize karo — hash change, sidebar clicks, keyboard nav
 */
export function initRouter() {
  // Sidebar click delegation
  document.getElementById('nav-list')?.addEventListener('click', e => {
    const btn = e.target.closest('[data-tab]');
    if (btn) navigateTo(btn.dataset.tab);
  });

  // Hash change (browser back/forward — rare in desktop app, but handle it)
  window.addEventListener('hashchange', () => {
    const hash = location.hash.slice(1);
    if (hash && _screenRenderers.has(hash)) {
      set({ tab: hash });
      _renderActiveScreen();
      _updateSidebarActive(hash);
      _updatePageTitle(hash);
    }
  });

  // Initial route from hash or default 'dashboard'
  const initialTab = location.hash.slice(1) || 'dashboard';
  set({ tab: initialTab });
  _updatePageTitle(initialTab);

  // State change pe re-render (when tab changes programmatically)
  subscribe('tab', () => {
    _renderActiveScreen();
    _updateSidebarActive(get('tab'));
    _updatePageTitle(get('tab'));
  });
}

/**
 * @typedef {Object} NavItem
 * @property {string} key
 * @property {string} label
 * @property {string} icon
 * @property {string[]} roles
 * @property {string|null} section
 */


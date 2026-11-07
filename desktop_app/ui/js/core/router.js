/**
 * router.js — Role-Aware Sidebar & Hash Router (Phase 2 — Section 9.5)
 *
 * Uses geometric stroke SVG icons (core/icons.js) — zero Unicode emojis.
 * Enforces focused 4–7 item navigation per role + Hostel/Transport module toggles.
 */

import { get, set, subscribe } from './state.js';
import { esc } from './dom.js';
import { icon } from './icons.js';

export const NAV_ITEMS = [
  { key: 'dashboard',  label: 'Overview',        iconName: 'dashboard',  roles: ['*'], section: null },
  { key: 'school',     label: 'Students',        iconName: 'users',      roles: ['admin', 'principal', 'front_desk', 'fee_clerk', 'teacher', 'exam_incharge'], section: 'Academic' },
  { key: 'attendance', label: 'Attendance',      iconName: 'attendance', roles: ['admin', 'principal', 'teacher', 'front_desk'], section: 'Academic' },
  { key: 'fees',       label: 'Fees & Billing',  iconName: 'fees',       roles: ['admin', 'principal', 'fee_clerk'], section: 'Finance' },
  { key: 'exam',       label: 'Exams & Results', iconName: 'exam',       roles: ['admin', 'principal', 'teacher', 'exam_incharge'], section: 'Academic' },
  { key: 'assignment', label: 'Assignments',     iconName: 'assignment', roles: ['admin', 'principal', 'teacher'], section: 'Academic' },
  { key: 'timetable',  label: 'Timetable',       iconName: 'timetable',  roles: ['admin', 'principal', 'teacher', 'exam_incharge'], section: 'Academic' },
  { key: 'library',    label: 'Library',         iconName: 'library',    roles: ['admin', 'principal'], section: 'Campus' },
  { key: 'hostel',     label: 'Hostel',          iconName: 'hostel',     roles: ['admin', 'principal'], prefKey: 'enable_hostel', section: 'Campus' },
  { key: 'transport',  label: 'Transport',       iconName: 'transport',  roles: ['admin', 'principal', 'front_desk', 'fee_clerk'], prefKey: 'enable_transport', section: 'Campus' },
  { key: 'event',      label: 'Events',          iconName: 'event',      roles: ['admin', 'principal', 'front_desk'], section: 'Campus' },
  { key: 'settings',   label: 'Settings',        iconName: 'settings',   roles: ['admin', 'principal'], section: 'System' },
];

const EXTRA_TITLES = {
  student360: 'Student 360° Profile',
};

const _screenRenderers = new Map();

export function registerScreen(tabKey, renderFn) {
  _screenRenderers.set(tabKey, renderFn);
}

export function isTabAllowed(tabKey) {
  if (tabKey === 'student360') return true;
  const role = get('role') || 'admin';
  const prefs = get('preferences') || {};
  const item = NAV_ITEMS.find(n => n.key === tabKey);
  if (!item) return false;
  if (item.prefKey && prefs[item.prefKey] === false) return false;
  return item.roles.includes('*') || item.roles.includes(role);
}

export function navigateTo(tab, extraState = {}) {
  const target = isTabAllowed(tab) ? tab : 'dashboard';
  set({ tab: target, filter: '', ...extraState });
  history.replaceState(null, '', `#${target}`);
  _renderActiveScreen();
  _updateSidebarActive(target);
  _updatePageTitle(target);
}

async function _renderActiveScreen() {
  const tab       = get('tab');
  const container = document.getElementById('main-view');
  if (!container) return;

  const renderer = _screenRenderers.get(tab);
  if (!renderer) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">${icon('folder', 40)}</div>
        <div class="empty-state-title">Module unavailable</div>
        <div class="empty-state-desc">Select an active workspace from the left navigation.</div>
      </div>`;
    return;
  }

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
        <div class="empty-state-icon">${icon('alert', 40)}</div>
        <div class="empty-state-title">Unable to load screen</div>
        <div class="empty-state-desc">${esc(err.message)}</div>
      </div>`;
  }
}

export function buildSidebar(bootstrapData) {
  const navEl = document.getElementById('nav-list');
  if (!navEl) return;

  const role  = get('role') || 'admin';
  const prefs = get('preferences') || {};
  const pills = _getPillCounts(bootstrapData);
  let lastSection = null;

  navEl.innerHTML = NAV_ITEMS
    .filter(item => {
      if (item.prefKey && prefs[item.prefKey] === false) return false;
      return item.roles.includes('*') || item.roles.includes(role);
    })
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
          <button class="sidebar-nav-item ${get('tab') === item.key ? 'active' : ''}"
                  data-tab="${esc(item.key)}"
                  aria-current="${get('tab') === item.key ? 'page' : 'false'}">
            <span class="sidebar-nav-icon">${icon(item.iconName, 16)}</span>
            <span class="sidebar-nav-label">${esc(item.label)}</span>
            ${count ? `<span class="sidebar-nav-badge" id="pill-${esc(item.key)}">${count}</span>` : ''}
          </button>
        </li>`;
    })
    .join('');
}

function _updateSidebarActive(activeTab) {
  const matchTab = activeTab === 'student360' ? 'school' : activeTab;
  document.querySelectorAll('.sidebar-nav-item').forEach(btn => {
    const isActive = btn.dataset.tab === matchTab;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-current', isActive ? 'page' : 'false');
  });
}

function _updatePageTitle(tab) {
  const item = NAV_ITEMS.find(n => n.key === tab);
  const label = item?.label ?? EXTRA_TITLES[tab] ?? 'School ERP';
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = label;
  document.title = `${label} — ${get('schoolName') || 'School ERP'}`;
}

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

export function updatePill(tab, count) {
  const el = document.getElementById(`pill-${tab}`);
  if (el) el.textContent = count > 0 ? String(count) : '';
}

export function initRouter() {
  document.getElementById('nav-list')?.addEventListener('click', e => {
    const btn = e.target.closest('[data-tab]');
    if (btn) navigateTo(btn.dataset.tab);
  });

  window.addEventListener('hashchange', () => {
    const hash = location.hash.slice(1);
    if (hash && _screenRenderers.has(hash) && isTabAllowed(hash)) {
      set({ tab: hash });
      _renderActiveScreen();
      _updateSidebarActive(hash);
      _updatePageTitle(hash);
    }
  });
}

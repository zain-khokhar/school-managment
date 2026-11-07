/**
 * screens/timetable/weekly-grid.js — Weekly 2D Timetable Grid, Today's Live Strip & Substitutions (G8, TT-1..4)
 *
 * Implements ADVANCEMENT_PLAN.md Section 9.8(H):
 *   - TT-1: View Switcher (Class / Teacher filter, "+ New Period", Short/Ramazan Bell indicator)
 *   - TT-2: Today's Live Strip with 1-click Substitute Teacher assignment
 *   - TT-3: 6-Day Weekly 2D Matrix Grid (Monday–Saturday)
 *   - TT-4: Automatic overlap/collision enforcement via `timetable_service.py`
 */

import { apiGet, apiPost } from '../../core/api.js';
import { get, getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { icon } from '../../core/icons.js';
import { renderCalendarSubTab } from './calendar-panel.js';

let _ttTab = 'grid';
let _selectedClassId = '';
let _selectedTeacherId = '';

export async function renderTimetableScreen() {
  const boot = getBootstrap();
  const classes = boot?.school?.standards || [];
  if (!_selectedClassId && classes[0]?.id) {
    _selectedClassId = String(classes[0].id);
  }
  const canManage = ['admin', 'principal', 'exam_incharge'].includes(get('role') || 'admin');

  const html = `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Timetable, Substitutions &amp; Academic Calendar</div>
        <div class="page-header-desc">Weekly 2D period matrix, daily teacher substitutions &amp; holiday-aware bell schedules</div>
      </div>
      <div class="page-header-actions">
        ${canManage ? `<button type="button" class="btn btn-primary" id="tt-btn-add-slot">${icon('plus', 15)} Add Period Slot</button>` : ''}
      </div>
    </div>

    <div class="panel">
      <div class="tab-bar" role="tablist">
        <button type="button" class="tab-btn ${_ttTab === 'grid' ? 'active' : ''}" data-tt-tab="grid">Weekly 2D Grid &amp; Today's Periods</button>
        <button type="button" class="tab-btn ${_ttTab === 'calendar' ? 'active' : ''}" data-tt-tab="calendar">Academic Calendar &amp; Holidays (S6)</button>
      </div>
      <div id="tt-workspace-body">${_ttTab === 'calendar' ? renderCalendarSubTab() : _renderGridContainer()}</div>
    </div>`;

  setTimeout(_bindTimetableEvents, 20);
  return html;
}

function _renderGridContainer() {
  const boot     = getBootstrap();
  const classes  = boot?.school?.standards || [];
  const teachers = boot?.school?.teachers || [];
  const clsOpts  = classes.map(c => `<option value="${esc(c.id)}" ${String(c.id) === String(_selectedClassId) ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  const tchOpts  = teachers.map(t => `<option value="${esc(t.id)}" ${String(t.id) === String(_selectedTeacherId) ? 'selected' : ''}>${esc(t.name)}</option>`).join('');

  setTimeout(_loadTodayAndWeeklyGrid, 25);

  return `
    <!-- TT-1: View Switcher & Filters -->
    <div class="fees-filter-bar" style="justify-content:space-between;">
      <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        <select class="form-control" id="tt-filter-class" style="min-width:170px;">
          <option value="">All Classes</option>${clsOpts}
        </select>
        <select class="form-control" id="tt-filter-teacher" style="min-width:180px;">
          <option value="">All Faculty</option>${tchOpts}
        </select>
        <span class="badge badge-info" id="tt-bell-badge">Regular Bell Timings</span>
      </div>
    </div>

    <!-- TT-2: Today's Live Strip & Substitutions -->
    <div class="panel-body" id="tt-today-strip" style="border-bottom:1px solid var(--rule-line); background:var(--surface-sunken, #FAF8F5);"></div>

    <!-- TT-3: Weekly 2D Grid -->
    <div class="table-wrap" id="tt-weekly-wrap">
      <div class="panel-body">${Array(5).fill('<div class="skeleton skeleton-row" style="margin-bottom:4px;"></div>').join('')}</div>
    </div>`;
}

async function _loadTodayAndWeeklyGrid() {
  const wrap  = document.getElementById('tt-weekly-wrap');
  const strip = document.getElementById('tt-today-strip');
  if (!wrap) return;

  try {
    const [todayRes, gridRes] = await Promise.all([
      apiGet('/api/timetable/today', { class_id: _selectedClassId }),
      apiGet('/api/timetable/weekly-grid', { class_id: _selectedClassId, teacher_id: _selectedTeacherId }),
    ]);

    const bellBadge = document.getElementById('tt-bell-badge');
    if (bellBadge) {
      bellBadge.textContent = gridRes.bell_schedule === 'short_seasonal'
        ? 'Short / Ramazan Bell Schedule Active'
        : 'Regular Bell Schedule';
    }

    if (strip) _renderTodayStrip(strip, todayRes);
    _renderWeeklyMatrix(wrap, gridRes);
  } catch (err) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">Unable to load timetable</div><div class="empty-state-desc">${esc(err.message)}</div></div>`;
  }
}

function _renderTodayStrip(stripEl, todayRes) {
  const canSub = ['admin', 'principal', 'exam_incharge'].includes(get('role') || 'admin');
  if (todayRes.holiday) {
    stripEl.innerHTML = `<div style="font-weight:600; color:var(--warn-text);">
      Scheduled Holiday Today (${esc(todayRes.date)}): ${esc(todayRes.holiday.title)} — No regular periods.
    </div>`;
    return;
  }
  const periods = todayRes.periods || [];
  if (!periods.length) {
    stripEl.innerHTML = `<div style="font-size:13px; color:var(--siyahi-soft);">
      <strong>Today's Live Schedule (${esc(todayRes.week_day)}):</strong> No periods scheduled for this filter today.
    </div>`;
    return;
  }

  const cards = periods.map(p => `
    <div class="tally-mode-card" style="padding:10px 12px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="num" style="font-size:11.5px; font-weight:700; color:var(--siyahi-soft);">${esc(p.start_time)}:00–${esc(p.end_time)}:00</span>
        <span class="badge badge-neutral">${esc(p.class_name)}</span>
      </div>
      <div style="font-weight:600; margin-top:4px;">${esc(p.subject_name)}</div>
      <div style="font-size:12px; color:var(--siyahi-soft); margin-top:2px;">
        ${p.substitute_teacher_name
          ? `<span style="color:var(--warn-text); font-weight:600;">Sub: ${esc(p.substitute_teacher_name)}</span> (for ${esc(p.teacher_name)})`
          : `Teacher: ${esc(p.teacher_name || '—')}`}
      </div>
      ${canSub ? `<button type="button" class="btn btn-xs btn-secondary" style="margin-top:6px;" data-sub-line="${esc(p.line_id)}" data-sub-subject="${esc(p.subject_name)}">Assign Substitute</button>` : ''}
    </div>`).join('');

  stripEl.innerHTML = `
    <div style="font-size:12.5px; font-weight:700; text-transform:uppercase; color:var(--siyahi-soft); margin-bottom:8px;">
      Today's Periods &amp; Substitution Desk (${esc(todayRes.week_day)} • ${esc(todayRes.date)})
    </div>
    <div class="tally-mode-grid" style="margin-bottom:0;">${cards}</div>`;

  stripEl.querySelectorAll('[data-sub-line]').forEach(btn => {
    btn.addEventListener('click', () => _openSubstituteModal(btn.getAttribute('data-sub-line'), btn.getAttribute('data-sub-subject'), todayRes.date));
  });
}

function _renderWeeklyMatrix(wrapEl, gridRes) {
  const days = gridRes.days || ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
  const grid = gridRes.grid || {};

  const colsHtml = days.map(day => {
    const items = grid[day] || [];
    const slots = items.map(ln => `
      <div style="border:1px solid var(--rule-line); border-radius:var(--radius-inner); padding:8px 10px; margin-bottom:8px; background:var(--surface);">
        <div class="num" style="font-size:11px; font-weight:700; color:var(--siyahi-soft);">${esc(ln.time_label)}</div>
        <div style="font-weight:600; font-size:13px; margin-top:2px;">${esc(ln.subject_name)}</div>
        <div style="font-size:12px; color:var(--siyahi-soft);">${esc(ln.teacher_name || '—')} • ${esc(ln.class_name)}</div>
      </div>`).join('') || `<div style="font-size:12px; color:var(--siyahi-soft); padding:10px 0;">No periods</div>`;

    return `
      <td style="vertical-align:top; min-width:165px; padding:12px;">
        ${slots}
      </td>`;
  }).join('');

  wrapEl.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>${days.map(d => `<th style="text-transform:capitalize;">${esc(d)}</th>`).join('')}</tr>
      </thead>
      <tbody><tr>${colsHtml}</tr></tbody>
    </table>`;
}

function _bindTimetableEvents() {
  document.querySelectorAll('[data-tt-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      _ttTab = btn.getAttribute('data-tt-tab');
      document.querySelectorAll('[data-tt-tab]').forEach(b => b.classList.toggle('active', b === btn));
      const body = document.getElementById('tt-workspace-body');
      if (body) {
        body.innerHTML = _ttTab === 'calendar' ? renderCalendarSubTab() : _renderGridContainer();
        _bindGridFilterControls();
      }
    });
  });
  document.getElementById('tt-btn-add-slot')?.addEventListener('click', _openAddPeriodModal);
  _bindGridFilterControls();
}

function _bindGridFilterControls() {
  document.getElementById('tt-filter-class')?.addEventListener('change', e => {
    _selectedClassId = e.target.value;
    _loadTodayAndWeeklyGrid();
  });
  document.getElementById('tt-filter-teacher')?.addEventListener('change', e => {
    _selectedTeacherId = e.target.value;
    _loadTodayAndWeeklyGrid();
  });
}

function _openSubstituteModal(lineId, subjectName, dateIso) {
  const teachers = getBootstrap()?.school?.teachers || [];
  const opts = teachers.map(t => `<option value="${esc(t.id)}">${esc(t.name)} (${esc(t.department || 'Faculty')})</option>`).join('');
  openModal(`Assign Substitute Teacher — ${subjectName}`, `
    <div class="form-group">
      <label class="form-label required" for="sub-tch">Substitute Teacher</label>
      <select class="form-control" id="sub-tch" required>${opts}</select>
    </div>
    <div class="form-group">
      <label class="form-label" for="sub-reason">Reason</label>
      <input class="form-control" id="sub-reason" placeholder="e.g. Teacher on casual leave" />
    </div>
  `, async () => {
    await apiPost('/api/timetable/substitutions', {
      date:                  dateIso,
      line_id:               parseInt(lineId, 10),
      substitute_teacher_id: parseInt(document.getElementById('sub-tch')?.value, 10),
      reason:                document.getElementById('sub-reason')?.value?.trim() || '',
    });
    closeModal();
    toast('Substitute teacher assigned for today', 'success');
    _loadTodayAndWeeklyGrid();
  }, { submitLabel: 'Assign Substitute' });
}

function _openAddPeriodModal() {
  const boot = getBootstrap();
  const classes  = boot?.school?.standards || [];
  const subjects = boot?.school?.subjects || [];
  const teachers = boot?.school?.teachers || [];
  const rooms    = boot?.school?.classrooms || [];

  openModal('Add Weekly Timetable Period (Clash-Protected)', `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="tts-cls">Class</label>
        <select class="form-control" id="tts-cls">${classes.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="tts-day">Day of Week</label>
        <select class="form-control" id="tts-day">
          <option value="monday">Monday</option><option value="tuesday">Tuesday</option>
          <option value="wednesday">Wednesday</option><option value="thursday">Thursday</option>
          <option value="friday">Friday</option><option value="saturday">Saturday</option>
        </select>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="tts-sub">Subject</label>
        <select class="form-control" id="tts-sub">${subjects.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}</select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="tts-tch">Teacher</label>
        <select class="form-control" id="tts-tch">${teachers.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}</select>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="tts-start">Start Hour (24h)</label>
        <input class="form-control num" id="tts-start" type="number" step="0.5" value="11" required />
      </div>
      <div class="form-group">
        <label class="form-label required" for="tts-end">End Hour (24h)</label>
        <input class="form-control num" id="tts-end" type="number" step="0.5" value="12" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="tts-room">Classroom</label>
        <select class="form-control" id="tts-room"><option value="">Default</option>${rooms.map(r => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('')}</select>
      </div>
    </div>
  `, async () => {
    await apiPost('/api/timetable/slot', {
      standard_id:   parseInt(document.getElementById('tts-cls')?.value, 10),
      week_day:      document.getElementById('tts-day')?.value,
      subject_id:    parseInt(document.getElementById('tts-sub')?.value, 10),
      teacher_id:    parseInt(document.getElementById('tts-tch')?.value, 10),
      start_time:    parseFloat(document.getElementById('tts-start')?.value),
      end_time:      parseFloat(document.getElementById('tts-end')?.value),
      class_room_id: document.getElementById('tts-room')?.value || null,
    });
    closeModal();
    toast('Period added to timetable', 'success');
    _loadTodayAndWeeklyGrid();
  }, { submitLabel: 'Save Period Slot' });
}

/**
 * screens/timetable/calendar-panel.js — Academic Calendar & Pakistani Holiday Preset (G21, S6)
 *
 * Extracted from weekly-grid.js so every timetable module stays <= 200 lines.
 */

import { apiGet, apiPost } from '../../core/api.js';
import { get } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { formatDate } from '../../core/format.js';
import { icon } from '../../core/icons.js';

export function renderCalendarSubTab() {
  const canEdit = ['admin', 'principal', 'exam_incharge'].includes(get('role') || 'admin');
  setTimeout(_loadCalendarRows, 25);

  return `
    <div class="fees-filter-bar" style="justify-content:space-between;">
      <div>
        <strong>Academic Calendar &amp; Scheduled Off-Days (S6)</strong>
        <div style="font-size:12px; color:var(--siyahi-soft);">Daily attendance is automatically blocked on scheduled off-day holidays</div>
      </div>
      ${canEdit ? `
        <div style="display:flex; gap:8px;">
          <button type="button" class="btn btn-secondary btn-sm" id="cal-btn-preset">${icon('download', 14)} Load Pakistani Holidays Preset</button>
          <button type="button" class="btn btn-primary btn-sm" id="cal-btn-add">${icon('plus', 14)} Add Calendar Day</button>
        </div>` : ''}
    </div>
    <div class="table-wrap" id="cal-table-wrap">
      <div class="panel-body">${Array(4).fill('<div class="skeleton skeleton-row" style="margin-bottom:4px;"></div>').join('')}</div>
    </div>`;
}

async function _loadCalendarRows() {
  const wrap = document.getElementById('cal-table-wrap');
  if (!wrap) return;
  const canEdit = ['admin', 'principal', 'exam_incharge'].includes(get('role') || 'admin');

  document.getElementById('cal-btn-preset')?.addEventListener('click', async () => {
    const res = await apiPost('/api/calendar/preset-pakistani', { year: new Date().getFullYear() });
    toast(`Loaded ${res.created_count} national holiday(s)`, 'success');
    _loadCalendarRows();
  });

  document.getElementById('cal-btn-add')?.addEventListener('click', _openAddCalendarModal);

  try {
    const res = await apiGet('/api/calendar/days');
    const items = res.items || [];
    wrap.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Title / Occasion</th>
            <th>Category</th>
            <th>Attendance Status</th>
            <th>Bell Profile</th>
            ${canEdit ? '<th>Action</th>' : ''}
          </tr>
        </thead>
        <tbody>
          ${items.map(d => `
            <tr>
              <td class="num" style="font-weight:600;">${esc(formatDate(d.date))}</td>
              <td style="font-weight:500;">${esc(d.title)}</td>
              <td><span class="badge badge-info" style="text-transform:capitalize;">${esc(d.day_type)}</span></td>
              <td><span class="badge ${d.is_off_day ? 'badge-warn' : 'badge-neutral'}">${d.is_off_day ? 'Off-Day (Attendance Blocked)' : 'Working Day'}</span></td>
              <td style="text-transform:capitalize;">${esc(d.bell_profile)}</td>
              ${canEdit ? `<td><button type="button" class="btn btn-xs btn-secondary" data-cal-del="${esc(d.id)}">Remove</button></td>` : ''}
            </tr>`).join('') || `<tr><td colspan="6" style="padding:20px; text-align:center;">No calendar holidays configured yet — click "Load Pakistani Holidays Preset".</td></tr>`}
        </tbody>
      </table>`;

    wrap.querySelectorAll('[data-cal-del]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const dayId = btn.dataset.calDel;
        await apiPost(`/api/calendar/days/${dayId}/delete`, {});
        toast('Calendar entry removed', 'info');
        _loadCalendarRows();
      });
    });
  } catch (err) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">Unable to load calendar</div><div class="empty-state-desc">${esc(err.message)}</div></div>`;
  }
}

function _openAddCalendarModal() {
  const today = new Date().toISOString().slice(0, 10);
  openModal('Add Academic Calendar Day / Holiday', `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="cd-date">Date</label>
        <input class="form-control" id="cd-date" type="date" value="${today}" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="cd-type">Category</label>
        <select class="form-control" id="cd-type">
          <option value="holiday">Public / School Holiday</option>
          <option value="ramazan">Ramazan Schedule Day</option>
          <option value="vacation">Seasonal Vacation</option>
          <option value="ptm">Parent-Teacher Meeting (PTM)</option>
          <option value="exam_day">Examination Day</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label required" for="cd-title">Occasion / Title</label>
      <input class="form-control" id="cd-title" placeholder="e.g. Eid-ul-Fitr Holiday" required />
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label" for="cd-bell">Bell Schedule Profile</label>
        <select class="form-control" id="cd-bell">
          <option value="regular">Regular Timings</option>
          <option value="ramazan">Ramazan Short Bell</option>
          <option value="winter">Winter Timings</option>
        </select>
      </div>
      <div class="form-group" style="display:flex; align-items:center; gap:8px; padding-top:22px;">
        <input type="checkbox" id="cd-off" checked style="width:17px; height:17px;" />
        <label for="cd-off" style="font-size:13px; font-weight:500;">School Off-Day (Block Roll-Call)</label>
      </div>
    </div>
  `, async () => {
    await apiPost('/api/calendar/days', {
      date:         document.getElementById('cd-date')?.value,
      day_type:     document.getElementById('cd-type')?.value,
      title:        document.getElementById('cd-title')?.value?.trim(),
      bell_profile: document.getElementById('cd-bell')?.value,
      is_off_day:   Boolean(document.getElementById('cd-off')?.checked),
    });
    closeModal();
    toast('Academic calendar updated', 'success');
    _loadCalendarRows();
  }, { submitLabel: 'Save Calendar Day' });
}

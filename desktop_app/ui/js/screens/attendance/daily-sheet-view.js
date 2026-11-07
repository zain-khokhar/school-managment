/**
 * attendance/daily-sheet-view.js — Pure HTML Builders for Daily Roll-Call Screen (Phase 1/2)
 *
 * Uses geometric stroke SVG icons (core/icons.js) and calm paper/ink roll-call styling.
 */

import { esc } from '../../core/dom.js';
import { formatDate } from '../../core/format.js';
import { icon } from '../../core/icons.js';

export function buildAttendanceShellHtml(classes) {
  if (!classes.length) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">${icon('attendance', 42)}</div>
        <div class="empty-state-title">No classes configured</div>
        <div class="empty-state-desc">
          Configure classes under Students before taking daily attendance.
        </div>
      </div>`;
  }

  const today = new Date().toLocaleDateString('en-PK', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  const classOptions = classes
    .map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`)
    .join('');

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Daily Attendance</div>
        <div class="page-header-desc">${esc(today)}</div>
      </div>
      <div class="page-header-actions">
        <a class="btn btn-secondary btn-sm" href="/api/attendance/export-xlsx" target="_blank">
          ${icon('download', 14)} Export 31-Day Sheet (.xlsx)
        </a>
      </div>
    </div>

    <div class="panel" id="att-class-selector">
      <div class="panel-header">
        <div class="panel-title">Select Class for Roll Call</div>
      </div>
      <div class="panel-body">
        <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
          <div class="form-group" style="flex:1; min-width:200px; margin-bottom:0;">
            <label class="form-label required" for="att-class-select">Class</label>
            <select class="form-control" id="att-class-select">
              <option value="">— Choose Class —</option>
              ${classOptions}
            </select>
          </div>
          <button class="btn btn-primary" id="att-load-btn" disabled>
            Open Roll Call ${icon('arrow-right', 14)}
          </button>
        </div>
        <p id="att-class-hint" class="form-hint" style="margin-top:8px;">
          All students default to Present — tap only the Absent exceptions and submit.
        </p>
      </div>
    </div>

    <div id="att-sheet-container"></div>
  `;
}

export function buildSheetHtml(att, className, lines) {
  const isValidated = att.state === 'validate';
  const present = lines.filter(l => l.is_present).length;
  const absent  = lines.filter(l => l.is_absent).length;
  const total   = lines.length;

  const rowsHtml = lines.map(line => buildStudentRowHtml(line, isValidated)).join('');

  return `
    <div class="panel" id="att-sheet-panel">
      <div class="panel-header">
        <div class="panel-title">
          ${esc(className)} — ${esc(formatDate(att.date))}
        </div>
        <div class="panel-toolbar">
          ${isValidated
            ? `<span class="badge badge-info">${icon('check', 12)} Validated</span>
               <button class="btn btn-secondary btn-sm" id="att-draft-btn">Reopen Sheet</button>`
            : `<span class="badge badge-warn">Draft • Roll Call Open</span>`}
        </div>
      </div>

      <div class="att-stats-bar">
        <div class="att-stat">
          <div class="att-stat-dot present"></div>
          <span>Present: <strong id="att-count-present" class="num">${present}</strong></span>
        </div>
        <div class="att-stat">
          <div class="att-stat-dot absent"></div>
          <span>Absent: <strong id="att-count-absent" class="num">${absent}</strong></span>
        </div>
        <div class="att-stat">
          <span style="color:var(--siyahi-soft)">Total: <span class="num">${total}</span></span>
        </div>
        ${isValidated ? '' : `
          <div style="margin-left:auto;">
            <button class="btn btn-secondary btn-sm" id="att-mark-all-present">Mark All Present</button>
          </div>`}
      </div>

      <div id="att-roll-list">
        ${rowsHtml || `
          <div class="empty-state" style="min-height:160px;">
            <div class="empty-state-icon">${icon('users', 36)}</div>
            <div class="empty-state-title">No enrolled students in this class</div>
            <div class="empty-state-desc">Admit students into this class from the Students directory.</div>
          </div>`}
      </div>

      ${!isValidated && lines.length ? `
        <div class="att-action-bar">
          <div class="att-action-bar-info">
            <span id="att-modified-count" class="num">0</span> changes —
            <strong id="att-bar-absent" class="num">${absent}</strong> marked Absent
          </div>
          <button class="btn btn-secondary" id="att-undo-btn" disabled>
            ${icon('undo', 14)} Undo
          </button>
          <button class="btn btn-primary" id="att-submit-btn">
            ${icon('check', 15)} Submit Roll Call
          </button>
        </div>` : ''}
    </div>
  `;
}

export function buildStudentRowHtml(line, isValidated) {
  const onLeave   = line.is_absent && !line.present_absentcheck;
  const isPresent = !!line.is_present;
  const isAbsent  = !!line.is_absent;

  return `
    <div class="att-student-row ${onLeave ? 'on-leave' : ''}"
         data-line-id="${esc(line.id)}">
      <div class="att-roll-no">${esc(line.roll_no || '—')}</div>
      <div style="flex:1;">
        <div class="att-student-name">
          ${esc(line.student_name)}${line.last ? ' ' + esc(line.last) : ''}
        </div>
        <div class="att-student-sub">GR: ${esc(line.pid || '—')}</div>
      </div>
      ${onLeave ? '<div class="att-leave-chip">Approved Leave</div>' : ''}
      <div class="att-toggle" role="group"
           aria-label="Attendance: ${esc(line.student_name)}">
        <button
          type="button"
          class="att-toggle-btn present ${isPresent ? 'active' : ''}"
          data-action="present"
          data-line="${esc(line.id)}"
          ${isValidated ? 'disabled' : ''}
          aria-pressed="${isPresent}">
          ${icon('check', 13)} Present
        </button>
        <button
          type="button"
          class="att-toggle-btn absent ${isAbsent ? 'active' : ''}"
          data-action="absent"
          data-line="${esc(line.id)}"
          ${isValidated ? 'disabled' : ''}
          aria-pressed="${isAbsent}">
          ${icon('x', 13)} Absent
        </button>
      </div>
    </div>`;
}

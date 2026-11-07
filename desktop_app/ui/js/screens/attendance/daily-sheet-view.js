/**
 * attendance/daily-sheet-view.js — Pure HTML Builders for Haziri Screen (Phase 1)
 *
 * Separated from daily-sheet.js to keep every JS module under 250 lines.
 * Uses only "Kaghaz aur Siyahi" design tokens.
 */

import { esc } from '../../core/dom.js';
import { formatDate } from '../../core/format.js';

/**
 * Build initial Attendance page shell with Class Selector
 * @param {Array<object>} classes
 * @returns {string}
 */
export function buildAttendanceShellHtml(classes) {
  if (!classes.length) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-title">Koi Class nahi mili</div>
        <div class="empty-state-desc">
          Pehle Students → Classes section mein jaayein aur classes banayein.
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
        <div class="page-header-title">📋 Daily Attendance (Haziri)</div>
        <div class="page-header-desc">${esc(today)}</div>
      </div>
    </div>

    <div class="panel" id="att-class-selector">
      <div class="panel-header">
        <div class="panel-title">Class Select Karein</div>
      </div>
      <div class="panel-body">
        <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
          <div class="form-group" style="flex:1; min-width:200px; margin-bottom:0;">
            <label class="form-label required" for="att-class-select">Class</label>
            <select class="form-control" id="att-class-select">
              <option value="">— Class chunein —</option>
              ${classOptions}
            </select>
          </div>
          <button class="btn btn-primary" id="att-load-btn" disabled>
            Haziri Shuru Karein →
          </button>
        </div>
        <p id="att-class-hint" class="form-hint" style="margin-top:8px;">
          Default sab students Hazir hote hain — sirf Ghair-hazir students par tap karein aur Jama karein.
        </p>
      </div>
    </div>

    <div id="att-sheet-container"></div>
  `;
}

/**
 * Build the Roll-Call Sheet HTML
 * @param {object} att
 * @param {string} className
 * @param {Array<object>} lines
 * @returns {string}
 */
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
            ? `<span class="badge badge-success">✓ Validated</span>
               <button class="btn btn-secondary btn-sm" id="att-draft-btn">
                 Reset to Draft
               </button>`
            : `<span class="badge badge-warn">Draft • Roll Call Open</span>`}
        </div>
      </div>

      <div class="att-stats-bar">
        <div class="att-stat">
          <div class="att-stat-dot present"></div>
          <span>Hazir: <strong id="att-count-present">${present}</strong></span>
        </div>
        <div class="att-stat">
          <div class="att-stat-dot absent"></div>
          <span>Ghair-hazir: <strong id="att-count-absent">${absent}</strong></span>
        </div>
        <div class="att-stat">
          <span style="color:var(--siyahi-soft)">Kul: ${total}</span>
        </div>
        ${isValidated ? '' : `
          <div style="margin-left:auto;">
            <button class="btn btn-secondary btn-sm" id="att-mark-all-present">
              Sab Hazir
            </button>
          </div>`}
      </div>

      <div id="att-roll-list">
        ${rowsHtml || `
          <div class="empty-state" style="min-height:160px;">
            <div class="empty-state-icon">👥</div>
            <div class="empty-state-title">Is class mein koi student nahi</div>
            <div class="empty-state-desc">Students tab mein jaayein aur students admit karein.</div>
          </div>`}
      </div>

      ${!isValidated && lines.length ? `
        <div class="att-action-bar">
          <div class="att-action-bar-info">
            <span id="att-modified-count">0</span> tabdeeliyan —
            <strong id="att-bar-absent">${absent}</strong> ghair-hazir
          </div>
          <button class="btn btn-secondary" id="att-undo-btn" disabled>
            ↩ Undo
          </button>
          <button class="btn btn-primary" id="att-submit-btn">
            ✓ Haziri Jama Karein
          </button>
        </div>` : ''}
    </div>
  `;
}

/**
 * Build a single student row in the roll-call grid
 * @param {object} line
 * @param {boolean} isValidated
 * @returns {string}
 */
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
      ${onLeave ? '<div class="att-leave-chip">Chhutti Approved</div>' : ''}
      <div class="att-toggle" role="group"
           aria-label="Haziri: ${esc(line.student_name)}">
        <button
          type="button"
          class="att-toggle-btn present ${isPresent ? 'active' : ''}"
          data-action="present"
          data-line="${esc(line.id)}"
          ${isValidated ? 'disabled' : ''}
          aria-pressed="${isPresent}">
          ✓ Hazir
        </button>
        <button
          type="button"
          class="att-toggle-btn absent ${isAbsent ? 'active' : ''}"
          data-action="absent"
          data-line="${esc(line.id)}"
          ${isValidated ? 'disabled' : ''}
          aria-pressed="${isAbsent}">
          ✗ Ghair-hazir
        </button>
      </div>
    </div>`;
}


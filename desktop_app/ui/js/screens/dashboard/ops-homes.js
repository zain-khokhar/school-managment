/**
 * screens/dashboard/ops-homes.js — Front Desk & Exam In-Charge Homes (Phase 2 — G9)
 *
 * Extracted from role-homes.js so every dashboard module stays <= 200 lines.
 */

import { esc } from '../../core/dom.js';
import { stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';

export function renderFrontDeskHome(d) {
  const k     = d.kpis || {};
  const seats = d.seat_meter || [];
  const inc   = d.incomplete_admissions || [];

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Today's Overview — Admissions &amp; Front Desk</div>
        <div class="page-header-desc">Live class seat availability &amp; incomplete admission queue</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-secondary" data-role-goto="school">${icon('users', 15)} Student Directory</button>
        <button class="btn btn-primary" id="fd-new-admission">${icon('plus', 15)} New Admission</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Admissions Today</div>
        <div class="kpi-value num">${esc(k.admissions_today || 0)}</div>
        <div class="kpi-sub">Recorded today</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Available Seats</div>
        <div class="kpi-value num">${esc(k.available_seats_total || 0)}</div>
        <div class="kpi-sub">Across ${esc(seats.length)} classes</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Incomplete Records</div>
        <div class="kpi-value num">${esc(k.incomplete_count || 0)}</div>
        <div class="kpi-sub">Draft or missing guardian mobile</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Active Students</div>
        <div class="kpi-value num">${esc(k.active_students || 0)}</div>
        <div class="kpi-sub">Enrolled in session</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1.15fr; gap:var(--sp-5); align-items:start;">
      <div class="panel">
        <div class="panel-header"><div class="panel-title">Live Seat Availability (FD-1)</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Class</th><th class="num">Enrolled</th><th class="num">Free Seats</th></tr></thead>
            <tbody>
              ${seats.map(s => `
                <tr>
                  <td style="font-weight:600;">${esc(s.name || s.class_name)}</td>
                  <td class="num">${esc(s.total_students ?? s.enrolled ?? 0)} / ${esc(s.capacity)}</td>
                  <td class="num">${esc(s.remaining_seats)}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header"><div class="panel-title">Incomplete Admissions Queue (FD-3)</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>GR No.</th><th>Student</th><th>Class</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              ${inc.map(s => `
                <tr>
                  <td class="num">${esc(s.pid)}</td>
                  <td><button type="button" class="btn btn-ghost btn-xs" data-open-s360="${esc(s.id)}" style="font-weight:600; padding:0;">${esc(s.student_name)} ${esc(s.last || '')}</button></td>
                  <td>${esc(s.class_name || '—')}</td>
                  <td><span class="badge ${stateBadgeClass(s.state)}">${esc(stateLabel(s.state))}</span></td>
                  <td>${s.state === 'draft'
                    ? `<button class="btn btn-xs btn-primary" data-fd-admit="${esc(s.id)}">Admit</button>`
                    : `<span style="font-size:12px; color:var(--siyahi-soft);">Missing Mobile</span>`}</td>
                </tr>`).join('') || `<tr><td colspan="5" style="padding:20px; text-align:center;">All admission files complete.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
}

export function renderExamHome(d) {
  const k      = d.exam_kpis || {};
  const matrix = d.marks_matrix || [];
  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Today's Overview — Examination Cell</div>
        <div class="page-header-desc">Marks entry completion, result verification &amp; re-evaluation queue</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-primary" data-role-goto="exam">${icon('exam', 15)} Open Exams &amp; Results</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Active Exams</div>
        <div class="kpi-value num">${esc(k.active_exams || 0)}</div>
        <div class="kpi-sub">Scheduled / running</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Pending Marksheets</div>
        <div class="kpi-value num">${esc(k.pending_results || 0)}</div>
        <div class="kpi-sub">Awaiting confirmation</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Finalized Results</div>
        <div class="kpi-value num">${esc(k.finalized_results || 0)}</div>
        <div class="kpi-sub">Published</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Re-Evaluations</div>
        <div class="kpi-value num">${esc(k.reeval_requests || 0)}</div>
        <div class="kpi-sub">Open requests</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header"><div class="panel-title">Exam Marks Progress Matrix (EX-2)</div></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Exam</th><th>Class</th><th class="num">Finalized</th><th class="num">Pending</th><th class="num">Avg %</th><th>Status</th></tr></thead>
          <tbody>
            ${matrix.map(m => `
              <tr>
                <td style="font-weight:600;">${esc(m.exam_name)}</td>
                <td>${esc(m.class_name)}</td>
                <td class="num">${esc(m.finalized_count || 0)} / ${esc(m.total_results || 0)}</td>
                <td class="num">${esc(m.pending_count || 0)}</td>
                <td class="num">${m.avg_pct !== null ? `${esc(m.avg_pct)}%` : '—'}</td>
                <td><span class="badge ${stateBadgeClass(m.exam_state)}">${esc(stateLabel(m.exam_state))}</span></td>
              </tr>`).join('') || `<tr><td colspan="6" style="padding:20px; text-align:center;">No active exams found.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>`;
}


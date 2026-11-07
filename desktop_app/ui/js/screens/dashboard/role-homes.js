/**
 * screens/dashboard/role-homes.js — Role Home Dispatcher, Teacher & Fee Clerk Homes (Phase 2 — G9)
 *
 * Delegates Front Desk & Exam In-Charge rendering to `ops-homes.js` so every file stays <= 200 lines.
 */

import { apiPost } from '../../core/api.js';
import { esc, toast, confirm } from '../../core/dom.js';
import { formatPKR, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { navigateTo } from '../../core/router.js';
import { openNewStudentModal, performStudentAction } from '../school/student-modal.js';
import { renderFrontDeskHome, renderExamHome } from './ops-homes.js';

export function renderRoleHome(role, d) {
  if (role === 'teacher')       return _renderTeacherHome(d);
  if (role === 'fee_clerk')     return _renderFeeClerkHome(d);
  if (role === 'front_desk')    return renderFrontDeskHome(d);
  if (role === 'exam_incharge') return renderExamHome(d);
  return _renderTeacherHome(d);
}

function _renderTeacherHome(d) {
  const classes      = d.classes_status || d.my_classes || [];
  const periods      = d.today_periods || [];
  const absents      = d.absent_today || [];
  const assignments  = d.assignments_due || d.active_assignments || [];
  const pendingMarks = (d.pending_marks || []).reduce((acc, r) => acc + (r.pending_cnt || 0), 0);

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Aaj Ka Din — Faculty Workspace</div>
        <div class="page-header-desc">Daily roll call, scheduled periods, homework &amp; marks entry</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-secondary" data-role-goto="assignment">${icon('assignment', 15)} Homework</button>
        <button class="btn btn-primary" data-role-goto="attendance">${icon('attendance', 15)} Mark Attendance</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Assigned Classes (T1)</div>
        <div class="kpi-value num">${esc(classes.length)}</div>
        <div class="kpi-sub">${esc(classes.filter(c => !c.att_id).length)} unmarked today</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Scheduled Periods (T2)</div>
        <div class="kpi-value num">${esc(periods.length)}</div>
        <div class="kpi-sub">${esc(d.weekday || 'Today')} timetable</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Pending Marks (T3)</div>
        <div class="kpi-value num">${esc(pendingMarks)}</div>
        <div class="kpi-sub">Draft exam results awaiting completion</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Active Homework (T4)</div>
        <div class="kpi-value num">${esc(assignments.length)}</div>
        <div class="kpi-sub">${esc(absents.length)} students absent today</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1.3fr 1fr; gap:var(--sp-5); align-items:start;">
      <div class="panel">
        <div class="panel-header"><div class="panel-title">My Classes &amp; Today's Roll Call</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Class</th><th class="num">Students</th><th>Roll Call</th><th>Action</th></tr></thead>
            <tbody>
              ${classes.map(c => `
                <tr>
                  <td style="font-weight:600;">${esc(c.name || c.class_name)}</td>
                  <td class="num">${esc(c.total_students ?? c.enrolled ?? 0)}</td>
                  <td>${c.att_id
                    ? `<span class="badge badge-info">${esc(c.total_presence ?? c.present ?? 0)}/${esc(c.total_student ?? 0)} (${esc(stateLabel(c.att_state))})</span>`
                    : `<span class="badge badge-warn">Pending Today</span>`}</td>
                  <td><button class="btn btn-xs btn-primary" data-open-haziri-class="${esc(c.id ?? c.class_id)}">Take Roll Call</button></td>
                </tr>`).join('') || `<tr><td colspan="4" style="padding:20px; text-align:center;">No classes assigned</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header"><div class="panel-title">Today's Periods (${esc(d.weekday || '')})</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Time</th><th>Class</th><th>Subject</th></tr></thead>
            <tbody>
              ${periods.map(p => `
                <tr>
                  <td class="num">${esc(p.start_time)} – ${esc(p.end_time)}</td>
                  <td>${esc(p.class_name)}</td>
                  <td style="font-weight:500;">${esc(p.subject_name)}</td>
                </tr>`).join('') || `<tr><td colspan="3" style="padding:20px; text-align:center; color:var(--siyahi-soft);">No periods scheduled for today</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
}

function _renderFeeClerkHome(d) {
  const t     = d.today_tally || {};
  const slips = d.defaulters || d.open_vouchers || [];

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Aaj Ka Din — Fee Counter &amp; Daily Tally</div>
        <div class="page-header-desc">Quick voucher collection, daily cash tally &amp; overdue balances</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-primary" data-role-goto="fees">${icon('fees', 15)} Open Full Fee Ledger</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Collected Today</div>
        <div class="kpi-value num">${esc(formatPKR(t.today_amount || 0))}</div>
        <div class="kpi-sub">${esc(t.receipts_today ?? t.receipt_count ?? 0)} receipts • Yesterday: ${esc(formatPKR(t.yesterday_amount || 0))}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Outstanding Dues</div>
        <div class="kpi-value num">${esc(formatPKR(t.total_due || 0))}</div>
        <div class="kpi-sub">${esc(slips.length)} unpaid vouchers</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Students With Dues</div>
        <div class="kpi-value num">${esc(t.defaulter_count ?? slips.length)}</div>
        <div class="kpi-sub">Top arrears listed below</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">Open Fee Vouchers (Quick Counter)</div>
          <div class="panel-subtitle">Confirm full receipt or open student 360° fee history</div>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Voucher #</th><th>Student</th><th>Class</th><th class="num">Total</th><th class="num">Due</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            ${slips.map(p => `
              <tr>
                <td class="num" style="color:var(--siyahi-soft);">${esc(p.number || '—')}</td>
                <td><button type="button" class="btn btn-ghost btn-xs" data-open-s360="${esc(p.student_id)}" style="font-weight:600; padding:0;">${esc(p.student_name)} ${esc(p.last || '')}</button></td>
                <td>${esc(p.class_name || '—')}</td>
                <td class="num">${esc(formatPKR(p.total))}</td>
                <td class="num" style="font-weight:600;">${esc(formatPKR(p.due_amount))}</td>
                <td><span class="badge ${stateBadgeClass(p.state)}">${esc(stateLabel(p.state))}</span></td>
                <td><button class="btn btn-xs btn-primary" data-collect-slip="${esc(p.id)}" data-slip-amt="${esc(formatPKR(p.due_amount))}" data-slip-stu="${esc(p.student_name)}">Receive Full</button></td>
              </tr>`).join('') || `<tr><td colspan="7" style="padding:24px; text-align:center;">All issued fee vouchers are settled.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>`;
}

export function attachRoleHomeEvents() {
  document.querySelectorAll('[data-role-goto]').forEach(btn => {
    btn.addEventListener('click', () => navigateTo(btn.getAttribute('data-role-goto')));
  });
  document.querySelectorAll('[data-open-haziri-class]').forEach(btn => {
    btn.addEventListener('click', () => {
      navigateTo('attendance', { selectedClassId: parseInt(btn.getAttribute('data-open-haziri-class'), 10) });
    });
  });
  document.querySelectorAll('[data-open-s360]').forEach(btn => {
    btn.addEventListener('click', () => {
      navigateTo('student360', { selectedStudentId: parseInt(btn.getAttribute('data-open-s360'), 10) });
    });
  });
  document.getElementById('fd-new-admission')?.addEventListener('click', () => {
    openNewStudentModal(() => navigateTo('dashboard'));
  });
  document.querySelectorAll('[data-fd-admit]').forEach(btn => {
    btn.addEventListener('click', () => {
      performStudentAction(parseInt(btn.getAttribute('data-fd-admit'), 10), 'admission_done', btn, () => navigateTo('dashboard'));
    });
  });
  document.querySelectorAll('[data-collect-slip]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id  = parseInt(btn.getAttribute('data-collect-slip'), 10);
      const amt = btn.getAttribute('data-slip-amt');
      const stu = btn.getAttribute('data-slip-stu');
      const ok = await confirm('Confirm Fee Collection', `Receive full payment (${amt}) for ${stu}?`, {
        confirmLabel: 'Confirm Receipt',
        confirmClass: 'btn-primary',
      });
      if (!ok) return;
      btn.disabled = true;
      try {
        await apiPost(`/api/fees/payslips/${id}/action`, { action: 'pay' });
        toast(`Payment recorded for ${stu}`, 'success');
        navigateTo('dashboard');
      } catch (err) {
        toast(err.message, 'error');
        btn.disabled = false;
      }
    });
  });
}

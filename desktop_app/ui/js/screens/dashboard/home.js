/**
 * screens/dashboard/home.js — Role-Aware "Aaj Ka Din" Command Center (Phase 2 — G9, P1..P7)
 *
 * Fetches `/api/dashboard/home` (< 500ms cached SQL aggregation).
 * Dispatches Principal/Admin home directly and delegates Teacher, Fee Clerk,
 * Front Desk, and Exam In-Charge homes to `role-homes.js`.
 */

import { apiGet, apiPost } from '../../core/api.js';
import { set, get } from '../../core/state.js';
import { esc, toast } from '../../core/dom.js';
import { formatPKR, formatDateTime, stateLabel } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { navigateTo } from '../../core/router.js';
import { openNewStudentModal } from '../school/student-modal.js';
import { renderRoleHome, attachRoleHomeEvents } from './role-homes.js';

export async function renderDashboardScreen() {
  const payload = await apiGet('/api/dashboard/home');
  if (payload.backup_health) {
    set({ backupHealth: payload.backup_health });
    window.ERP?.refreshTopbarStatus?.();
  }

  const eff = payload.role || payload.effective_role || 'principal';
  if (eff !== 'principal') {
    const html = renderRoleHome(eff, payload);
    setTimeout(() => attachRoleHomeEvents(eff), 20);
    return html;
  }

  const html = _buildPrincipalHomeHtml(payload);
  setTimeout(_attachPrincipalEvents, 20);
  return html;
}

function _buildPrincipalHomeHtml(d) {
  const cards = d.cards || {};
  const c     = cards.today_collection || d.collection || {};
  const att   = cards.today_attendance || d.attendance || {};
  const due   = cards.fee_dues || d.fee_dues || {};
  const enr   = cards.enrollment || {};
  const chk   = d.checklist || null;
  const schoolName = get('schoolName') || 'School ERP';
  const curYear    = get('currentYear')?.name || 'Current Session';
  const todayLabel = new Date().toLocaleDateString('en-PK', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  const chkDone  = chk ? (chk.completed ?? chk.completed_count ?? 0) : 0;
  const chkTotal = chk ? (chk.total ?? chk.total_count ?? 5) : 5;
  const checklistBanner = chk && !chk.dismissed && chkDone < chkTotal ? `
    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">School Setup Checklist (${chkDone}/${chkTotal} Completed)</div>
          <div class="panel-subtitle">Complete initial setup steps so daily operations run smoothly</div>
        </div>
        <button class="btn btn-secondary btn-sm" data-dash-goto="settings">Open Settings</button>
      </div>
      <div class="panel-body">
        <div class="checklist-strip">
          ${(chk.steps || []).map(s => `
            <button type="button" class="checklist-step ${s.done ? 'done' : ''}" data-dash-goto="${esc(s.target_tab || s.tab || 'settings')}">
              <span>${icon(s.done ? 'check' : 'arrow-right', 15)}</span>
              <span class="truncate">${esc(s.title || s.label)}</span>
            </button>`).join('')}
        </div>
      </div>
    </div>` : '';

  const attentionItems = (d.attention_items || []).map(item => `
    <div class="attention-row">
      <div>
        <div style="font-weight:600; font-size:13.5px; color:var(--siyahi);">${esc(item.title)}</div>
        <div style="font-size:12px; color:var(--siyahi-soft);">${esc(item.detail || item.sub || '')}</div>
      </div>
      <div style="display:flex; gap:6px; align-items:center;">
        <span class="badge ${item.severity === 'warn' ? 'badge-warn' : 'badge-neutral'}">
          ${item.severity === 'warn' ? 'Action Needed' : 'Notice'}
        </span>
        ${item.type === 'backup_stale' || item.type === 'backup_overdue'
          ? `<button class="btn btn-xs btn-primary" id="dash-quick-backup">${icon('database', 13)} Backup Now</button>`
          : `<button class="btn btn-xs btn-secondary" data-dash-goto="${esc(item.action_tab || 'dashboard')}">${esc(item.action_label || 'Open')}</button>`}
      </div>
    </div>`).join('');

  const leaveRows = (d.pending_leaves || []).map(lv => `
    <div class="attention-row">
      <div>
        <div style="font-weight:600;">${esc(lv.student_name)} ${esc(lv.last || '')} <span style="font-weight:400; color:var(--siyahi-soft);">(${esc(lv.class_name || '—')})</span></div>
        <div style="font-size:12px; color:var(--siyahi-soft);">${esc(lv.start_date)} to ${esc(lv.end_date)} (${esc(lv.days)}d) — ${esc(lv.reason || 'Leave request')}</div>
      </div>
      <div style="display:flex; gap:6px;">
        <button class="btn btn-xs btn-primary" data-leave-id="${esc(lv.id)}" data-leave-act="approve">Approve</button>
        <button class="btn btn-xs btn-secondary" data-leave-id="${esc(lv.id)}" data-leave-act="reject">Reject</button>
      </div>
    </div>`).join('');

  const classRows = (d.class_strip || []).map(cls => {
    const cid  = cls.id ?? cls.class_id;
    const name = cls.name || cls.class_name;
    const cap  = cls.capacity || 35;
    const cnt  = cls.total_students ?? cls.enrolled ?? 0;
    const free = Math.max(0, cap - cnt);
    const fill = Math.min(100, Math.round((cnt / cap) * 100));
    const marked = Boolean(cls.att_id);
    const pres = cls.att_present ?? cls.present ?? 0;
    const tot  = cls.att_total ?? cls.total_student ?? 0;
    const attChip = marked
      ? `<span class="badge ${cls.att_state === 'validate' ? 'badge-info' : 'badge-neutral'}">${esc(pres)}/${esc(tot)} (${esc(stateLabel(cls.att_state))})</span>`
      : `<span class="badge badge-warn">Unmarked</span>`;

    return `
      <tr>
        <td style="font-weight:600;">${esc(name)}</td>
        <td>${esc(cls.teacher_name || 'Unassigned')}</td>
        <td class="num">${esc(cnt)} / ${esc(cap)}</td>
        <td>
          <div style="display:flex; align-items:center; gap:8px;">
            <div class="seat-bar-track"><div class="seat-bar-fill ${free === 0 ? 'full' : ''}" style="width:${fill}%"></div></div>
            <span class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(free)} free</span>
          </div>
        </td>
        <td>${attChip}</td>
        <td>
          <button class="btn btn-xs btn-secondary" data-open-haziri-class="${esc(cid)}">
            Haziri ${icon('arrow-right', 12)}
          </button>
        </td>
      </tr>`;
  }).join('');

  const activityRows = (d.recent_activity || []).slice(0, 8).map(a => `
    <div class="timeline-item">
      <div style="font-weight:500; color:var(--siyahi);">${esc(a.summary)}</div>
      <div style="font-size:11.5px; color:var(--siyahi-soft); margin-top:2px;">
        ${esc(a.username)} (${esc(a.role)}) • ${esc(formatDateTime(a.created_at))}
      </div>
    </div>`).join('');

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Aaj Ka Din — ${esc(schoolName)}</div>
        <div class="page-header-desc">${esc(todayLabel)} • ${esc(curYear)}</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-secondary" data-dash-goto="attendance">${icon('attendance', 15)} Mark Attendance</button>
        <button class="btn btn-secondary" data-dash-goto="fees">${icon('fees', 15)} Fee Counter</button>
        <button class="btn btn-primary" id="dash-btn-admit">${icon('plus', 15)} New Admission</button>
      </div>
    </div>

    ${checklistBanner}

    <!-- P1, P2, P3, Campus Summary — Calm Ink Numbers (Zero Red/Green Slop) -->
    <div class="kpi-grid">
      <div class="kpi-card clickable" data-dash-goto="fees" style="cursor:pointer;">
        <div class="kpi-label">Today's Fee Collection (P1)</div>
        <div class="kpi-value num">${esc(formatPKR(c.amount ?? c.today_amount ?? 0))}</div>
        <div class="kpi-sub">${esc(c.receipts ?? c.today_receipts ?? 0)} receipts today • Yesterday: ${esc(formatPKR(c.yesterday_amount || 0))}</div>
      </div>

      <div class="kpi-card clickable" data-dash-goto="attendance" style="cursor:pointer;">
        <div class="kpi-label">Today's Attendance (P2)</div>
        <div class="kpi-value num">${att.pct !== null && att.pct !== undefined ? `${att.pct}%` : 'Not Started'}</div>
        <div class="kpi-sub">${esc(att.marked_classes || 0)}/${esc(att.total_classes || 0)} classes marked • ${esc(att.unmarked_classes || 0)} pending</div>
      </div>

      <div class="kpi-card clickable" data-dash-goto="fees" style="cursor:pointer;">
        <div class="kpi-label">Outstanding Fee Dues (P3)</div>
        <div class="kpi-value num">${esc(formatPKR(due.total_due || 0))}</div>
        <div class="kpi-sub">${esc(due.students_count ?? due.student_count ?? 0)} students (${esc(due.overdue_30d_count || 0)} over 30 days)</div>
      </div>

      <div class="kpi-card clickable" data-dash-goto="school" style="cursor:pointer;">
        <div class="kpi-label">Active Enrollment</div>
        <div class="kpi-value num">${esc(enr.enrolled ?? d.active_students ?? 0)}</div>
        <div class="kpi-sub">${esc(att.total_classes || 0)} active classes in session</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns: 1.45fr 1fr; gap:var(--sp-5); align-items:start;">
      <div>
        <!-- P4: Exceptions & Pending Approvals -->
        <div class="panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">Attention Required (Tawajjo Talab)</div>
              <div class="panel-subtitle">Exceptions, unmarked attendance &amp; pending leave approvals</div>
            </div>
          </div>
          <div>
            ${attentionItems || leaveRows
              ? `${attentionItems}${leaveRows}`
              : `<div class="panel-body" style="color:var(--siyahi-soft); font-size:13.5px;">${icon('check', 16)} All daily operations are on track today.</div>`}
          </div>
        </div>

        <!-- P5: Class-Wise Attendance & Capacity -->
        <div class="panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">Class-Wise Attendance &amp; Seat Capacity</div>
              <div class="panel-subtitle">Click Haziri to open any class roll-call sheet directly</div>
            </div>
            <button class="btn btn-secondary btn-sm" data-dash-goto="school">All Students</button>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Class</th><th>Teacher</th><th class="num">Enrolled</th>
                  <th>Capacity</th><th>Today's Roll Call</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${classRows || `<tr><td colspan="6" style="text-align:center; padding:24px;">No classes configured</td></tr>`}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- P7: Audit Trail Feed -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Recent Staff Activity</div>
            <div class="panel-subtitle">Append-only audit log across modules</div>
          </div>
          <button class="btn btn-ghost btn-sm" data-dash-goto="settings">Full Log</button>
        </div>
        <div>
          ${activityRows || `<div class="panel-body" style="color:var(--siyahi-soft); font-size:13px;">No recorded actions yet today.</div>`}
        </div>
      </div>
    </div>`;
}

function _attachPrincipalEvents() {
  document.getElementById('dash-btn-admit')?.addEventListener('click', () => {
    openNewStudentModal(() => navigateTo('dashboard'));
  });
  document.getElementById('dash-quick-backup')?.addEventListener('click', async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      await apiPost('/api/settings/backup', { note: 'Principal 1-click dashboard backup' });
      toast('Database backup completed and verified', 'success');
      navigateTo('dashboard');
    } catch (err) {
      toast(err.message, 'error');
      btn.disabled = false;
    }
  });
  document.querySelectorAll('[data-dash-goto]').forEach(el => {
    el.addEventListener('click', () => navigateTo(el.getAttribute('data-dash-goto')));
  });
  document.querySelectorAll('[data-open-haziri-class]').forEach(btn => {
    btn.addEventListener('click', () => {
      const cid = parseInt(btn.getAttribute('data-open-haziri-class'), 10);
      navigateTo('attendance', { selectedClassId: cid });
    });
  });
  document.querySelectorAll('[data-leave-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id  = parseInt(btn.getAttribute('data-leave-id'), 10);
      const act = btn.getAttribute('data-leave-act');
      btn.disabled = true;
      try {
        await apiPost(`/api/attendance/leaves/${id}/action`, { action: act });
        toast(`Leave request ${act}d`, 'success');
        navigateTo('dashboard');
      } catch (err) {
        toast(err.message, 'error');
        btn.disabled = false;
      }
    });
  });
}

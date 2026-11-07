/**
 * screens/school/student-profile.js — Student 360° Unified Profile (Phase 2 — S360-1..S360-8)
 *
 * Replaces 4-tab hunting (F10: 12 clicks -> 1 click) with:
 *   - S360-1: Identity header & lifecycle actions
 *   - S360-2: 6 Smart Buttons (Attendance %, Fee Due, Last Exam, Books, Transport, Hostel)
 *   - S360-3..7: 5 focused tabs (Bio & Siblings, Fee Vouchers, Attendance, Exams, Campus/Awards)
 *   - S360-8: Audit-log Activity Timeline on the right rail
 */

import { apiGet, apiPost } from '../../core/api.js';
import { get } from '../../core/state.js';
import { esc, toast, confirm } from '../../core/dom.js';
import { fullName, formatPKR, formatDate, formatDateTime, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { navigateTo } from '../../core/router.js';
import { performStudentAction } from './student-modal.js';

let _activeSubTab = 'bio';
let _cachedProfile = null;

export async function renderStudentProfileScreen() {
  const sid = get('selectedStudentId');
  if (!sid) {
    navigateTo('school');
    return '';
  }

  _cachedProfile = await apiGet(`/api/students/${sid}/360`);
  _activeSubTab = 'bio';
  const html = _buildProfileHtml(_cachedProfile);
  setTimeout(_bindProfileEvents, 20);
  return html;
}

function _buildProfileHtml(d) {
  const s  = d.student || {};
  const sb = d.smart_buttons || {};
  const role = get('role') || 'admin';
  const canManageAdmission = ['admin', 'principal', 'front_desk'].includes(role);

  return `
    <div class="page-header">
      <div class="page-header-info">
        <div style="margin-bottom:6px;">
          <button type="button" class="btn btn-ghost btn-xs" id="s360-back">${icon('arrow-left', 13)} Back to Students</button>
        </div>
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
          <div class="page-header-title">${esc(fullName(s))}</div>
          <span class="badge ${stateBadgeClass(s.state)}">${esc(stateLabel(s.state))}</span>
        </div>
        <div class="page-header-desc">
          GR No: <strong>${esc(s.pid)}</strong> • Class: <strong>${esc(s.class_name || '—')}</strong> • Roll #${esc(s.roll_no || '—')} • ${esc(s.year_name || '')}
        </div>
      </div>
      <div class="page-header-actions">
        ${canManageAdmission && s.state === 'draft' ? `<button class="btn btn-primary btn-sm" data-s360-act="admission_done">Confirm Admission</button>` : ''}
        ${canManageAdmission && s.state === 'done' ? `<button class="btn btn-secondary btn-sm" data-s360-act="set_alumni">Mark Alumni</button>` : ''}
        <button class="btn btn-secondary btn-sm" id="s360-print">${icon('printer', 14)} Print Summary</button>
      </div>
    </div>

    <!-- S360-2: 6 Odoo-style Smart Buttons -->
    <div class="smart-strip">
      <button type="button" class="smart-btn" data-s360-tab="attendance">
        <span class="smart-btn-label">Attendance</span>
        <span class="smart-btn-val">${sb.attendance_pct !== null && sb.attendance_pct !== undefined ? `${sb.attendance_pct}%` : '—'}</span>
        <span class="smart-btn-sub">${esc(sb.attendance_detail || '')}</span>
      </button>
      <button type="button" class="smart-btn" data-s360-tab="fees">
        <span class="smart-btn-label">Fee Balance Due</span>
        <span class="smart-btn-val">${esc(formatPKR(sb.fee_due || 0))}</span>
        <span class="smart-btn-sub">${esc((d.payslips || []).length)} vouchers</span>
      </button>
      <button type="button" class="smart-btn" data-s360-tab="exams">
        <span class="smart-btn-label">Latest Exam</span>
        <span class="smart-btn-val">${esc(sb.last_exam || '—')}</span>
        <span class="smart-btn-sub">${esc((d.exam_results || []).length)} marksheets</span>
      </button>
      <button type="button" class="smart-btn" data-s360-tab="campus">
        <span class="smart-btn-label">Library Books</span>
        <span class="smart-btn-val">${esc(sb.library_issued || 0)} Issued</span>
        <span class="smart-btn-sub">Active loans</span>
      </button>
      <button type="button" class="smart-btn" data-s360-tab="campus">
        <span class="smart-btn-label">Transport Route</span>
        <span class="smart-btn-val truncate" style="max-width:140px;">${esc(sb.transport_route || 'None')}</span>
        <span class="smart-btn-sub">${d.transport ? esc(d.transport.license_plate) : 'No bus assigned'}</span>
      </button>
      <button type="button" class="smart-btn" data-s360-tab="campus">
        <span class="smart-btn-label">Boarding / Hostel</span>
        <span class="smart-btn-val truncate" style="max-width:140px;">${esc(sb.hostel_room || 'Day Scholar')}</span>
        <span class="smart-btn-sub">Accommodation</span>
      </button>
    </div>

    <div class="s360-layout">
      <div class="panel">
        <div class="tab-bar" role="tablist">
          <button type="button" class="tab-btn active" data-s360-tab="bio">Profile &amp; Family</button>
          <button type="button" class="tab-btn" data-s360-tab="fees">Fee Vouchers (${(d.payslips || []).length})</button>
          <button type="button" class="tab-btn" data-s360-tab="attendance">Attendance &amp; Leaves</button>
          <button type="button" class="tab-btn" data-s360-tab="exams">Exam Results (${(d.exam_results || []).length})</button>
          <button type="button" class="tab-btn" data-s360-tab="campus">Campus &amp; Awards</button>
        </div>
        <div id="s360-tab-content">${_renderSubTab('bio', d)}</div>
      </div>

      <!-- S360-8: Audit Activity Timeline -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Activity Timeline</div>
            <div class="panel-subtitle">Verified audit history</div>
          </div>
        </div>
        <div>
          ${(d.audit_timeline || []).map(a => `
            <div class="timeline-item">
              <div style="font-weight:500;">${esc(a.summary)}</div>
              <div style="font-size:11.5px; color:var(--siyahi-soft); margin-top:2px;">
                ${esc(a.username)} (${esc(a.role)}) • ${esc(formatDateTime(a.created_at))}
              </div>
            </div>`).join('') || `<div class="panel-body" style="color:var(--siyahi-soft); font-size:12.5px;"> Admission record initialized (${esc(formatDate(s.admission_date))}).</div>`}
        </div>
      </div>
    </div>`;
}

function _renderSubTab(tab, d) {
  const s = d.student || {};
  const canCollectFee = ['admin', 'principal', 'fee_clerk'].includes(get('role') || 'admin');
  if (tab === 'fees') {
    const rows = (d.payslips || []).map(p => `
      <tr>
        <td class="num">${esc(p.number || '—')}</td>
        <td>${esc(p.name || 'Monthly Fee')}</td>
        <td class="num">${esc(formatDate(p.date))}</td>
        <td class="num">${esc(formatPKR(p.total))}</td>
        <td class="num" style="font-weight:600;">${esc(formatPKR(p.due_amount))}</td>
        <td><span class="badge ${stateBadgeClass(p.state)}">${esc(stateLabel(p.state))}</span></td>
        <td>${canCollectFee && p.state !== 'paid' ? `<button class="btn btn-xs btn-primary" data-s360-pay="${esc(p.id)}" data-amt="${esc(formatPKR(p.due_amount))}">Receive</button>` : '—'}</td>
      </tr>`).join('');
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Voucher #</th><th>Description</th><th>Date</th><th class="num">Total</th><th class="num">Due</th><th>Status</th><th>Action</th></tr></thead><tbody>${rows || `<tr><td colspan="7" style="padding:20px; text-align:center;">No fee vouchers issued yet.</td></tr>`}</tbody></table></div>`;
  }

  if (tab === 'attendance') {
    const a = d.attendance || {};
    const lvs = (a.leaves || []).map(l => `
      <tr>
        <td>${esc(l.name || 'Leave')}</td>
        <td class="num">${esc(l.start_date)} – ${esc(l.end_date)} (${esc(l.days)}d)</td>
        <td>${esc(l.reason || '—')}</td>
        <td><span class="badge ${stateBadgeClass(l.state)}">${esc(stateLabel(l.state))}</span></td>
      </tr>`).join('');
    return `
      <div class="panel-body" style="border-bottom:1px solid var(--rule-line);">
        <strong>Summary:</strong> ${esc(a.present_days || 0)} Present / ${esc(a.absent_days || 0)} Absent out of ${esc(a.total_days || 0)} recorded roll-call days.
      </div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Type</th><th>Dates</th><th>Reason</th><th>Status</th></tr></thead><tbody>${lvs || `<tr><td colspan="4" style="padding:20px; text-align:center;">No leave applications on file.</td></tr>`}</tbody></table></div>`;
  }

  if (tab === 'exams') {
    const rows = (d.exam_results || []).map(r => `
      <tr>
        <td style="font-weight:600;">${esc(r.exam_name)}</td>
        <td class="num">${esc(r.total)}</td>
        <td class="num">${esc(r.percentage)}%</td>
        <td>${esc(r.grade || '—')}</td>
        <td><span class="badge ${stateBadgeClass(r.result || r.state)}">${esc(stateLabel(r.result || r.state))}</span></td>
      </tr>`).join('');
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Examination</th><th class="num">Total Marks</th><th class="num">Percentage</th><th>Grade</th><th>Outcome</th></tr></thead><tbody>${rows || `<tr><td colspan="5" style="padding:20px; text-align:center;">No examination marksheets recorded.</td></tr>`}</tbody></table></div>`;
  }

  if (tab === 'campus') {
    const books = (d.library_issues || []).map(b => `
      <tr><td>${esc(b.issue_code)}</td><td>${esc(b.book_name)}</td><td class="num">${esc(formatDate(b.date_issue))}</td><td><span class="badge ${stateBadgeClass(b.state)}">${esc(stateLabel(b.state))}</span></td></tr>`).join('');
    const awards = (d.awards || []).map(aw => `<li><strong>${esc(aw.name)}:</strong> ${esc(aw.description || '')}</li>`).join('');
    return `
      <div class="panel-body" style="border-bottom:1px solid var(--rule-line); display:grid; grid-template-columns:1fr 1fr; gap:16px;">
        <div><strong>Transport:</strong> ${d.transport ? `${esc(d.transport.route_name)} (${esc(d.transport.license_plate)})` : 'Not registered'}</div>
        <div><strong>Hostel:</strong> ${d.hostel ? `Room ${esc(d.hostel.room_no)} — ${esc(d.hostel.hostel_name)}` : 'Day Scholar'}</div>
        ${awards ? `<div style="grid-column:1/-1;"><strong>Awards:</strong><ul style="margin-top:4px;">${awards}</ul></div>` : ''}
      </div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Issue #</th><th>Book Title</th><th>Issued On</th><th>Status</th></tr></thead><tbody>${books || `<tr><td colspan="4" style="padding:20px; text-align:center;">No library book issues.</td></tr>`}</tbody></table></div>`;
  }

  // Default: Bio, Guardians & Siblings (S360-3)
  const parents = (d.parents || []).map(p => `<div style="margin-bottom:6px;"><strong>${esc(p.name)}</strong> (${esc(p.relation_name || p.relation_id || 'Guardian')}) — ${esc(p.phone || p.mobile || 'No phone')}</div>`).join('');
  const siblings = (d.siblings || []).map(sib => `
    <button type="button" class="btn btn-secondary btn-xs" data-sib-id="${esc(sib.id)}" style="margin-right:6px; margin-bottom:4px;">
      ${esc(sib.student_name)} ${esc(sib.last || '')} (${esc(sib.class_name || sib.pid)})
    </button>`).join('');

  return `
    <div class="panel-body" style="display:grid; grid-template-columns:1fr 1fr; gap:16px; font-size:13.5px;">
      <div><div style="color:var(--siyahi-soft); font-size:12px;">Date of Birth</div><strong>${esc(formatDate(s.date_of_birth))}</strong></div>
      <div><div style="color:var(--siyahi-soft); font-size:12px;">Gender</div><strong style="text-transform:capitalize;">${esc(s.gender || '—')}</strong></div>
      <div><div style="color:var(--siyahi-soft); font-size:12px;">Mobile</div><strong>${esc(s.contact_mobile || s.contact_phone || '—')}</strong></div>
      <div><div style="color:var(--siyahi-soft); font-size:12px;">Admission Date</div><strong>${esc(formatDate(s.admission_date))}</strong></div>
      <div style="grid-column:1/-1; padding-top:8px; border-top:1px solid var(--rule-line);">
        <div style="color:var(--siyahi-soft); font-size:12px; margin-bottom:4px;">Parents / Guardians</div>
        ${parents || '<span style="color:var(--siyahi-soft);">No linked guardian record</span>'}
      </div>
      <div style="grid-column:1/-1; padding-top:8px; border-top:1px solid var(--rule-line);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <span style="color:var(--siyahi-soft); font-size:12px;">Siblings &amp; Family Ledger</span>
          <button type="button" class="btn btn-secondary btn-xs" id="s360-open-family-ledger" data-fam-query="${esc(s.contact_mobile || s.pid || '')}">${icon('fees', 13)} Open Family Ledger</button>
        </div>
        ${siblings || '<span style="color:var(--siyahi-soft);">No siblings detected on shared guardian/mobile</span>'}
      </div>
    </div>`;
}

function _bindProfileEvents() {
  document.getElementById('s360-back')?.addEventListener('click', () => navigateTo('school'));
  document.getElementById('s360-print')?.addEventListener('click', () => window.print());

  document.querySelectorAll('[data-s360-act]').forEach(btn => {
    btn.addEventListener('click', () => {
      const sid = get('selectedStudentId');
      performStudentAction(sid, btn.getAttribute('data-s360-act'), btn, () => navigateTo('student360', { selectedStudentId: sid }));
    });
  });

  document.querySelectorAll('[data-s360-tab]').forEach(el => {
    el.addEventListener('click', () => {
      _activeSubTab = el.getAttribute('data-s360-tab');
      document.querySelectorAll('.tab-btn[data-s360-tab]').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-s360-tab') === _activeSubTab);
      });
      const content = document.getElementById('s360-tab-content');
      if (content && _cachedProfile) {
        content.innerHTML = _renderSubTab(_activeSubTab, _cachedProfile);
        _bindDynamicTabEvents();
      }
    });
  });
  _bindDynamicTabEvents();
}

function _bindDynamicTabEvents() {
  document.getElementById('s360-open-family-ledger')?.addEventListener('click', e => {
    const q = e.currentTarget.getAttribute('data-fam-query') || '';
    navigateTo('fees', { feesSubTab: 'family', feesQuery: q });
  });
  document.querySelectorAll('[data-sib-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      navigateTo('student360', { selectedStudentId: parseInt(btn.getAttribute('data-sib-id'), 10) });
    });
  });
  document.querySelectorAll('[data-s360-pay]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = parseInt(btn.getAttribute('data-s360-pay'), 10);
      const ok = await confirm('Confirm Fee Receipt', `Receive ${btn.getAttribute('data-amt')} for this voucher?`, {
        confirmLabel: 'Confirm Receipt',
        confirmClass: 'btn-primary',
      });
      if (!ok) return;
      btn.disabled = true;
      try {
        await apiPost(`/api/fees/payslips/${id}/action`, { action: 'pay' });
        toast('Fee voucher marked Paid', 'success');
        navigateTo('student360', { selectedStudentId: get('selectedStudentId') });
      } catch (err) {
        toast(err.message, 'error');
        btn.disabled = false;
      }
    });
  });
}


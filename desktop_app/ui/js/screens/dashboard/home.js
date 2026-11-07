/**
 * dashboard/home.js — "Aaj Ka Din" Principal & Admin Command Center (Phase 1/2)
 *
 * Strictly uses "Kaghaz aur Siyahi" design tokens.
 * Gives immediate visibility into:
 *   1. 4 Actionable KPI Cards (Enrolled Students, Fee Collection vs Due, Today's Haziri %, Active Services)
 *   2. Quick Action Strip (1-click jump to Haziri, New Admission, Fee Vouchers)
 *   3. Class-Wise Seat & Attendance Overview Table
 *   4. Recent Fee Vouchers / Defaulters Snapshot
 */

import { getBootstrap } from '../../core/state.js';
import { esc } from '../../core/dom.js';
import { formatPKR, formatDate, stateLabel, stateBadgeClass } from '../../core/format.js';
import { navigateTo } from '../../core/router.js';
import { openNewStudentModal } from '../school/student-modal.js';

export function renderDashboardScreen() {
  const data = getBootstrap();
  if (!data) {
    return `
      <div class="panel">
        <div class="panel-body">
          <div class="skeleton skeleton-title" style="width:200px"></div>
          <div class="skeleton skeleton-row" style="margin-top:16px"></div>
        </div>
      </div>`;
  }

  const k          = data.kpis || {};
  const classes    = data.school?.standards || [];
  const dailyAtt   = data.attendance?.daily || [];
  const payslips   = data.fees?.payslips    || [];
  const schoolName = data.school?.schools?.[0]?.name || 'School ERP';
  const curYear    = (data.school?.years || []).find(y => y.current)?.name || 'Current Session';

  const todayIso = new Date().toISOString().split('T')[0];
  const todayAtt = dailyAtt.filter(a => a.date === todayIso);
  const totalPres = todayAtt.reduce((acc, a) => acc + (a.total_presence || 0), 0);
  const totalStud = todayAtt.reduce((acc, a) => acc + (a.total_student || 0), 0);
  const attPct    = totalStud > 0 ? Math.round((totalPres / totalStud) * 100) : null;

  const todayFormatted = new Date().toLocaleDateString('en-PK', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  const classRows = classes.map(cls => {
    const att = todayAtt.find(a => a.standard_id === cls.id);
    const enrolled = cls.total_students ?? 0;
    const cap      = cls.capacity ?? 35;
    const free     = cls.remaining_seats ?? Math.max(0, cap - enrolled);
    const fillPct  = cap > 0 ? Math.min(100, Math.round((enrolled / cap) * 100)) : 0;

    let attBadge = `<span class="badge badge-warn">Pending Today</span>`;
    if (att) {
      attBadge = `<span class="badge ${att.state === 'validate' ? 'badge-success' : 'badge-info'}">
        ${esc(att.total_presence)}/${esc(att.total_student)} Hazir (${esc(stateLabel(att.state))})
      </span>`;
    }

    return `
      <tr>
        <td style="font-weight:600;">${esc(cls.name)}</td>
        <td>${esc(cls.teacher_name || 'Assigned Faculty')}</td>
        <td class="num">${esc(enrolled)} / ${esc(cap)}</td>
        <td>
          <div style="display:flex; align-items:center; gap:8px;">
            <div style="flex:1; height:7px; background:var(--rule-line); border-radius:99px; overflow:hidden; max-width:90px;">
              <div style="width:${fillPct}%; height:100%; background:${free === 0 ? 'var(--surkh)' : 'var(--pista-text)'};"></div>
            </div>
            <span class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(free)} free</span>
          </div>
        </td>
        <td>${attBadge}</td>
        <td>
          <button class="btn btn-xs btn-secondary" data-dash-goto="attendance">
            Haziri →
          </button>
        </td>
      </tr>`;
  }).join('');

  const recentSlips = payslips.slice(0, 6).map(p => `
    <tr>
      <td class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(p.number || '—')}</td>
      <td style="font-weight:500;">${esc(p.student_name)}</td>
      <td class="num" style="font-weight:600;">${esc(formatPKR(p.total))}</td>
      <td class="num" style="color:${p.due_amount > 0 ? 'var(--surkh)' : 'var(--pista-text)'}; font-weight:600;">
        ${esc(formatPKR(p.due_amount))}
      </td>
      <td><span class="badge ${stateBadgeClass(p.state)}">${esc(stateLabel(p.state))}</span></td>
    </tr>`).join('');

  setTimeout(_attachDashboardEvents, 20);

  return `
    <!-- Top Welcome & Quick Actions Banner -->
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Aaj Ka Din — ${esc(schoolName)}</div>
        <div class="page-header-desc">${esc(todayFormatted)} • ${esc(curYear)}</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-secondary" id="dash-btn-haziri">📋 Haziri Lagayein</button>
        <button class="btn btn-secondary" id="dash-btn-fees">💰 Fee Counter</button>
        <button class="btn btn-primary" id="dash-btn-admit">+ Naya Admission</button>
      </div>
    </div>

    <!-- 4 Enterprise KPI Cards -->
    <div class="kpi-grid">
      <div class="kpi-card clickable" data-dash-goto="school" style="cursor:pointer;">
        <div class="kpi-label">Active Enrolled Students</div>
        <div class="kpi-value num">${esc(k.active_students ?? 0)}</div>
        <div class="kpi-sub">${esc(k.classes ?? classes.length)} Active Classes • ${esc(k.teachers ?? 0)} Teachers</div>
      </div>

      <div class="kpi-card clickable" data-dash-goto="attendance" style="cursor:pointer;">
        <div class="kpi-label">Aaj Ki Haziri (Attendance)</div>
        <div class="kpi-value num">${attPct !== null ? `${attPct}%` : 'Pending'}</div>
        <div class="kpi-sub">
          ${todayAtt.length > 0
            ? `${todayAtt.length}/${classes.length} classes marked (${totalPres}/${totalStud} hazir)`
            : 'Click karein aaj ki haziri shuru karne ke liye'}
        </div>
      </div>

      <div class="kpi-card clickable" data-dash-goto="fees" style="cursor:pointer;">
        <div class="kpi-label">Fee Wasooli (Collected)</div>
        <div class="kpi-value num" style="color:var(--pista-text);">${esc(formatPKR(k.fees_collected ?? 0))}</div>
        <div class="kpi-sub" style="color:${(k.fees_due ?? 0) > 0 ? 'var(--surkh)' : 'var(--siyahi-soft)'};">
          Baaqaya (Due): ${esc(formatPKR(k.fees_due ?? 0))}
        </div>
      </div>

      <div class="kpi-card clickable" data-dash-goto="library" style="cursor:pointer;">
        <div class="kpi-label">Campus Services</div>
        <div class="kpi-value num">${esc(k.available_books ?? 0)} Books</div>
        <div class="kpi-sub">${esc(k.hostel_residents ?? 0)} Hostel • ${esc(k.transport_participants ?? 0)} Bus Riders</div>
      </div>
    </div>

    <!-- Two-Column Workspace: Class Overview & Fee Snapshot -->
    <div style="display:grid; grid-template-columns: 1.35fr 1fr; gap:var(--sp-5); align-items:start;">

      <!-- Left: Class-Wise Seat & Today's Attendance Status -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Classes, Seat Capacity &amp; Aaj Ki Haziri</div>
            <div class="panel-subtitle">Har class ki enrollment aur rozana haziri ki haalat</div>
          </div>
          <div class="panel-toolbar">
            <button class="btn btn-secondary btn-sm" data-dash-goto="school">Tamam Students →</button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Class</th>
                <th>Class Teacher</th>
                <th class="num">Enrolled</th>
                <th>Seat Meter</th>
                <th>Today's Haziri</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${classRows || `<tr><td colspan="6" style="text-align:center; padding:24px;">Koi class mojood nahi</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right: Recent Fee Challans & Defaulters -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Recent Fee Vouchers &amp; Baaqaya</div>
            <div class="panel-subtitle">Taza fee challans aur wasooli status</div>
          </div>
          <div class="panel-toolbar">
            <button class="btn btn-secondary btn-sm" data-dash-goto="fees">Fee Counter →</button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Challan #</th>
                <th>Student</th>
                <th class="num">Total</th>
                <th class="num">Baaqaya</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${recentSlips || `<tr><td colspan="5" style="text-align:center; padding:24px;">Koi fee voucher nahi bana</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  `;
}

function _attachDashboardEvents() {
  document.getElementById('dash-btn-haziri')?.addEventListener('click', () => navigateTo('attendance'));
  document.getElementById('dash-btn-fees')?.addEventListener('click', () => navigateTo('fees'));
  document.getElementById('dash-btn-admit')?.addEventListener('click', () => {
    openNewStudentModal(() => window.location.reload());
  });

  document.querySelectorAll('[data-dash-goto]').forEach(el => {
    el.addEventListener('click', () => {
      const target = el.getAttribute('data-dash-goto');
      if (target) navigateTo(target);
    });
  });
}


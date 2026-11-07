/**
 * screens/exam/exam-workspace.js — Examinations, Spreadsheet Marks Grid, Ranks & Gazette (G7, S5)
 *
 * Sub-tabs:
 *   1. Marks Grid (MRK-1..3 spreadsheet keyboard entry)
 *   2. Result Gazette & Report Cards (R-E1 Olympic tie-aware ranks & bulk print)
 *   3. Exam Schedules (Quick Exam creation & lifecycle actions)
 */

import { apiGet, apiPost } from '../../core/api.js';
import { get, getBootstrap, setBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { formatDate, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { renderMarksGridTab } from './marks-grid.js';
import { openReportCardsPrintPreview } from '../../print/academic-print.js';

let _activeExamTab = 'grid';

export async function renderExamScreen() {
  const boot = getBootstrap();
  const exams = boot?.exam?.exams || [];
  const role = get('role') || 'admin';
  const canLeadExam = ['admin', 'principal', 'exam_incharge'].includes(role);

  const html = `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Examinations, Marks Grid &amp; Report Cards</div>
        <div class="page-header-desc">Keyboard spreadsheet marks entry, Olympic tie-aware class ranking &amp; official report cards</div>
      </div>
      <div class="page-header-actions">
        ${canLeadExam ? `<button type="button" class="btn btn-primary" id="btn-quick-exam">${icon('plus', 15)} New Exam &amp; Marksheets</button>` : ''}
      </div>
    </div>

    <div class="panel">
      <div class="tab-bar" role="tablist">
        <button type="button" class="tab-btn ${_activeExamTab === 'grid' ? 'active' : ''}" data-ex-tab="grid">Spreadsheet Marks Grid</button>
        <button type="button" class="tab-btn ${_activeExamTab === 'gazette' ? 'active' : ''}" data-ex-tab="gazette">Result Gazette &amp; Report Cards</button>
        <button type="button" class="tab-btn ${_activeExamTab === 'list' ? 'active' : ''}" data-ex-tab="list">Exam Sessions (${exams.length})</button>
      </div>
      <div id="exam-workspace-body">${_renderActiveSubTab()}</div>
    </div>`;

  setTimeout(_bindExamWorkspaceEvents, 20);
  return html;
}

function _renderActiveSubTab() {
  if (_activeExamTab === 'grid') return renderMarksGridTab();
  if (_activeExamTab === 'gazette') return _renderGazetteTab();
  return _renderExamSessionsTab();
}

function _renderGazetteTab() {
  const boot    = getBootstrap();
  const exams   = boot?.exam?.exams || [];
  const classes = boot?.school?.standards || [];
  const exOpts  = exams.map(e => `<option value="${esc(e.id)}">${esc(e.name)} (${esc(e.exam_code)})</option>`).join('');
  const clsOpts = classes.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');

  setTimeout(_loadGazetteView, 25);

  return `
    <div class="fees-filter-bar" style="justify-content:space-between;">
      <div style="display:flex; gap:10px; align-items:center;">
        <select class="form-control" id="gz-exam" style="min-width:220px;">${exOpts}</select>
        <select class="form-control" id="gz-class" style="min-width:160px;">
          <option value="">All Classes</option>${clsOpts}
        </select>
        <button type="button" class="btn btn-secondary btn-sm" id="gz-compute-ranks">${icon('refresh', 14)} Recompute Ranks</button>
      </div>
      <button type="button" class="btn btn-primary btn-sm" id="gz-print-all">${icon('printer', 14)} Print Bulk Report Cards</button>
    </div>
    <div id="gz-content-wrap">
      <div class="panel-body">${Array(5).fill('<div class="skeleton skeleton-row" style="margin-bottom:4px;"></div>').join('')}</div>
    </div>`;
}

async function _loadGazetteView() {
  const wrap = document.getElementById('gz-content-wrap');
  const examId = document.getElementById('gz-exam')?.value;
  const classId = document.getElementById('gz-class')?.value || '';
  if (!wrap || !examId) return;

  try {
    const res = await apiGet(`/api/exams/${examId}/gazette`, { class_id: classId });
    const s = res.summary || {};
    const items = res.items || [];

    wrap.innerHTML = `
      <div class="panel-body" style="border-bottom:1px solid var(--rule-line);">
        <div class="tally-mode-grid" style="margin-bottom:0;">
          <div class="tally-mode-card"><div class="tally-mode-label">Candidates</div><div class="tally-mode-val">${esc(s.total_students || 0)}</div></div>
          <div class="tally-mode-card"><div class="tally-mode-label">Pass Rate</div><div class="tally-mode-val">${esc(s.pass_rate_pct || 0)}%</div></div>
          <div class="tally-mode-card"><div class="tally-mode-label">Class Average</div><div class="tally-mode-val">${esc(s.class_average_pct || 0)}%</div></div>
          <div class="tally-mode-card"><div class="tally-mode-label">Top Position</div><div class="tally-mode-val" style="font-size:15px;">${esc(s.top_performer || '—')}</div></div>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="num">Rank</th>
              <th class="num">Roll #</th>
              <th>GR No.</th>
              <th>Student Name</th>
              <th>Class</th>
              <th class="num">Total Marks</th>
              <th class="num">Percentage</th>
              <th>Grade</th>
              <th>Outcome</th>
              <th>Report Card</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(r => `
              <tr>
                <td class="num" style="font-weight:700;">${r.rank ? `#${esc(r.rank)}` : '—'}</td>
                <td class="num">${esc(r.roll_no || '—')}</td>
                <td class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(r.pid)}</td>
                <td style="font-weight:600;">${esc([r.student_name, r.middle, r.last].filter(Boolean).join(' '))}</td>
                <td>${esc(r.class_name || '—')}</td>
                <td class="num" style="font-weight:600;">${esc(r.total)} / ${esc(r.max_total || 0)}</td>
                <td class="num">${esc(r.percentage)}%</td>
                <td><strong>${esc(r.grade || '—')}</strong></td>
                <td><span class="badge ${stateBadgeClass(r.result)}">${esc(stateLabel(r.result))}</span></td>
                <td>
                  <button type="button" class="btn btn-xs btn-secondary" data-gz-print-stu="${esc(r.student_id)}">
                    ${icon('printer', 12)} Print
                  </button>
                </td>
              </tr>`).join('') || `<tr><td colspan="10" style="padding:22px; text-align:center;">No marksheets found for this exam.</td></tr>`}
          </tbody>
        </table>
      </div>`;

    wrap.querySelectorAll('[data-gz-print-stu]').forEach(btn => {
      btn.addEventListener('click', () => {
        openReportCardsPrintPreview({
          examId,
          classId,
          studentId: btn.getAttribute('data-gz-print-stu'),
        });
      });
    });
  } catch (err) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">Unable to load gazette</div><div class="empty-state-desc">${esc(err.message)}</div></div>`;
  }
}

function _renderExamSessionsTab() {
  const exams = getBootstrap()?.exam?.exams || [];
  return `
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Code</th><th>Exam Name</th><th>Dates</th><th>Session</th><th class="num">Marksheets</th><th>Status</th><th>Action</th></tr>
        </thead>
        <tbody>
          ${exams.map(e => `
            <tr>
              <td class="num" style="font-weight:600;">${esc(e.exam_code)}</td>
              <td style="font-weight:600;">${esc(e.name)}</td>
              <td class="num">${esc(formatDate(e.start_date))} – ${esc(formatDate(e.end_date))}</td>
              <td>${esc(e.academic_year_name || '—')}</td>
              <td class="num">${esc(e.result_count || 0)}</td>
              <td><span class="badge ${stateBadgeClass(e.state)}">${esc(stateLabel(e.state))}</span></td>
              <td>
                <button type="button" class="btn btn-xs btn-secondary" data-open-exam-grid="${esc(e.id)}">Open Marks Grid</button>
              </td>
            </tr>`).join('') || `<tr><td colspan="7" style="padding:20px; text-align:center;">No exams scheduled yet.</td></tr>`}
        </tbody>
      </table>
    </div>`;
}

function _bindExamWorkspaceEvents() {
  document.querySelectorAll('[data-ex-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      _activeExamTab = btn.getAttribute('data-ex-tab');
      document.querySelectorAll('[data-ex-tab]').forEach(b => b.classList.toggle('active', b === btn));
      const body = document.getElementById('exam-workspace-body');
      if (body) {
        body.innerHTML = _renderActiveSubTab();
        _bindSubTabDynamicEvents();
      }
    });
  });

  document.getElementById('btn-quick-exam')?.addEventListener('click', _openQuickExamModal);
  _bindSubTabDynamicEvents();
}

function _bindSubTabDynamicEvents() {
  document.getElementById('gz-exam')?.addEventListener('change', _loadGazetteView);
  document.getElementById('gz-class')?.addEventListener('change', _loadGazetteView);
  document.getElementById('gz-compute-ranks')?.addEventListener('click', async () => {
    const examId = document.getElementById('gz-exam')?.value;
    const classId = document.getElementById('gz-class')?.value || null;
    if (!examId) return;
    await apiPost(`/api/exams/${examId}/compute-ranks`, { class_id: classId });
    toast('Olympic class ranks recomputed', 'success');
    _loadGazetteView();
  });
  document.getElementById('gz-print-all')?.addEventListener('click', () => {
    const examId = document.getElementById('gz-exam')?.value;
    const classId = document.getElementById('gz-class')?.value || '';
    if (examId) openReportCardsPrintPreview({ examId, classId });
  });
  document.querySelectorAll('[data-open-exam-grid]').forEach(btn => {
    btn.addEventListener('click', () => {
      _activeExamTab = 'grid';
      document.querySelectorAll('[data-ex-tab]').forEach(b => b.classList.toggle('active', b.getAttribute('data-ex-tab') === 'grid'));
      const body = document.getElementById('exam-workspace-body');
      if (body) body.innerHTML = renderMarksGridTab(btn.getAttribute('data-open-exam-grid'));
    });
  });
}

function _openQuickExamModal() {
  const boot = getBootstrap();
  const classes = boot?.school?.standards || [];
  const today = new Date().toISOString().slice(0, 10);
  const clsChecks = classes.map(c => `
    <label style="display:flex; align-items:center; gap:6px; font-size:13px;">
      <input type="checkbox" class="qe-cls-chk" value="${esc(c.id)}" checked /> ${esc(c.name)}
    </label>`).join('');

  openModal('Create Exam & Initialize Class Marksheets', `
    <div class="form-group">
      <label class="form-label required" for="qe-name">Examination Title</label>
      <input class="form-control" id="qe-name" placeholder="e.g. Mid-Term Examination 2026" required autofocus />
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="qe-start">Start Date</label>
        <input class="form-control" id="qe-start" type="date" value="${today}" required />
      </div>
      <div class="form-group">
        <label class="form-label required" for="qe-end">End Date</label>
        <input class="form-control" id="qe-end" type="date" value="${today}" required />
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Participating Classes (auto-generates marksheets)</label>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:10px; border:1px solid var(--rule-line); border-radius:var(--radius);">
        ${clsChecks}
      </div>
    </div>
  `, async () => {
    const name = document.getElementById('qe-name')?.value?.trim();
    const start_date = document.getElementById('qe-start')?.value;
    const end_date = document.getElementById('qe-end')?.value;
    const standard_ids = Array.from(document.querySelectorAll('.qe-cls-chk:checked')).map(el => parseInt(el.value, 10));
    const res = await apiPost('/api/exams/quick-create', { name, start_date, end_date, standard_ids });
    const freshBoot = await apiGet('/api/bootstrap');
    setBootstrap(freshBoot);
    closeModal();
    toast(`Exam created with ${res.generated_results} marksheet(s)`, 'success');
    const body = document.getElementById('exam-workspace-body');
    if (body) body.innerHTML = renderMarksGridTab(res.exam_id);
  }, { submitLabel: 'Create Exam & Generate Marksheets' });
}

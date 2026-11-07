/**
 * screens/exam/marks-grid.js — Keyboard-First Spreadsheet Marks Grid (MRK-1..3, R-T3, F5, F16)
 *
 * Features:
 *   - MRK-1: Context Bar (Exam, Class, Subject, Max/Min badge, Entered progress pill, Paste from Excel)
 *   - MRK-2: Keyboard navigation (Enter / ArrowDown / ArrowUp moves between rows), Absent toggle,
 *            live %/Grade/Pass-Fail calculation, and strict Poka-Yoke highlight (`0 <= marks <= max`)
 *   - MRK-3: Sticky bottom summary (Class Avg %, Highest, Pass/Fail, Save Draft, Finalize & Compute Ranks)
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { icon } from '../../core/icons.js';
import { openReportCardsPrintPreview } from '../../print/academic-print.js';

let _gridCtx = { examId: '', classId: '', subjectId: '', data: null };

export function renderMarksGridTab(initialExamId = '', initialClassId = '', initialSubjectId = '') {
  const boot     = getBootstrap();
  const exams    = boot?.exam?.exams || [];
  const classes  = boot?.school?.standards || [];
  const subjects = boot?.school?.subjects || [];

  if (!_gridCtx.examId && (initialExamId || exams[0]?.id)) _gridCtx.examId = String(initialExamId || exams[0].id);
  if (!_gridCtx.classId && (initialClassId || classes[0]?.id)) _gridCtx.classId = String(initialClassId || classes[0].id);
  if (!_gridCtx.subjectId && (initialSubjectId || subjects[0]?.id)) _gridCtx.subjectId = String(initialSubjectId || subjects[0].id);

  const examOpts  = exams.map(e => `<option value="${esc(e.id)}" ${String(e.id) === String(_gridCtx.examId) ? 'selected' : ''}>${esc(e.name)} (${esc(e.exam_code)})</option>`).join('');
  const classOpts = classes.map(c => `<option value="${esc(c.id)}" ${String(c.id) === String(_gridCtx.classId) ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  const subOpts   = subjects.map(s => `<option value="${esc(s.id)}" ${String(s.id) === String(_gridCtx.subjectId) ? 'selected' : ''}>${esc(s.name)} (Max ${esc(s.maximum_marks)})</option>`).join('');

  setTimeout(() => {
    _bindMarksGridToolbar();
    if (_gridCtx.examId && _gridCtx.classId && _gridCtx.subjectId) _loadMarksGrid();
  }, 20);

  return `
    <!-- MRK-1: Context Bar & Progress Meter -->
    <div class="fees-filter-bar" style="justify-content:space-between;">
      <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
        <select class="form-control" id="mg-exam" style="min-width:210px;" aria-label="Select Exam">${examOpts}</select>
        <select class="form-control" id="mg-class" style="min-width:150px;" aria-label="Select Class">${classOpts}</select>
        <select class="form-control" id="mg-subject" style="min-width:180px;" aria-label="Select Subject">${subOpts}</select>
        <span class="badge badge-info" id="mg-max-badge">Max: 100 • Pass: 35</span>
        <span class="badge badge-neutral num" id="mg-progress-pill">0 / 0 Entered</span>
      </div>
      <div style="display:flex; gap:8px;">
        <button type="button" class="btn btn-secondary btn-sm" id="mg-paste-excel">${icon('download', 14)} Paste from Excel</button>
        <button type="button" class="btn btn-secondary btn-sm" id="mg-print-rc">${icon('printer', 14)} Print Class Report Cards</button>
      </div>
    </div>

    <div id="mg-error-banner" style="display:none; padding:10px 18px; background:var(--danger-bg); color:var(--danger-text); font-size:13px; font-weight:600; border-bottom:1px solid var(--surkh);"></div>

    <!-- MRK-2: Keyboard-First Marks Table -->
    <div class="table-wrap" id="mg-table-wrap">
      <div class="panel-body">
        ${Array(6).fill('<div class="skeleton skeleton-row" style="margin-bottom:4px;"></div>').join('')}
      </div>
    </div>

    <!-- MRK-3: Live Class Summary & Rank Preview Strip -->
    <div class="panel-body" id="mg-footer-bar" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; border-top:1px solid var(--rule-line); background:var(--surface);">
      <div style="display:flex; gap:18px; font-size:13px;">
        <span>Class Avg: <strong class="num" id="mg-stat-avg">—</strong></span>
        <span>Highest: <strong class="num" id="mg-stat-high">—</strong></span>
        <span>Pass / Fail: <strong class="num" id="mg-stat-pf">0 / 0</strong></span>
      </div>
      <div style="display:flex; gap:10px;">
        <button type="button" class="btn btn-secondary" id="mg-save-draft">Save Draft</button>
        <button type="button" class="btn btn-primary" id="mg-finalize-ranks">${icon('check', 15)} Finalize &amp; Compute Ranks</button>
      </div>
    </div>`;
}

function _bindMarksGridToolbar() {
  ['mg-exam', 'mg-class', 'mg-subject'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      _gridCtx.examId    = document.getElementById('mg-exam')?.value || '';
      _gridCtx.classId   = document.getElementById('mg-class')?.value || '';
      _gridCtx.subjectId = document.getElementById('mg-subject')?.value || '';
      _loadMarksGrid();
    });
  });

  document.getElementById('mg-paste-excel')?.addEventListener('click', _openExcelPasteModal);
  document.getElementById('mg-print-rc')?.addEventListener('click', () => {
    if (_gridCtx.examId) {
      openReportCardsPrintPreview({ examId: _gridCtx.examId, classId: _gridCtx.classId });
    }
  });
  document.getElementById('mg-save-draft')?.addEventListener('click', () => _submitMarksGrid(false));
  document.getElementById('mg-finalize-ranks')?.addEventListener('click', () => _submitMarksGrid(true));
}

async function _loadMarksGrid() {
  const wrap = document.getElementById('mg-table-wrap');
  if (!wrap || !_gridCtx.examId || !_gridCtx.classId || !_gridCtx.subjectId) return;

  try {
    const res = await apiGet(`/api/exams/${_gridCtx.examId}/marks-grid`, {
      class_id:   _gridCtx.classId,
      subject_id: _gridCtx.subjectId,
    });
    _gridCtx.data = res;
    _renderMarksRows(res);
  } catch (err) {
    wrap.innerHTML = `<div class="empty-state">
      <div class="empty-state-title">Unable to load marks grid</div>
      <div class="empty-state-desc">${esc(err.message)}</div>
    </div>`;
  }
}

function _renderMarksRows(res) {
  const wrap = document.getElementById('mg-table-wrap');
  if (!wrap) return;
  const sub  = res.subject || {};
  const maxM = Number(sub.maximum_marks || 100);
  const minM = Number(sub.minimum_marks || 35);
  const rows = res.rows || [];

  const maxBadge = document.getElementById('mg-max-badge');
  if (maxBadge) maxBadge.textContent = `Max: ${maxM} • Pass: ${minM}`;

  if (!rows.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-state-title">No enrolled students in this class</div><div class="empty-state-desc">Admit students into this class before entering subject marks.</div></div>`;
    return;
  }

  wrap.innerHTML = `
    <table class="data-table" id="mg-grid-table">
      <thead>
        <tr><th class="num" style="width:65px;">Roll #</th><th style="width:110px;">GR No.</th><th>Student Name</th><th style="width:140px;">Obtained (/${esc(maxM)})</th><th style="width:85px; text-align:center;">Absent</th><th class="num" style="width:85px;">Sub %</th><th style="width:90px;">Status</th><th class="num" style="width:90px;">Rank</th><th>Teacher Remarks</th></tr>
      </thead>
      <tbody>
        ${rows.map((r, idx) => `
          <tr data-sline-id="${esc(r.subject_line_id)}" data-max="${esc(maxM)}" data-min="${esc(minM)}">
            <td class="num" style="font-weight:600;">${esc(r.roll_no || idx + 1)}</td>
            <td class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(r.pid)}</td>
            <td style="font-weight:500;">${esc(r.student_name)}</td>
            <td>
              <input type="number" step="0.5" min="0" max="${esc(maxM)}"
                     class="form-control num mg-mark-input"
                     data-row-idx="${idx}"
                     value="${esc(r.obtain_marks)}"
                     ${r.is_absent ? 'disabled' : ''}
                     style="height:34px; font-weight:600;" />
            </td>
            <td style="text-align:center;">
              <input type="checkbox" class="mg-absent-chk" ${r.is_absent ? 'checked' : ''} style="width:17px; height:17px;" aria-label="Mark Absent" />
            </td>
            <td class="num mg-cell-pct">${esc(r.subject_percentage)}%</td>
            <td class="mg-cell-status">
              <span class="badge ${r.subject_status === 'Pass' ? 'badge-success' : 'badge-danger'}">${esc(r.subject_status)}</span>
            </td>
            <td class="num" style="font-weight:600;">${r.rank ? `#${esc(r.rank)}` : '—'}</td>
            <td>
              <input type="text" class="form-control mg-remark-input" value="${esc(r.remarks || '')}"
                     placeholder="Optional remark..." style="height:32px; font-size:12.5px;" />
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;

  _attachGridRowInteractions(maxM, minM);
  _recomputeLiveFooter(maxM, minM);
}

function _attachGridRowInteractions(maxM, minM) {
  const inputs = Array.from(document.querySelectorAll('.mg-mark-input'));
  inputs.forEach((inp, idx) => {
    inp.addEventListener('keydown', e => {
      const step = (e.key === 'Enter' || e.key === 'ArrowDown') ? 1 : (e.key === 'ArrowUp' ? -1 : 0);
      if (step) { e.preventDefault(); inputs[idx + step]?.focus(); inputs[idx + step]?.select(); }
    });
    inp.addEventListener('input', () => _recomputeLiveFooter(maxM, minM));
  });

  document.querySelectorAll('.mg-absent-chk').forEach(chk => {
    chk.addEventListener('change', e => {
      const inp = e.target.closest('tr')?.querySelector('.mg-mark-input');
      if (inp) {
        inp.disabled = e.target.checked;
        if (e.target.checked) inp.value = '0'; else inp.focus();
      }
      _recomputeLiveFooter(maxM, minM);
    });
  });
}

function _recomputeLiveFooter(maxM, minM) {
  const rows = Array.from(document.querySelectorAll('#mg-grid-table tbody tr'));
  let entered = 0, passCnt = 0, failCnt = 0, sumPct = 0, highest = 0, hasError = false;

  rows.forEach(tr => {
    const inp = tr.querySelector('.mg-mark-input');
    const isAbs = Boolean(tr.querySelector('.mg-absent-chk')?.checked);
    const val = parseFloat(inp?.value || '0');
    const invalid = !isAbs && (isNaN(val) || val < 0 || val > maxM);
    tr.style.background = invalid ? 'var(--danger-bg)' : '';
    if (invalid) hasError = true;

    const cleanVal = isAbs || isNaN(val) ? 0 : val;
    if (cleanVal > 0 || isAbs) entered++;
    if (cleanVal > highest) highest = cleanVal;

    const pct = maxM > 0 && !isAbs ? Math.round((cleanVal / maxM) * 1000) / 10 : 0;
    sumPct += pct;
    const passed = !isAbs && cleanVal >= minM;
    if (passed) passCnt++; else failCnt++;

    const pctCell = tr.querySelector('.mg-cell-pct');
    if (pctCell) pctCell.textContent = `${pct}%`;
    const stCell = tr.querySelector('.mg-cell-status');
    if (stCell) {
      stCell.innerHTML = `<span class="badge ${passed ? 'badge-success' : 'badge-danger'}">${isAbs ? 'Absent' : (passed ? 'Pass' : 'Fail')}</span>`;
    }
  });

  const errBanner = document.getElementById('mg-error-banner');
  if (errBanner) {
    errBanner.style.display = hasError ? 'block' : 'none';
    errBanner.textContent = hasError ? `Poka-Yoke Alert: Marks must be between 0 and ${maxM}. Please correct highlighted rows before saving.` : '';
  }
  const setTxt = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
  setTxt('mg-progress-pill', `${entered} / ${rows.length} Entered`);
  setTxt('mg-stat-avg', rows.length ? `${(sumPct / rows.length).toFixed(1)}%` : '—');
  setTxt('mg-stat-high', `${highest} / ${maxM}`);
  setTxt('mg-stat-pf', `${passCnt} Pass / ${failCnt} Fail`);
  ['mg-save-draft', 'mg-finalize-ranks'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = hasError;
  });
}

async function _submitMarksGrid(finalize) {
  const rows = Array.from(document.querySelectorAll('#mg-grid-table tbody tr'));
  if (!rows.length) return;
  const entries = rows.map(tr => ({
    subject_line_id: parseInt(tr.getAttribute('data-sline-id'), 10),
    obtain_marks:    parseFloat(tr.querySelector('.mg-mark-input')?.value || '0'),
    is_absent:       Boolean(tr.querySelector('.mg-absent-chk')?.checked),
    remarks:         tr.querySelector('.mg-remark-input')?.value?.trim() || '',
  }));

  try {
    const res = await apiPost(`/api/exams/${_gridCtx.examId}/marks-grid`, {
      class_id:   parseInt(_gridCtx.classId, 10),
      subject_id: parseInt(_gridCtx.subjectId, 10),
      entries,
      finalize,
    });
    _gridCtx.data = res;
    _renderMarksRows(res);
    toast(finalize ? 'Marks finalized and Olympic class ranks computed!' : 'Subject marks saved', 'success');
  } catch (err) {
    toast(err.message, 'error');
  }
}

function _openExcelPasteModal() {
  openModal('Paste Marks Column from Excel / Spreadsheet', `
    <p style="font-size:13px; color:var(--siyahi-soft); margin-bottom:10px;">
      Copy a column of marks from Excel (in Roll Number order) and paste below. Type <code>ABS</code> for absent students.
    </p>
    <textarea class="form-control" id="mg-excel-paste-box" rows="8" placeholder="88&#10;92&#10;ABS&#10;74"></textarea>
  `, async () => {
    const raw = document.getElementById('mg-excel-paste-box')?.value || '';
    const lines = raw.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    const trs = Array.from(document.querySelectorAll('#mg-grid-table tbody tr'));
    lines.forEach((val, idx) => {
      const tr = trs[idx];
      if (!tr) return;
      const inp = tr.querySelector('.mg-mark-input');
      const chk = tr.querySelector('.mg-absent-chk');
      if (val.toUpperCase() === 'ABS' || val.toUpperCase() === 'A') {
        if (chk) chk.checked = true;
        if (inp) { inp.value = '0'; inp.disabled = true; }
      } else {
        if (chk) chk.checked = false;
        if (inp) { inp.disabled = false; inp.value = String(parseFloat(val) || 0); }
      }
    });
    closeModal();
    const sub = _gridCtx.data?.subject || {};
    _recomputeLiveFooter(Number(sub.maximum_marks || 100), Number(sub.minimum_marks || 35));
    toast(`Applied ${Math.min(lines.length, trs.length)} marks from clipboard`, 'info');
  }, { submitLabel: 'Apply Marks' });
}

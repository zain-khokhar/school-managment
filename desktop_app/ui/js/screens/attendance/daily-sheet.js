/**
 * attendance/daily-sheet.js — Haziri Controller & State (Phase 1, G1 Fix)
 *
 * Flow: Class select → "Haziri Shuru Karein" → roll call grid → Jama Karein
 * Before: teacher haziri mark kar hi nahi sakta tha (no route existed)
 * After:  40 bachon ki haziri < 60 seconds mein (~5 clicks)
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast } from '../../core/dom.js';
import { buildAttendanceShellHtml, buildSheetHtml } from './daily-sheet-view.js';

let _attState = {
  classId: null,
  className: '',
  attId: null,
  date: '',
  lines: [],
  modified: new Set(),
  submitting: false,
  validated: false,
};

let _undoStack = [];

/**
 * Attendance screen render karo
 * @returns {Promise<string>} HTML
 */
export async function renderAttendanceScreen() {
  const data = getBootstrap();
  const classes = data?.school?.standards || [];

  _attState = {
    classId: null, className: '', attId: null, date: '',
    lines: [], modified: new Set(), submitting: false, validated: false,
  };
  _undoStack = [];

  return buildAttendanceShellHtml(classes);
}

/**
 * Attach top-level class selector events
 */
export function attachAttendanceEvents() {
  const selectEl = document.getElementById('att-class-select');
  const loadBtn = document.getElementById('att-load-btn');
  if (!selectEl || !loadBtn) return;

  selectEl.addEventListener('change', () => {
    loadBtn.disabled = !selectEl.value;
  });

  loadBtn.addEventListener('click', async () => {
    const classId = parseInt(selectEl.value, 10);
    if (!classId) return;
    const data = getBootstrap();
    const cls = (data?.school?.standards || []).find(c => c.id === classId);
    _attState.classId = classId;
    _attState.className = cls?.name || `Class ${classId}`;
    await _loadOrCreateAttendance(classId);
  });
}

async function _loadOrCreateAttendance(classId) {
  const container = document.getElementById('att-sheet-container');
  if (!container) return;

  container.innerHTML = `
    <div class="panel">
      <div class="panel-body">
        <div class="skeleton skeleton-title" style="width:180px"></div>
        ${Array(5).fill('<div class="skeleton skeleton-row" style="margin-top:4px"></div>').join('')}
      </div>
    </div>`;

  try {
    const res = await apiGet(`/api/attendance/today/${classId}`);
    if (res.attendance) {
      _populateSheet(res.attendance);
    } else {
        await apiPost('/api/attendance/daily', {
          standard_id: classId,
          user_id: null,
          date: new Date().toISOString().split('T')[0],
        });
        const fresh = await apiGet(`/api/attendance/today/${classId}`);
        _populateSheet(fresh.attendance);
    }
  } catch (err) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <div class="empty-state-title">Haziri load nahi ho saki</div>
        <div class="empty-state-desc">${esc(err.message)}</div>
        <button class="btn btn-secondary" onclick="window.ERP.reloadAttendance(${classId})">
          Dobara Try Karein
        </button>
      </div>`;
  }
}

function _populateSheet(att) {
  if (!att) return;
  _attState.attId = att.id;
  _attState.date = att.date;
  _attState.lines = (att.student_ids || []).map(l => ({ ...l, _orig_absent: l.is_absent }));
  _attState.validated = att.state === 'validate';
  _attState.modified = new Set();
  _undoStack = [];

  const container = document.getElementById('att-sheet-container');
  if (!container) return;

  container.innerHTML = buildSheetHtml(att, _attState.className, _attState.lines);
  _attachSheetEvents();
}

function _attachSheetEvents() {
  const rollList = document.getElementById('att-roll-list');
  const submitBtn = document.getElementById('att-submit-btn');
  const undoBtn = document.getElementById('att-undo-btn');
  const draftBtn = document.getElementById('att-draft-btn');
  const allPresentBtn = document.getElementById('att-mark-all-present');

  rollList?.addEventListener('click', e => {
    const btn = e.target.closest('[data-action][data-line]');
    if (!btn || _attState.validated) return;
    const lineId = parseInt(btn.dataset.line, 10);
    _saveUndo();
    _toggleLine(lineId, btn.dataset.action === 'absent');
  });

  allPresentBtn?.addEventListener('click', () => {
    _saveUndo();
    _attState.lines.forEach(l => {
      if (!l.is_absent || l.present_absentcheck) {
        _attState.modified.add(l.id);
        l.is_present = 1;
        l.is_absent = 0;
      }
    });
    _refreshStats();
    _refreshAllRows();
  });

  undoBtn?.addEventListener('click', () => {
    if (!_undoStack.length) return;
    _attState.lines = _undoStack.pop();
    _attState.modified = new Set(
      _attState.lines.map(l => (l._orig_absent !== l.is_absent ? l.id : null)).filter(Boolean)
    );
    _refreshStats();
    _refreshAllRows();
  });

  submitBtn?.addEventListener('click', _submitAttendance);

  draftBtn?.addEventListener('click', async () => {
    try {
      await apiPost(`/api/attendance/daily/${_attState.attId}/action`, { action: 'draft' });
      toast('Haziri draft mein wapis aa gayi', 'info');
      await _loadOrCreateAttendance(_attState.classId);
    } catch (err) {
      toast(err.message, 'error');
    }
  });
}

function _toggleLine(lineId, makeAbsent) {
  const line = _attState.lines.find(l => l.id === lineId);
  if (!line) return;

  _attState.modified.add(lineId);
  line.is_present = makeAbsent ? 0 : 1;
  line.is_absent = makeAbsent ? 1 : 0;

  const row = document.querySelector(`[data-line-id="${lineId}"]`);
  if (row) {
    const pBtn = row.querySelector('[data-action="present"]');
    const aBtn = row.querySelector('[data-action="absent"]');
    pBtn?.classList.toggle('active', !makeAbsent);
    aBtn?.classList.toggle('active', makeAbsent);
    pBtn?.setAttribute('aria-pressed', String(!makeAbsent));
    aBtn?.setAttribute('aria-pressed', String(makeAbsent));
  }
  _refreshStats();
}

function _refreshStats() {
  const present = _attState.lines.filter(l => l.is_present).length;
  const absent = _attState.lines.filter(l => l.is_absent).length;
  const changed = _attState.modified.size;

  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(val);
  };
  setTxt('att-count-present', present);
  setTxt('att-count-absent', absent);
  setTxt('att-modified-count', changed);
  setTxt('att-bar-absent', absent);

  const uBtn = document.getElementById('att-undo-btn');
  if (uBtn) uBtn.disabled = _undoStack.length === 0;
}

function _refreshAllRows() {
  _attState.lines.forEach(line => {
    const row = document.querySelector(`[data-line-id="${line.id}"]`);
    if (!row) return;
    row.querySelector('[data-action="present"]')?.classList.toggle('active', !!line.is_present);
    row.querySelector('[data-action="absent"]')?.classList.toggle('active', !!line.is_absent);
  });
}

function _saveUndo() {
  _undoStack.push(_attState.lines.map(l => ({ ...l })));
  if (_undoStack.length > 10) _undoStack.shift();
}

async function _submitAttendance() {
  if (_attState.submitting || !_attState.attId) return;
  _attState.submitting = true;

  const submitBtn = document.getElementById('att-submit-btn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Jama ho raha hai...';
  }

  try {
    const lines = _attState.lines.map(l => ({
      line_id: l.id,
      is_absent: !!l.is_absent,
    }));

    await apiPost(`/api/attendance/daily/${_attState.attId}/bulk-mark`, { lines });
    await apiPost(`/api/attendance/daily/${_attState.attId}/action`, { action: 'validate' });

    const absent = lines.filter(l => l.is_absent).length;
    const present = lines.length - absent;

    toast(`✓ Haziri jama ho gayi — ${present} hazir, ${absent} ghair-hazir`, 'success', { duration: 5000 });
    await _loadOrCreateAttendance(_attState.classId);
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    _attState.submitting = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = '✓ Haziri Jama Karein';
    }
  }
}

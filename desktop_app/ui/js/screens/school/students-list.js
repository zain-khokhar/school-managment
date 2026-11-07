/**
 * school/students-list.js — Paginated Students Directory (Phase 1)
 *
 * Server-side pagination (50 per page) — no more loading 1000 students at once.
 * Filters: class, year, search (debounced 200ms).
 */

import { apiGet } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, delegate } from '../../core/dom.js';
import { fullName, stateLabel, stateBadgeClass } from '../../core/format.js';
import { openNewStudentModal, performStudentAction } from './student-modal.js';

let _listState = { page: 1, q: '', classId: '', yearId: '', total: 0, pages: 1, loading: false };
let _searchTimer = null;

export async function renderStudentsScreen() {
  const data = getBootstrap();
  const classes = data?.school?.standards || [];
  const years = data?.school?.years || [];

  const classOptions = classes.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
  const yearOptions = years.map(y => `<option value="${esc(y.id)}">${esc(y.name)}</option>`).join('');

  _listState = { page: 1, q: '', classId: '', yearId: '', total: 0, pages: 1, loading: false };

  const html = `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">🎓 Students Directory</div>
        <div class="page-header-desc" id="students-count-desc">Loading...</div>
      </div>
      <div class="page-header-actions">
        <button class="btn btn-primary" id="btn-new-student">+ Naya Admission</button>
      </div>
    </div>

    <div class="panel">
      <div class="table-filters">
        <div class="search-control" style="flex:1; min-width:200px; max-width:320px;">
          <span style="color:var(--siyahi-soft); font-size:14px;">🔍</span>
          <input type="search" id="students-search" placeholder="Naam, GR No, Roll No, mobile..."
                 autocomplete="off" style="font-size:13.5px;" />
        </div>
        <select class="form-control" id="students-class-filter" style="width:170px;" aria-label="Filter by Class">
          <option value="">Tamam Classes</option>${classOptions}
        </select>
        <select class="form-control" id="students-year-filter" style="width:170px;" aria-label="Filter by Year">
          <option value="">Tamam Saal</option>${yearOptions}
        </select>
        <button class="btn btn-secondary btn-sm" id="students-clear-filters">Reset</button>
      </div>

      <div class="table-wrap" id="students-table-wrap">
        <div class="panel-body">
          <div class="skeleton skeleton-title" style="width:160px"></div>
          ${Array(6).fill('<div class="skeleton skeleton-row" style="margin-top:4px"></div>').join('')}
        </div>
      </div>

      <div class="table-pagination" id="students-pagination" style="display:none;"></div>
    </div>`;

  setTimeout(() => {
    _attachStudentEvents();
    _loadStudents();
  }, 0);

  return html;
}

function _attachStudentEvents() {
  document.getElementById('students-search')?.addEventListener('input', e => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
      _listState.q    = e.target.value.trim();
      _listState.page = 1;
      _loadStudents();
    }, 200);
  });

  document.getElementById('students-class-filter')?.addEventListener('change', e => {
    _listState.classId = e.target.value;
    _listState.page    = 1;
    _loadStudents();
  });

  document.getElementById('students-year-filter')?.addEventListener('change', e => {
    _listState.yearId = e.target.value;
    _listState.page   = 1;
    _loadStudents();
  });

  document.getElementById('students-clear-filters')?.addEventListener('click', () => {
    ['students-search', 'students-class-filter', 'students-year-filter'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    _listState = { ..._listState, q: '', classId: '', yearId: '', page: 1 };
    _loadStudents();
  });

  document.getElementById('btn-new-student')?.addEventListener('click', () => {
    openNewStudentModal(() => _loadStudents());
  });

  const tableWrap = document.getElementById('students-table-wrap');
  delegate(tableWrap, 'click', 'tr[data-student-id]', (e, row) => {
    toast(`Student 360° Profile — Phase 2 mein khulega (ID: ${row.dataset.studentId})`, 'info');
  });

  delegate(tableWrap, 'click', '[data-student-action]', async (e, btn) => {
    e.stopPropagation();
    const id = parseInt(btn.dataset.studentId, 10);
    await performStudentAction(id, btn.dataset.studentAction, btn, () => _loadStudents());
  });
}

async function _loadStudents() {
  if (_listState.loading) return;
  _listState.loading = true;

  const tableWrap = document.getElementById('students-table-wrap');
  if (tableWrap) {
    tableWrap.innerHTML = `<div class="panel-body">
      ${Array(6).fill('<div class="skeleton skeleton-row" style="margin-bottom:2px"></div>').join('')}
    </div>`;
  }

  try {
    const res = await apiGet('/api/students/list', {
      page:     _listState.page,
      per_page: 50,
      q:        _listState.q,
      class_id: _listState.classId,
      year_id:  _listState.yearId,
    });

    _listState.total = res.total;
    _listState.pages = res.pages;
    _renderTable(res.items);
    _renderPagination(res.page, res.pages);
    _updateCountDesc(res.total);
  } catch (err) {
    if (tableWrap) {
      tableWrap.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-title">Students load nahi hue</div>
          <div class="empty-state-desc">${esc(err.message)}</div>
          <button class="btn btn-secondary" onclick="window.ERP.reloadStudents()">Dobara Try Karein</button>
        </div>`;
    }
  } finally {
    _listState.loading = false;
  }
}

function _renderTable(students) {
  const tableWrap = document.getElementById('students-table-wrap');
  if (!tableWrap) return;

  if (!students.length) {
    tableWrap.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🎓</div>
        <div class="empty-state-title">Koi student nahi mila</div>
        <div class="empty-state-desc">
          ${_listState.q || _listState.classId
            ? 'Filter change karein ya search clear karein.'
            : 'Pehla student add karein — "+ Naya Admission" button se.'}
        </div>
        ${!(_listState.q || _listState.classId)
          ? '<button class="btn btn-primary" id="btn-new-student-empty">+ Naya Admission</button>'
          : ''}
      </div>`;
    document.getElementById('btn-new-student-empty')?.addEventListener('click', () => {
      openNewStudentModal(() => _loadStudents());
    });
    return;
  }

  const rows = students.map(s => `
    <tr class="clickable" data-student-id="${esc(s.id)}" title="Detail dekhne ke liye click karein">
      <td class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(s.pid || '—')}</td>
      <td class="num" style="font-weight:600;">${esc(s.roll_no || '—')}</td>
      <td>
        <div style="font-weight:500;">${esc(fullName(s))}</div>
        ${s.contact_mobile ? `<div style="font-size:12px;color:var(--siyahi-soft);">${esc(s.contact_mobile)}</div>` : ''}
      </td>
      <td>${esc(s.class_name || '—')}</td>
      <td style="font-size:12.5px; color:var(--siyahi-soft);">${esc(s.year_name || '—')}</td>
      <td><span class="badge ${stateBadgeClass(s.state)}">${esc(stateLabel(s.state))}</span></td>
      <td>
        <div style="display:flex; gap:4px;" onclick="event.stopPropagation()">
          ${s.state === 'draft' ? `<button class="btn btn-xs btn-primary" data-student-id="${esc(s.id)}" data-student-action="admission_done">Admit</button>` : ''}
          ${s.state === 'done' ? `<button class="btn btn-xs btn-secondary" data-student-id="${esc(s.id)}" data-student-action="set_alumni">Alumni</button>` : ''}
        </div>
      </td>
    </tr>`).join('');

  tableWrap.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>GR No.</th><th class="num">Roll</th><th>Student Name</th>
          <th>Class</th><th>Year</th><th>Status</th><th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function _renderPagination(page, pages) {
  const paginationEl = document.getElementById('students-pagination');
  if (!paginationEl) return;
  if (pages <= 1) {
    paginationEl.style.display = 'none';
    return;
  }
  paginationEl.style.display = 'flex';
  paginationEl.innerHTML = `
    <span>${_listState.total} results</span>
    <div class="table-pagination-pages">
      <button class="btn btn-secondary btn-sm" id="pag-prev" ${page <= 1 ? 'disabled' : ''}>← Pehla</button>
      <span style="font-size:13px; padding:0 8px;">Page ${page} of ${pages}</span>
      <button class="btn btn-secondary btn-sm" id="pag-next" ${page >= pages ? 'disabled' : ''}>Agla →</button>
    </div>`;

  document.getElementById('pag-prev')?.addEventListener('click', () => { _listState.page--; _loadStudents(); });
  document.getElementById('pag-next')?.addEventListener('click', () => { _listState.page++; _loadStudents(); });
}

function _updateCountDesc(total) {
  const descEl = document.getElementById('students-count-desc');
  if (!descEl) return;
  const start = (_listState.page - 1) * 50 + 1;
  const end   = Math.min(_listState.page * 50, total);
  descEl.textContent = total > 0 ? `${total} students — ${start}–${end} dikha rahe hain` : 'Koi student nahi';
}

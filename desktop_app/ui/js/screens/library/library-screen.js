/**
 * screens/library/library-screen.js — Simplified Library Workspace & 1-Click Quick Issue (F14)
 *
 * Implements ADVANCEMENT_PLAN.md Section 9.8(L):
 *   - Removes mandatory manual Library Card creation step from UI (student's GR No / PID
 *     auto-provisions/resolves the library card in backend via `/api/library/quick-issue`)
 *   - Top: 3 KPIs (Available Books, Active Loans, Overdue / Fines)
 *   - Left 60%: Book Catalog & Availability Table
 *   - Right 40%: Quick Issue by Student GR + Active Loans & 1-Click Return
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap, setBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { formatDate, formatPKR, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';

export async function renderLibraryScreen() {
  const boot     = getBootstrap();
  const books    = boot?.library?.books || [];
  const issues   = boot?.library?.issues || [];
  const students = (boot?.school?.students || []).filter(s => s.state === 'done');

  const availBooks  = books.reduce((acc, b) => acc + Number(b.books_available || 0), 0);
  const activeLoans = issues.filter(i => ['issue', 'reissue'].includes(i.state)).length;
  const fineCount   = issues.filter(i => i.state === 'fine' || Number(i.penalty || 0) > 0).length;

  const stuOpts  = students.map(s => `<option value="${esc(s.id)}">${esc(s.student_name)} ${esc(s.last || '')} (${esc(s.pid)} • ${esc(s.class_name || '')})</option>`).join('');
  const bookOpts = books.filter(b => Number(b.books_available || 0) > 0).map(b =>
    `<option value="${esc(b.id)}">${esc(b.name)} (${esc(b.books_available)} available)</option>`
  ).join('');

  const html = `
    <div class="page-header">
      <div class="page-header-info">
        <div class="page-header-title">Library Catalog &amp; Quick Issue Desk</div>
        <div class="page-header-desc">Issue books directly by Student GR No. (automatic library card provisioning — F14)</div>
      </div>
      <div class="page-header-actions">
        <button type="button" class="btn btn-primary" id="lib-btn-new-book">${icon('plus', 15)} Add Book to Catalog</button>
      </div>
    </div>

    <div class="kpi-grid" style="grid-template-columns:repeat(3, 1fr);">
      <div class="kpi-card">
        <div class="kpi-label">Available Copies</div>
        <div class="kpi-value num">${esc(availBooks)}</div>
        <div class="kpi-sub">Across ${esc(books.length)} cataloged titles</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Active Book Loans</div>
        <div class="kpi-value num">${esc(activeLoans)}</div>
        <div class="kpi-sub">Currently checked out</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Overdue / Fine Records</div>
        <div class="kpi-value num">${esc(fineCount)}</div>
        <div class="kpi-sub">Pending late return settlement</div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1.35fr 1fr; gap:var(--sp-5); align-items:start;">
      <!-- Left 60%: Book Catalog Table -->
      <div class="panel">
        <div class="panel-header"><div class="panel-title">Book Catalog &amp; Live Availability</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Book Title</th><th>ISBN / Code</th><th class="num">Available / Total</th><th>Status</th></tr>
            </thead>
            <tbody>
              ${books.map(b => `
                <tr>
                  <td style="font-weight:600;">${esc(b.name)}</td>
                  <td class="num" style="font-size:12px; color:var(--siyahi-soft);">${esc(b.isbn || b.code || '—')}</td>
                  <td class="num" style="font-weight:600;">${esc(b.books_available)} / ${esc(b.qty_available)}</td>
                  <td><span class="badge ${stateBadgeClass(b.availability)}">${esc(stateLabel(b.availability))}</span></td>
                </tr>`).join('') || `<tr><td colspan="4" style="padding:20px; text-align:center;">No books in catalog.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right 40%: Quick Issue Form + Active Loans -->
      <div>
        <div class="panel" style="margin-bottom:var(--sp-4);">
          <div class="panel-header"><div class="panel-title">1-Click Quick Issue by Student GR (F14)</div></div>
          <form id="lib-quick-issue-form" class="panel-body">
            <div class="form-group">
              <label class="form-label required" for="lqi-stu">Student (GR No / Name)</label>
              <select class="form-control" id="lqi-stu" required>${stuOpts}</select>
            </div>
            <div class="form-group">
              <label class="form-label required" for="lqi-book">Available Book</label>
              <select class="form-control" id="lqi-book" required>${bookOpts}</select>
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%;">Issue Book Now</button>
          </form>
        </div>

        <div class="panel">
          <div class="panel-header"><div class="panel-title">Active &amp; Recent Loans</div></div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Code</th><th>Borrower</th><th>Book</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>
                ${issues.slice(0, 12).map(iss => `
                  <tr>
                    <td class="num" style="font-size:12px;">${esc(iss.issue_code)}</td>
                    <td style="font-weight:500;">${esc(iss.card_name || 'Student')}</td>
                    <td>${esc(iss.book_name || `#${iss.book_id}`)}</td>
                    <td>
                      <span class="badge ${stateBadgeClass(iss.state)}">${esc(stateLabel(iss.state))}</span>
                      ${Number(iss.penalty || 0) > 0 ? `<div class="num" style="font-size:11px; color:var(--danger-text);">${esc(formatPKR(iss.penalty))}</div>` : ''}
                    </td>
                    <td>
                      ${['issue', 'reissue'].includes(iss.state)
                        ? `<button type="button" class="btn btn-xs btn-secondary" data-lib-ret="${esc(iss.id)}">Return</button>`
                        : (iss.state === 'fine' ? `<button type="button" class="btn btn-xs btn-primary" data-lib-pay="${esc(iss.id)}">Pay Fine</button>` : `<span>${esc(formatDate(iss.date_return))}</span>`)}
                    </td>
                  </tr>`).join('') || `<tr><td colspan="5" style="padding:16px; text-align:center;">No book loans recorded.</td></tr>`}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>`;

  setTimeout(_bindLibraryEvents, 20);
  return html;
}

async function _refreshLib() {
  const fresh = await apiGet('/api/bootstrap');
  setBootstrap(fresh);
  const mainEl = document.getElementById('main-view');
  if (mainEl) mainEl.innerHTML = await renderLibraryScreen();
}

function _bindLibraryEvents() {
  document.getElementById('lib-quick-issue-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const student_id = parseInt(document.getElementById('lqi-stu')?.value, 10);
    const book_id    = parseInt(document.getElementById('lqi-book')?.value, 10);
    try {
      const res = await apiPost('/api/library/quick-issue', { student_id, book_id });
      toast(`Book issued on card ${res.card_code}`, 'success');
      await _refreshLib();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  document.querySelectorAll('[data-lib-ret]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.libRet;
      await apiPost(`/api/library/issues/${id}/action`, { action: 'return' });
      toast('Book returned to library stock', 'success');
      await _refreshLib();
    });
  });

  document.querySelectorAll('[data-lib-pay]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.libPay;
      await apiPost(`/api/library/issues/${id}/action`, { action: 'pay_fine' });
      toast('Overdue library fine settled', 'success');
      await _refreshLib();
    });
  });

  document.getElementById('lib-btn-new-book')?.addEventListener('click', () => {
    openModal('Add Book to Library Catalog', `
      <div class="form-group">
        <label class="form-label required" for="nb-title">Book Title</label>
        <input class="form-control" id="nb-title" placeholder="e.g. Oxford Secondary Physics" required autofocus />
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div class="form-group">
          <label class="form-label" for="nb-isbn">ISBN</label>
          <input class="form-control num" id="nb-isbn" placeholder="978-0-19-842800-0" />
        </div>
        <div class="form-group">
          <label class="form-label required" for="nb-qty">Total Copies</label>
          <input class="form-control num" id="nb-qty" type="number" min="1" value="5" required />
        </div>
      </div>
    `, async () => {
      await apiPost('/api/library/books', {
        name:          document.getElementById('nb-title')?.value?.trim(),
        isbn:          document.getElementById('nb-isbn')?.value?.trim() || null,
        qty_available: parseInt(document.getElementById('nb-qty')?.value || '1', 10),
      });
      closeModal();
      toast('Book added to catalog', 'success');
      await _refreshLib();
    }, { submitLabel: 'Save Book' });
  });
}

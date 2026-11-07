/**
 * screens/fees/vouchers-tab.js — Server-Paginated Vouchers Register & Counter (G4, S1, R-F2)
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap, get, set } from '../../core/state.js';
import { esc, toast } from '../../core/dom.js';
import { formatPaisa, formatDate, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { navigateTo } from '../../core/router.js';
import { openVoucherPrintPreview } from '../../print/voucher-print.js';
import { openSingleReceiptPrint } from '../../print/receipt-print.js';
import {
  openBulkGenerateModal,
  openReceivePaymentModal,
  getRecentUndoReceipt,
  clearRecentUndoReceipt,
} from './fee-modals.js';

export { openBulkGenerateModal, openReceivePaymentModal };

let _vState = { page: 1, q: '', class_id: '', state: '', billing_month: '' };

export function setVouchersMonthFilter(bm) {
  if (bm) { _vState.billing_month = bm; _vState.page = 1; }
}

export async function renderVouchersSubTab(mountEl, onRefreshKpis) {
  const wasFocusedSearch = document.activeElement?.id === 'vf-q';
  const cursorPos = wasFocusedSearch ? (document.activeElement.selectionStart ?? null) : null;
  const presetQ = get('feesQuery');
  if (presetQ) {
    _vState.q = presetQ;
    set({ feesQuery: '' });
  }

  const classes = getBootstrap()?.school?.standards || [];
  const data = await apiGet('/api/fees/vouchers', {
    page: _vState.page,
    per_page: 25,
    q: _vState.q,
    class_id: _vState.class_id,
    state: _vState.state,
    billing_month: _vState.billing_month,
  });

  const undoItem = getRecentUndoReceipt();
  const undoBanner = undoItem ? `
    <div class="undo-receipt-banner">
      <div>
        <strong>Receipt ${esc(undoItem.receiptNo)}</strong> recorded (${esc(formatPaisa(undoItem.amountPaisa))}).
        Made a mistake? You can undo this entry within 30 seconds without admin override.
      </div>
      <div style="display:flex; gap:8px;">
        <button type="button" class="btn btn-xs btn-secondary" id="vch-banner-print">${icon('printer', 13)} Print Receipt</button>
        <button type="button" class="btn btn-xs btn-primary" id="vch-banner-undo">${icon('undo', 13)} Undo Receipt</button>
      </div>
    </div>` : '';

  const rowsHtml = (data.items || []).map(v => `
    <tr>
      <td class="num" style="font-weight:600;">${esc(v.voucher_display)}</td>
      <td>
        <button type="button" class="btn btn-ghost btn-xs" data-vch-s360="${esc(v.student_id)}" style="font-weight:600; padding:0;">
          ${esc(v.student_name)} ${esc(v.last || '')}
        </button>
        <div style="font-size:11.5px; color:var(--siyahi-soft);">GR: ${esc(v.pid || '—')}</div>
      </td>
      <td>${esc(v.class_name || '—')}</td>
      <td class="num">${esc(v.billing_month || formatDate(v.date))}</td>
      <td class="num">${esc(formatPaisa(v.total_paisa))}</td>
      <td class="num">${esc(formatPaisa(v.paid_paisa))}</td>
      <td class="num" style="font-weight:600;">${esc(formatPaisa(v.due_paisa))}</td>
      <td><span class="badge ${stateBadgeClass(v.state)}">${esc(stateLabel(v.state))}</span></td>
      <td>
        <div style="display:flex; gap:5px; flex-wrap:wrap;">
          ${v.due_paisa > 0 && ['confirm', 'pending'].includes(v.state)
            ? `<button type="button" class="btn btn-xs btn-primary" data-vch-pay="${esc(v.id)}">Receive</button>`
            : ''}
          <button type="button" class="btn btn-xs btn-secondary" data-vch-print="${esc(v.id)}" title="Print 3-Part Bank Voucher">${icon('printer', 13)}</button>
        </div>
      </td>
    </tr>`).join('');

  mountEl.innerHTML = `
    ${undoBanner}
    <div class="panel">
      <div class="fees-filter-bar">
        <input type="search" class="form-control" id="vf-q" placeholder="Search voucher #, student, GR, mobile..." value="${esc(_vState.q)}" style="flex:1; min-width:210px;" />
        <select class="form-control" id="vf-class" style="width:165px;">
          <option value="">All Classes</option>
          ${classes.map(c => `<option value="${esc(c.id)}" ${String(_vState.class_id) === String(c.id) ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}
        </select>
        <select class="form-control" id="vf-state" style="width:150px;">
          <option value="">All Statuses</option>
          <option value="confirm" ${_vState.state === 'confirm' ? 'selected' : ''}>Open</option>
          <option value="pending" ${_vState.state === 'pending' ? 'selected' : ''}>Partial</option>
          <option value="paid" ${_vState.state === 'paid' ? 'selected' : ''}>Paid</option>
          <option value="rolled_over" ${_vState.state === 'rolled_over' ? 'selected' : ''}>Carried Forward</option>
        </select>
        <input type="month" class="form-control" id="vf-month" value="${esc(_vState.billing_month)}" style="width:155px;" title="Billing month" />
        <button type="button" class="btn btn-secondary btn-sm" id="vf-reset">Reset</button>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Voucher #</th><th>Student</th><th>Class</th><th>Month / Date</th>
              <th class="num">Total</th><th class="num">Paid</th><th class="num">Balance Due</th><th>Status</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="9" style="text-align:center; padding:28px; color:var(--siyahi-soft);">No fee vouchers matched the current filters.</td></tr>`}
          </tbody>
        </table>
      </div>

      <div class="panel-body" style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--rule-line); padding:10px 18px; font-size:12.5px;">
        <span>Showing page <strong class="num">${data.page}</strong> of <strong class="num">${data.pages}</strong> (<span class="num">${data.total}</span> total vouchers)</span>
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn btn-xs btn-secondary" id="vf-prev" ${data.page <= 1 ? 'disabled' : ''}>Previous</button>
          <button type="button" class="btn btn-xs btn-secondary" id="vf-next" ${data.page >= data.pages ? 'disabled' : ''}>Next</button>
        </div>
      </div>
    </div>`;

  const reload = async () => {
    await renderVouchersSubTab(mountEl, onRefreshKpis);
    onRefreshKpis?.();
  };

  const voucherMap = new Map((data.items || []).map(v => [Number(v.id), v]));
  const qInput = document.getElementById('vf-q');
  if (wasFocusedSearch && qInput) {
    qInput.focus();
    const pos = cursorPos ?? qInput.value.length;
    qInput.setSelectionRange(pos, pos);
  }
  let qTimer = null;
  qInput?.addEventListener('input', e => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => { _vState.q = e.target.value.trim(); _vState.page = 1; reload(); }, 220);
  });
  document.getElementById('vf-class')?.addEventListener('change', e => { _vState.class_id = e.target.value; _vState.page = 1; reload(); });
  document.getElementById('vf-state')?.addEventListener('change', e => { _vState.state = e.target.value; _vState.page = 1; reload(); });
  document.getElementById('vf-month')?.addEventListener('change', e => { _vState.billing_month = e.target.value; _vState.page = 1; reload(); });
  document.getElementById('vf-reset')?.addEventListener('click', () => {
    _vState = { page: 1, q: '', class_id: '', state: '', billing_month: '' };
    reload();
  });
  document.getElementById('vf-prev')?.addEventListener('click', () => { _vState.page = Math.max(1, _vState.page - 1); reload(); });
  document.getElementById('vf-next')?.addEventListener('click', () => { _vState.page += 1; reload(); });

  document.getElementById('vch-banner-print')?.addEventListener('click', () => {
    if (undoItem) openSingleReceiptPrint(undoItem.paymentId);
  });
  document.getElementById('vch-banner-undo')?.addEventListener('click', async () => {
    if (!undoItem) return;
    try {
      await apiPost(`/api/fees/payments/${undoItem.paymentId}/reverse`, { reason: 'Quick undo within 30s window' });
      toast(`Receipt ${undoItem.receiptNo} undone.`, 'info');
      clearRecentUndoReceipt();
      reload();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  mountEl.querySelectorAll('[data-vch-s360]').forEach(b => {
    b.onclick = () => navigateTo('student360', { selectedStudentId: parseInt(b.getAttribute('data-vch-s360'), 10) });
  });
  mountEl.querySelectorAll('[data-vch-pay]').forEach(b => {
    b.onclick = () => {
      const v = voucherMap.get(parseInt(b.getAttribute('data-vch-pay'), 10));
      if (v) openReceivePaymentModal(v, reload);
    };
  });
  mountEl.querySelectorAll('[data-vch-print]').forEach(b => {
    b.onclick = () => openVoucherPrintPreview({ payslipIds: [parseInt(b.getAttribute('data-vch-print'), 10)] });
  });
}

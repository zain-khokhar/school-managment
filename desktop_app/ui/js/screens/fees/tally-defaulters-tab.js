/**
 * screens/fees/tally-defaulters-tab.js — Daily Cash Tally, Reversals & Defaulters Aging
 *
 * Implements R-F2 (30s clerk Undo vs post-30s Admin reversal with reason + audit)
 * and R-F4 (exact paisa-by-paisa daily collection tally by payment mode).
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap, get } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { formatPaisa, formatDate, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { navigateTo } from '../../core/router.js';
import { openSingleReceiptPrint } from '../../print/receipt-print.js';
import { openVoucherPrintPreview } from '../../print/voucher-print.js';
import { openReceivePaymentModal } from './vouchers-tab.js';

let _tallyDate = new Date().toISOString().slice(0, 10);
let _defClassId = '';
let _defMinDays = 0;

function _handleReverseReceipt(receipt, onDone) {
  const role = get('role') || 'admin';
  const paidMs = Date.parse((receipt.paid_at || '').replace(' ', 'T'));
  const within30s = !Number.isNaN(paidMs) && (Date.now() - paidMs) <= 30000;

  if (within30s) {
    apiPost(`/api/fees/payments/${receipt.id}/reverse`, { reason: 'Quick undo within 30s window' })
      .then(() => { toast(`Receipt ${receipt.receipt_no} undone.`, 'info'); onDone?.(); })
      .catch(err => toast(err.message, 'error'));
    return;
  }

  if (!['admin', 'principal'].includes(role)) {
    toast('The 30-second undo window has expired. Ask an Administrator or Principal to reverse this receipt.', 'warn');
    return;
  }

  openModal(`Reverse Settled Receipt — ${receipt.receipt_no}`, `
    <p style="font-size:13px; color:var(--siyahi-soft); margin-bottom:12px;">
      Reversing <strong>${esc(formatPaisa(receipt.amount_paisa))}</strong> for <strong>${esc(receipt.student_name)}</strong> will restore the unpaid balance on voucher <strong>${esc(receipt.voucher_no || receipt.slip_number)}</strong> and record a permanent audit entry.
    </p>
    <div class="form-group">
      <label class="form-label required" for="rev-reason">Mandatory Reversal Reason</label>
      <input class="form-control" id="rev-reason" placeholder="e.g. Dishonoured cheque / wrong student selected" required minlength="3" />
    </div>
  `, async () => {
    const reason = document.getElementById('rev-reason')?.value?.trim() || '';
    await apiPost(`/api/fees/payments/${receipt.id}/reverse`, { reason });
    closeModal();
    toast(`Receipt ${receipt.receipt_no} reversed and logged to audit trail.`, 'info');
    onDone?.();
  }, { submitLabel: 'Confirm Reversal' });
}

export async function renderTallySubTab(mountEl, onRefreshKpis) {
  const tally = await apiGet('/api/fees/tally', { date: _tallyDate });
  const bm = tally.by_mode_paisa || {};
  const role = get('role') || 'admin';

  const rowsHtml = (tally.receipts || []).map(r => {
    const isRev = Boolean(r.reversed_at);
    const paidMs = Date.parse((r.paid_at || '').replace(' ', 'T'));
    const canQuickUndo = !isRev && !Number.isNaN(paidMs) && (Date.now() - paidMs) <= 30000;
    const canAdminRev  = !isRev && ['admin', 'principal'].includes(role);

    return `
      <tr>
        <td class="num" style="font-weight:600;">${esc(r.receipt_no)}</td>
        <td>${esc(r.student_name)} ${esc(r.last || '')} <span style="color:var(--siyahi-soft); font-size:11.5px;">(${esc(r.class_name || r.pid || '—')})</span></td>
        <td class="num">${esc(r.voucher_no || r.slip_number || '—')}</td>
        <td style="text-transform:uppercase; font-size:11.5px;">${esc(r.payment_mode)}${r.reference ? ` • ${esc(r.reference)}` : ''}</td>
        <td style="font-size:12px; color:var(--siyahi-soft);">${esc(r.received_by || '—')}</td>
        <td class="num" style="font-weight:600;">${esc(formatPaisa(r.amount_paisa))}</td>
        <td>${isRev
          ? `<span class="badge badge-danger" title="${esc(r.reversal_reason || '')}">Reversed</span>`
          : `<span class="badge badge-success">Settled</span>`}</td>
        <td>
          <div style="display:flex; gap:5px;">
            <button type="button" class="btn btn-xs btn-secondary" data-tly-print="${esc(r.id)}">${icon('printer', 12)} Slip</button>
            ${canQuickUndo
              ? `<button type="button" class="btn btn-xs btn-primary" data-tly-rev="${esc(r.id)}">${icon('undo', 12)} Undo</button>`
              : (canAdminRev ? `<button type="button" class="btn btn-xs btn-secondary" data-tly-rev="${esc(r.id)}">Reverse</button>` : '')}
          </div>
        </td>
      </tr>`;
  }).join('');

  mountEl.innerHTML = `
    <div class="panel" style="margin-bottom:var(--sp-4);">
      <div class="fees-filter-bar" style="border-bottom:none; justify-content:space-between;">
        <div style="display:flex; align-items:center; gap:10px;">
          <label for="tly-date" style="font-size:13px; font-weight:600;">Collection Date:</label>
          <input type="date" class="form-control" id="tly-date" value="${esc(_tallyDate)}" style="width:165px;" />
          <button type="button" class="btn btn-secondary btn-sm" id="tly-today">Today</button>
        </div>
        <div style="font-size:12.5px; color:var(--siyahi-soft);">
          Active Receipts: <strong class="num" style="color:var(--siyahi);">${esc(tally.active_receipts_count)}</strong> •
          Reversed: <strong class="num" style="color:var(--siyahi);">${esc(tally.reversed_count)}</strong> (${esc(formatPaisa(tally.reversed_paisa || 0))})
        </div>
      </div>
    </div>

    <div class="tally-mode-grid">
      <div class="tally-mode-card"><div class="tally-mode-label">Net Collected</div><div class="tally-mode-val">${esc(formatPaisa(tally.net_collected_paisa))}</div></div>
      <div class="tally-mode-card"><div class="tally-mode-label">Cash Counter</div><div class="tally-mode-val">${esc(formatPaisa(bm.cash || 0))}</div></div>
      <div class="tally-mode-card"><div class="tally-mode-label">Bank Deposit</div><div class="tally-mode-val">${esc(formatPaisa(bm.bank || 0))}</div></div>
      <div class="tally-mode-card"><div class="tally-mode-label">Online / IBFT</div><div class="tally-mode-val">${esc(formatPaisa(bm.online || 0))}</div></div>
      <div class="tally-mode-card"><div class="tally-mode-label">Cheque / Pay Order</div><div class="tally-mode-val">${esc(formatPaisa(bm.cheque || 0))}</div></div>
    </div>

    <div class="panel">
      <div class="panel-header"><div class="panel-title">Daily Receipt Register (${esc(formatDate(_tallyDate))})</div></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Receipt #</th><th>Student</th><th>Voucher #</th><th>Mode / Ref</th><th>Cashier</th><th class="num">Amount</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="8" style="text-align:center; padding:26px; color:var(--siyahi-soft);">No fee payments recorded on ${esc(formatDate(_tallyDate))}.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>`;

  const reload = async () => { await renderTallySubTab(mountEl, onRefreshKpis); onRefreshKpis?.(); };
  const rcpMap = new Map((tally.receipts || []).map(r => [Number(r.id), r]));

  document.getElementById('tly-date')?.addEventListener('change', e => { _tallyDate = e.target.value; reload(); });
  document.getElementById('tly-today')?.addEventListener('click', () => { _tallyDate = new Date().toISOString().slice(0, 10); reload(); });
  mountEl.querySelectorAll('[data-tly-print]').forEach(b => {
    b.onclick = () => openSingleReceiptPrint(parseInt(b.getAttribute('data-tly-print'), 10));
  });
  mountEl.querySelectorAll('[data-tly-rev]').forEach(b => {
    b.onclick = () => {
      const rcp = rcpMap.get(parseInt(b.getAttribute('data-tly-rev'), 10));
      if (rcp) _handleReverseReceipt(rcp, reload);
    };
  });
}

export async function renderDefaultersSubTab(mountEl, onRefreshKpis) {
  const classes = getBootstrap()?.school?.standards || [];
  const res = await apiGet('/api/fees/defaulters', {
    class_id: _defClassId,
    min_days_overdue: _defMinDays,
  });
  const items = res.items || [];

  const rowsHtml = items.map(v => `
    <tr>
      <td class="num" style="font-weight:600;">${esc(v.voucher_display)}</td>
      <td>
        <button type="button" class="btn btn-ghost btn-xs" data-def-s360="${esc(v.student_id)}" style="font-weight:600; padding:0;">
          ${esc(v.student_name)} ${esc(v.last || '')}
        </button>
        <div style="font-size:11.5px; color:var(--siyahi-soft);">GR: ${esc(v.pid || '—')} • ${esc(v.contact_mobile || 'No mobile')}</div>
      </td>
      <td>${esc(v.class_name || '—')}</td>
      <td class="num">${esc(formatDate(v.due_date || v.date))}</td>
      <td>
        <span class="badge ${v.days_overdue >= 30 ? 'badge-danger' : (v.days_overdue > 0 ? 'badge-warn' : 'badge-neutral')}">
          ${v.days_overdue > 0 ? `${esc(v.days_overdue)}d Overdue` : 'Within Due Date'}
        </span>
      </td>
      <td class="num" style="font-weight:600;">${esc(formatPaisa(v.due_paisa))}</td>
      <td>
        <div style="display:flex; gap:5px;">
          <button type="button" class="btn btn-xs btn-primary" data-def-pay="${esc(v.id)}">Receive</button>
          <button type="button" class="btn btn-xs btn-secondary" data-def-print="${esc(v.id)}">${icon('printer', 12)}</button>
        </div>
      </td>
    </tr>`).join('');

  mountEl.innerHTML = `
    <div class="panel">
      <div class="fees-filter-bar">
        <select class="form-control" id="def-class" style="width:180px;">
          <option value="">All Classes</option>
          ${classes.map(c => `<option value="${esc(c.id)}" ${String(_defClassId) === String(c.id) ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}
        </select>
        <select class="form-control" id="def-aging" style="width:190px;">
          <option value="0" ${_defMinDays === 0 ? 'selected' : ''}>All Unpaid Vouchers</option>
          <option value="1" ${_defMinDays === 1 ? 'selected' : ''}>Past Due Date (1+ days)</option>
          <option value="15" ${_defMinDays === 15 ? 'selected' : ''}>15+ Days Overdue</option>
          <option value="30" ${_defMinDays === 30 ? 'selected' : ''}>30+ Days Critical Arrears</option>
        </select>
        <span style="margin-left:auto; font-size:13px; color:var(--siyahi-soft);">
          Filtered Arrears: <strong class="num" style="color:var(--siyahi);">${esc(formatPaisa(res.total_due_paisa || 0))}</strong> (${esc(res.total || 0)} vouchers)
        </span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Voucher #</th><th>Student &amp; Contact</th><th>Class</th><th>Due Date</th><th>Aging</th><th class="num">Balance Due</th><th>Action</th></tr></thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="7" style="text-align:center; padding:26px; color:var(--siyahi-soft);">Zero unpaid vouchers match this aging filter.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>`;

  const reload = async () => { await renderDefaultersSubTab(mountEl, onRefreshKpis); onRefreshKpis?.(); };
  const vMap = new Map(items.map(v => [Number(v.id), v]));

  document.getElementById('def-class')?.addEventListener('change', e => { _defClassId = e.target.value; reload(); });
  document.getElementById('def-aging')?.addEventListener('change', e => { _defMinDays = parseInt(e.target.value || '0', 10); reload(); });
  mountEl.querySelectorAll('[data-def-s360]').forEach(b => {
    b.onclick = () => navigateTo('student360', { selectedStudentId: parseInt(b.getAttribute('data-def-s360'), 10) });
  });
  mountEl.querySelectorAll('[data-def-pay]').forEach(b => {
    b.onclick = () => {
      const v = vMap.get(parseInt(b.getAttribute('data-def-pay'), 10));
      if (v) openReceivePaymentModal(v, reload);
    };
  });
  mountEl.querySelectorAll('[data-def-print]').forEach(b => {
    b.onclick = () => openVoucherPrintPreview({ payslipIds: [parseInt(b.getAttribute('data-def-print'), 10)] });
  });
}


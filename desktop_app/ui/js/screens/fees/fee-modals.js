/**
 * screens/fees/fee-modals.js — Bulk Voucher Generator & Partial/Full Payment Modals
 *
 * Extracted from `vouchers-tab.js` so every JS module stays well under 200-250 lines.
 */

import { apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { formatPaisa, formatPKR } from '../../core/format.js';
import { openSingleReceiptPrint } from '../../print/receipt-print.js';

let _recentUndo = null; // { paymentId, receiptNo, amountPaisa, expiresAt }

export function getRecentUndoReceipt() {
  if (_recentUndo && Date.now() < _recentUndo.expiresAt) return _recentUndo;
  return null;
}

export function clearRecentUndoReceipt() {
  _recentUndo = null;
}

export function openBulkGenerateModal(onSuccess) {
  const boot = getBootstrap();
  const classes = boot?.school?.standards || [];
  const structs = boot?.fees?.structures || [];
  const nowMonth = new Date().toISOString().slice(0, 7);
  const defaultDue = `${nowMonth}-10`;

  if (!structs.length) {
    toast('Please create at least one Fee Structure before generating monthly vouchers.', 'warn');
    return;
  }

  openModal('Bulk Generate Monthly Fee Vouchers', `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="bg-month">Billing Month (YYYY-MM)</label>
        <input class="form-control" id="bg-month" type="month" value="${esc(nowMonth)}" required />
      </div>
      <div class="form-group">
        <label class="form-label required" for="bg-due">Due Date</label>
        <input class="form-control" id="bg-due" type="date" value="${esc(defaultDue)}" required />
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label" for="bg-class">Target Class</label>
        <select class="form-control" id="bg-class">
          <option value="">All Active Classes (Whole School)</option>
          ${classes.map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="bg-struct">Fee Structure</label>
        <select class="form-control" id="bg-struct" required>
          ${structs.map(s => `<option value="${esc(s.id)}">${esc(s.name)} (${esc(formatPKR(s.total_amount || 0))})</option>`).join('')}
        </select>
      </div>
    </div>
    <label style="display:flex; align-items:center; gap:8px; margin-bottom:8px; font-size:13px;">
      <input type="checkbox" id="bg-rules" checked />
      <span>Apply active scholarships, sibling concessions &amp; seasonal fee rules</span>
    </label>
    <label style="display:flex; align-items:center; gap:8px; font-size:13px;">
      <input type="checkbox" id="bg-arrears" checked />
      <span>Carry forward prior unpaid arrears automatically</span>
    </label>
  `, async () => {
    const billing_month = document.getElementById('bg-month')?.value?.trim();
    const due_date = document.getElementById('bg-due')?.value?.trim();
    const classVal = document.getElementById('bg-class')?.value;
    const fees_structure_id = parseInt(document.getElementById('bg-struct')?.value || '0', 10);

    const res = await apiPost('/api/fees/vouchers/bulk-generate', {
      billing_month,
      due_date,
      class_id: classVal ? parseInt(classVal, 10) : null,
      fees_structure_id,
      apply_rules: document.getElementById('bg-rules')?.checked ?? true,
      include_arrears: document.getElementById('bg-arrears')?.checked ?? true,
    });
    closeModal();
    toast(
      `Generated ${res.created_count} voucher(s) for ${res.billing_month}${res.skipped_count ? ` (${res.skipped_count} already existed)` : ''}`,
      'success'
    );
    onSuccess?.(billing_month);
  }, { submitLabel: 'Generate Vouchers' });
}

export function openReceivePaymentModal(voucher, onSuccess) {
  const maxRupees = (voucher.due_paisa / 100).toFixed(2);
  const stuName = [voucher.student_name, voucher.last].filter(Boolean).join(' ');

  openModal(`Receive Fee Payment — ${voucher.voucher_display}`, `
    <div style="background:var(--surface-sunken, #FAF8F5); border:1px solid var(--rule-line); border-radius:var(--radius); padding:10px 14px; margin-bottom:14px; font-size:13px;">
      <div><strong>${esc(stuName)}</strong> (${esc(voucher.pid || '—')} • ${esc(voucher.class_name || '—')})</div>
      <div style="display:flex; gap:16px; margin-top:4px; color:var(--siyahi-soft);">
        <span>Total: <strong class="num" style="color:var(--siyahi);">${esc(formatPaisa(voucher.total_paisa))}</strong></span>
        <span>Paid: <strong class="num" style="color:var(--siyahi);">${esc(formatPaisa(voucher.paid_paisa))}</strong></span>
        <span>Balance Due: <strong class="num" style="color:var(--siyahi);">${esc(formatPaisa(voucher.due_paisa))}</strong></span>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="pmt-amount">Amount Received (PKR)</label>
        <input class="form-control num" id="pmt-amount" type="number" step="0.01" min="0.01" max="${esc(maxRupees)}" value="${esc(maxRupees)}" required />
        <div class="form-hint">Partial or full amount up to Rs. ${esc(maxRupees)}</div>
      </div>
      <div class="form-group">
        <label class="form-label required" for="pmt-mode">Payment Mode</label>
        <select class="form-control" id="pmt-mode">
          <option value="cash">Cash Counter</option>
          <option value="bank">Bank Deposit Slip</option>
          <option value="online">Online / IBFT Transfer</option>
          <option value="cheque">Cheque / Pay Order</option>
        </select>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label" for="pmt-ref">Bank / Cheque / Txn Ref</label>
        <input class="form-control" id="pmt-ref" placeholder="Optional slip or transaction #" />
      </div>
      <div class="form-group">
        <label class="form-label" for="pmt-note">Cashier Note</label>
        <input class="form-control" id="pmt-note" placeholder="Optional remark" />
      </div>
    </div>
    <label style="display:flex; align-items:center; gap:8px; font-size:13px;">
      <input type="checkbox" id="pmt-auto-print" />
      <span>Open printable fee receipt immediately after saving</span>
    </label>
  `, async () => {
    const res = await apiPost('/api/fees/payments', {
      payslip_id:    voucher.id,
      amount_rupees: document.getElementById('pmt-amount')?.value?.trim(),
      payment_mode:  document.getElementById('pmt-mode')?.value || 'cash',
      reference:     document.getElementById('pmt-ref')?.value?.trim() || '',
      note:          document.getElementById('pmt-note')?.value?.trim() || '',
    });
    const autoPrint = document.getElementById('pmt-auto-print')?.checked;
    closeModal();

    const pmt = res.payment;
    _recentUndo = {
      paymentId: pmt.id,
      receiptNo: pmt.receipt_no,
      amountPaisa: pmt.amount_paisa,
      expiresAt: Date.now() + 30000,
    };

    toast(`Receipt ${pmt.receipt_no} saved (${formatPaisa(pmt.amount_paisa)})`, 'success', {
      duration: 28000,
      undoLabel: 'Undo (30s)',
      undoFn: async () => {
        try {
          await apiPost(`/api/fees/payments/${pmt.id}/reverse`, { reason: 'Quick undo within 30s window' });
          _recentUndo = null;
          toast(`Receipt ${pmt.receipt_no} undone and balance restored.`, 'info');
          onSuccess?.();
        } catch (err) {
          toast(err.message, 'error');
        }
      },
    });

    onSuccess?.();
    if (autoPrint) openSingleReceiptPrint(pmt.id);
  }, { submitLabel: 'Confirm Receipt' });
}


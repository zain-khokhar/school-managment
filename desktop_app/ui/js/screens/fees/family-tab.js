/**
 * screens/fees/family-tab.js — Consolidated Family Ledger & Multi-Sibling Fee Counter (S2, R-F1)
 *
 * Searches families by guardian name, mobile, CNIC, student name, or GR No;
 * links siblings to a shared guardian; and collects a single atomic payment across siblings.
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap, get, set } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { formatPaisa, formatDate, stateLabel, stateBadgeClass } from '../../core/format.js';
import { icon } from '../../core/icons.js';
import { navigateTo } from '../../core/router.js';
import { openFamilyReceiptPrint, openSingleReceiptPrint } from '../../print/receipt-print.js';
import { openVoucherPrintPreview } from '../../print/voucher-print.js';

let _famQuery = '';
let _onlyWithDues = false;
let _selectedFamilyKey = '';

function _openLinkGuardianModal(onSaved) {
  const students = (getBootstrap()?.school?.students || []).filter(s => s.active !== 0);
  openModal('Link Guardian & Sibling Account', `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="lg-name">Guardian Full Name</label>
        <input class="form-control" id="lg-name" placeholder="e.g. Tariq Mehmood" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="lg-rel">Relationship</label>
        <select class="form-control" id="lg-rel">
          <option value="Father">Father</option>
          <option value="Mother">Mother</option>
          <option value="Guardian">Guardian</option>
        </select>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="lg-phone">Mobile / Phone</label>
        <input class="form-control" id="lg-phone" placeholder="0300-1234567" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="lg-cnic">CNIC Number</label>
        <input class="form-control" id="lg-cnic" placeholder="35202-1234567-1" />
      </div>
    </div>
    <div class="form-group">
      <label class="form-label required">Select Siblings to Link (check one or more students)</label>
      <div style="max-height:190px; overflow-y:auto; border:1px solid var(--rule-line); border-radius:var(--radius); padding:8px 12px;">
        ${students.map(s => `
          <label style="display:flex; align-items:center; gap:8px; padding:4px 0; font-size:13px;">
            <input type="checkbox" name="lg-stu" value="${esc(s.id)}" />
            <span><strong>${esc(s.student_name)} ${esc(s.last || '')}</strong> — ${esc(s.pid || '')} (${esc(s.class_name || '—')})</span>
          </label>`).join('')}
      </div>
    </div>
  `, async () => {
    const checked = Array.from(document.querySelectorAll('input[name="lg-stu"]:checked')).map(el => parseInt(el.value, 10));
    const res = await apiPost('/api/families/guardian', {
      name:        document.getElementById('lg-name')?.value?.trim(),
      relation:    document.getElementById('lg-rel')?.value || 'Father',
      phone:       document.getElementById('lg-phone')?.value?.trim(),
      cnic:        document.getElementById('lg-cnic')?.value?.trim(),
      student_ids: checked,
    });
    closeModal();
    _selectedFamilyKey = res.family_key;
    toast('Guardian and sibling family account linked.', 'success');
    onSaved?.();
  }, { submitLabel: 'Save Family Link' });
}

function _openFamilyPaymentModal(ledger, onPaid) {
  const maxRupees = (ledger.summary.total_due_paisa / 100).toFixed(2);
  const fkey = ledger.family_key;

  openModal(`Receive Family Fee — ${ledger.guardian.name}`, `
    <div style="background:var(--surface-sunken, #FAF8F5); border:1px solid var(--rule-line); border-radius:var(--radius); padding:10px 14px; margin-bottom:12px; font-size:13px;">
      <div><strong>${esc(ledger.guardian.name)}</strong> • ${esc(ledger.children.length)} enrolled student(s)</div>
      <div style="margin-top:4px; color:var(--siyahi-soft);">
        Open Vouchers: <strong class="num" style="color:var(--siyahi);">${esc(ledger.summary.open_vouchers_count)}</strong> •
        Consolidated Balance: <strong class="num" style="color:var(--siyahi);">${esc(formatPaisa(ledger.summary.total_due_paisa))}</strong>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="fp-amt">Total Amount Received (PKR)</label>
        <input class="form-control num" id="fp-amt" type="number" step="0.01" min="0.01" max="${esc(maxRupees)}" value="${esc(maxRupees)}" required />
        <div class="form-hint">Auto-allocates oldest due vouchers first across siblings</div>
      </div>
      <div class="form-group">
        <label class="form-label required" for="fp-mode">Payment Mode</label>
        <select class="form-control" id="fp-mode">
          <option value="cash">Cash Counter</option>
          <option value="bank">Bank Deposit Slip</option>
          <option value="online">Online / IBFT Transfer</option>
          <option value="cheque">Cheque / Pay Order</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label" for="fp-ref">Reference / Slip Number</label>
      <input class="form-control" id="fp-ref" placeholder="Optional bank or transaction reference" />
    </div>
  `, async () => {
    const res = await apiPost(`/api/families/${encodeURIComponent(fkey)}/pay`, {
      amount_rupees: document.getElementById('fp-amt')?.value?.trim(),
      payment_mode:  document.getElementById('fp-mode')?.value || 'cash',
      reference:     document.getElementById('fp-ref')?.value?.trim() || '',
    });
    closeModal();
    toast(`Combined receipt ${res.family_receipt.combined_receipt_no} issued across ${res.family_receipt.receipt_count} voucher(s)`, 'success');
    await onPaid?.();
    openFamilyReceiptPrint(res);
  }, { submitLabel: 'Collect & Print Family Receipt' });
}

export async function renderFamilySubTab(mountEl, onRefreshKpis) {
  const wasFocusedSearch = document.activeElement?.id === 'fam-q';
  const cursorPos = wasFocusedSearch ? (document.activeElement.selectionStart ?? null) : null;
  const incomingQ = get('feesQuery');
  if (incomingQ) {
    _famQuery = incomingQ;
    set({ feesQuery: '' });
  }

  const famRes = await apiGet('/api/families', {
    q: _famQuery,
    only_with_dues: _onlyWithDues ? '1' : '',
  });
  const families = famRes.items || [];
  if ((!_selectedFamilyKey || !families.some(f => f.family_key === _selectedFamilyKey)) && families.length) {
    _selectedFamilyKey = families[0].family_key;
  }

  let ledger = null;
  if (_selectedFamilyKey) {
    try {
      const fkey = _selectedFamilyKey;
      ledger = await apiGet(`/api/families/${encodeURIComponent(fkey)}/ledger`);
    } catch {
      ledger = null;
    }
  }

  const listHtml = families.map(f => `
    <button type="button" class="family-card-row ${f.family_key === _selectedFamilyKey ? 'active' : ''}" data-fkey="${esc(f.family_key)}">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
        <div style="font-weight:600; color:var(--siyahi); font-size:13.5px;">${esc(f.guardian_name)}</div>
        <span class="num" style="font-weight:700; font-size:13px; color:var(--siyahi);">${esc(formatPaisa(f.total_due_paisa))}</span>
      </div>
      <div style="font-size:12px; color:var(--siyahi-soft); margin-top:3px;" class="truncate">
        ${esc(f.children_count)} child${f.children_count > 1 ? 'ren' : ''}: ${esc(f.children_names)}
      </div>
      <div style="font-size:11.5px; color:var(--siyahi-soft); margin-top:2px;">
        ${esc(f.phone || 'No mobile')}${f.cnic ? ` • CNIC: ${esc(f.cnic)}` : ''}
      </div>
    </button>`).join('');

  const detailHtml = ledger ? `
    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">${esc(ledger.guardian.name)} <span class="badge badge-neutral">${esc(ledger.guardian.relation)}</span></div>
          <div class="panel-subtitle">
            Phone: <strong class="num">${esc(ledger.guardian.phone || '—')}</strong>
            ${ledger.guardian.cnic ? ` • CNIC: <strong class="num">${esc(ledger.guardian.cnic)}</strong>` : ''}
            • Total Family Due: <strong class="num">${esc(formatPaisa(ledger.summary.total_due_paisa))}</strong>
          </div>
        </div>
        <div class="panel-toolbar">
          ${ledger.open_vouchers.length ? `
            <button type="button" class="btn btn-secondary btn-sm" id="fam-print-all">${icon('printer', 14)} Print Open Vouchers</button>
            <button type="button" class="btn btn-primary btn-sm" id="fam-pay-btn">${icon('fees', 14)} Receive Family Payment</button>
          ` : `<span class="badge badge-success">All Sibling Dues Settled</span>`}
        </div>
      </div>

      <div class="panel-body" style="border-bottom:1px solid var(--rule-line); padding:10px 18px;">
        <span style="font-size:12px; color:var(--siyahi-soft); margin-right:8px;">Enrolled Siblings:</span>
        ${ledger.children.map(c => `
          <button type="button" class="btn btn-xs btn-secondary" data-fam-s360="${esc(c.id)}" style="margin-right:6px; margin-bottom:4px;">
            ${esc(c.student_name)} ${esc(c.last || '')} (${esc(c.class_name || c.pid)}) — <span class="num">${esc(formatPaisa(c.due_paisa))}</span>
          </button>`).join('')}
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Voucher #</th><th>Student</th><th>Month / Due</th><th class="num">Total</th><th class="num">Paid</th><th class="num">Balance</th><th>Status</th></tr></thead>
          <tbody>
            ${ledger.vouchers.slice(0, 15).map(v => `
              <tr>
                <td class="num" style="font-weight:600;">${esc(v.voucher_display)}</td>
                <td>${esc(v.student_name)} ${esc(v.last || '')}</td>
                <td class="num">${esc(v.billing_month || formatDate(v.due_date || v.date))}</td>
                <td class="num">${esc(formatPaisa(v.total_paisa))}</td>
                <td class="num">${esc(formatPaisa(v.paid_paisa))}</td>
                <td class="num" style="font-weight:600;">${esc(formatPaisa(v.due_paisa))}</td>
                <td><span class="badge ${stateBadgeClass(v.state)}">${esc(stateLabel(v.state))}</span></td>
              </tr>`).join('') || `<tr><td colspan="7" style="text-align:center; padding:22px;">No vouchers issued for this family yet.</td></tr>`}
          </tbody>
        </table>
      </div>

      ${ledger.payments.length ? `
        <div class="panel-header" style="border-top:1px solid var(--rule-line);"><div class="panel-title" style="font-size:13.5px;">Recent Family Receipts</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Receipt #</th><th>Student</th><th>Date</th><th>Mode</th><th class="num">Amount</th><th>Action</th></tr></thead>
            <tbody>
              ${ledger.payments.slice(0, 8).map(p => `
                <tr>
                  <td class="num">${esc(p.receipt_no)}</td>
                  <td>${esc(p.student_name)} ${esc(p.last || '')}</td>
                  <td class="num">${esc(formatDate(p.payment_date))}</td>
                  <td style="text-transform:uppercase; font-size:11.5px;">${esc(p.payment_mode)}</td>
                  <td class="num" style="font-weight:600;">${esc(formatPaisa(p.amount_paisa))}</td>
                  <td>${p.reversed_at ? `<span class="badge badge-danger">Reversed</span>` : `<button type="button" class="btn btn-xs btn-secondary" data-fam-rcp="${esc(p.id)}">${icon('printer', 12)} Slip</button>`}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>` : ''}
    </div>` : `
    <div class="empty-state">
      <div class="empty-state-icon">${icon('users', 38)}</div>
      <div class="empty-state-title">Select a family account</div>
      <div class="empty-state-desc">Search by guardian name, mobile, CNIC, or student GR number, or link siblings under a shared guardian.</div>
    </div>`;

  mountEl.innerHTML = `
    <div class="panel" style="margin-bottom:var(--sp-4);">
      <div class="fees-filter-bar" style="border-bottom:none;">
        <input type="search" class="form-control" id="fam-q" placeholder="Search guardian, CNIC, mobile, student or GR..." value="${esc(_famQuery)}" style="flex:1; min-width:220px;" />
        <label style="display:flex; align-items:center; gap:6px; font-size:13px;">
          <input type="checkbox" id="fam-dues-only" ${_onlyWithDues ? 'checked' : ''} />
          <span>Only families with unpaid dues</span>
        </label>
        <button type="button" class="btn btn-secondary btn-sm" id="fam-link-btn">${icon('plus', 14)} Link Guardian &amp; Siblings</button>
      </div>
    </div>

    <div class="family-split-grid">
      <div class="panel family-list-scroll">
        ${listHtml || `<div style="padding:24px; text-align:center; color:var(--siyahi-soft); font-size:13px;">No matching families found.</div>`}
      </div>
      <div>${detailHtml}</div>
    </div>`;

  const reload = async () => {
    await renderFamilySubTab(mountEl, onRefreshKpis);
    onRefreshKpis?.();
  };

  let t = null;
  const famQEl = document.getElementById('fam-q');
  if (wasFocusedSearch && famQEl) {
    famQEl.focus();
    const pos = cursorPos ?? famQEl.value.length;
    famQEl.setSelectionRange(pos, pos);
  }
  famQEl?.addEventListener('input', e => {
    clearTimeout(t);
    t = setTimeout(() => { _famQuery = e.target.value.trim(); reload(); }, 220);
  });
  document.getElementById('fam-dues-only')?.addEventListener('change', e => { _onlyWithDues = e.target.checked; reload(); });
  document.getElementById('fam-link-btn')?.addEventListener('click', () => _openLinkGuardianModal(reload));

  mountEl.querySelectorAll('[data-fkey]').forEach(b => {
    b.onclick = () => { _selectedFamilyKey = b.getAttribute('data-fkey'); reload(); };
  });
  mountEl.querySelectorAll('[data-fam-s360]').forEach(b => {
    b.onclick = () => navigateTo('student360', { selectedStudentId: parseInt(b.getAttribute('data-fam-s360'), 10) });
  });
  mountEl.querySelectorAll('[data-fam-rcp]').forEach(b => {
    b.onclick = () => openSingleReceiptPrint(parseInt(b.getAttribute('data-fam-rcp'), 10));
  });
  document.getElementById('fam-pay-btn')?.addEventListener('click', () => {
    if (ledger) _openFamilyPaymentModal(ledger, reload);
  });
  document.getElementById('fam-print-all')?.addEventListener('click', () => {
    if (ledger?.open_vouchers?.length) {
      openVoucherPrintPreview({ payslipIds: ledger.open_vouchers.map(v => v.id) });
    }
  });
}


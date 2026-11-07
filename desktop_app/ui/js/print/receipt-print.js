/**
 * print/receipt-print.js — Official A4 Slip & 80mm Thermal Fee Receipt Renderer
 *
 * Supports both individual payment receipts (/api/fees/print/receipt/{id})
 * and consolidated multi-sibling Family Receipts in A4 or 80mm POS format.
 */

import { apiGet } from '../core/api.js';
import { get } from '../core/state.js';
import { esc, openModal, closeModal, toast } from '../core/dom.js';
import { formatPaisa, formatDate, formatDateTime, stateLabel } from '../core/format.js';
import { triggerIsolatedPrint } from './voucher-print.js';

function _buildSingleReceiptA4(data) {
  const sch = data.school || {};
  const r   = data.receipt || {};
  const v   = data.voucher || {};
  const stu = [v.student_name, v.middle, v.last].filter(Boolean).join(' ');

  return `
    <div class="receipt-a4">
      <div style="display:flex; justify-content:space-between; border-bottom:2px solid #18181B; padding-bottom:10px; margin-bottom:14px;">
        <div>
          <div style="font-size:18px; font-weight:700;">${esc(sch.name || 'School ERP')}</div>
          <div style="font-size:12px; color:#52525B;">${esc(sch.city || '')}${sch.phone ? ` • Tel: ${esc(sch.phone)}` : ''}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:11px; text-transform:uppercase; font-weight:700; letter-spacing:0.05em;">Official Fee Receipt</div>
          <div class="num" style="font-size:15px; font-weight:700;">${esc(r.receipt_no)}</div>
          ${r.reversed_at ? `<div style="font-size:11px; font-weight:700;">[REVERSED RECEIPT]</div>` : ''}
        </div>
      </div>

      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 18px; margin-bottom:14px; font-size:12.5px;">
        <div><span style="color:#52525B;">Student Name:</span> <strong>${esc(stu)}</strong></div>
        <div><span style="color:#52525B;">Payment Date:</span> <strong class="num">${esc(formatDate(r.payment_date))}</strong></div>
        <div><span style="color:#52525B;">GR No / Class:</span> <strong>${esc(v.pid || '—')} • ${esc(v.class_name || '—')}</strong></div>
        <div><span style="color:#52525B;">Payment Mode:</span> <strong style="text-transform:uppercase;">${esc(r.payment_mode || 'cash')}${r.reference ? ` (${esc(r.reference)})` : ''}</strong></div>
        <div><span style="color:#52525B;">Voucher Ref:</span> <strong class="num">${esc(v.voucher_display || v.number || '—')}</strong></div>
        <div><span style="color:#52525B;">Voucher Status:</span> <strong>${esc(stateLabel(v.state))}</strong></div>
      </div>

      <table class="vch-lines-table" style="font-size:12.5px; margin-bottom:14px;">
        <thead>
          <tr><th>Description</th><th style="text-align:right;">Amount</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>Payment received against ${esc(v.name || 'Fee Voucher')} (${esc(v.voucher_display || '')})</td>
            <td class="num" style="text-align:right; font-weight:700;">${esc(formatPaisa(r.amount_paisa))}</td>
          </tr>
        </tbody>
      </table>

      <div style="display:grid; grid-template-columns:1fr 240px; gap:16px; align-items:end; border-top:1.5px solid #18181B; padding-top:10px;">
        <div style="font-size:11.5px; color:#52525B;">
          Received by: <strong>${esc(r.received_by || 'Cashier')}</strong> • Printed: ${esc(formatDateTime(new Date().toISOString()))}
          ${r.note ? `<div>Note: ${esc(r.note)}</div>` : ''}
        </div>
        <div>
          <div class="vch-total-row"><span>Voucher Total:</span><span>${esc(formatPaisa(v.total_paisa))}</span></div>
          <div class="vch-total-row strong"><span>Amount Received:</span><span>${esc(formatPaisa(r.amount_paisa))}</span></div>
          <div class="vch-total-row"><span>Balance Remaining:</span><span>${esc(formatPaisa(v.due_paisa))}</span></div>
        </div>
      </div>
    </div>`;
}

function _buildSingleReceiptThermal(data) {
  const sch = data.school || {};
  const r   = data.receipt || {};
  const v   = data.voucher || {};
  const stu = [v.student_name, v.last].filter(Boolean).join(' ');

  return `
    <div class="receipt-thermal">
      <div style="text-align:center; font-weight:700; font-size:12.5px;">${esc(sch.name || 'SCHOOL ERP')}</div>
      <div style="text-align:center; font-size:10px;">FEE PAYMENT RECEIPT</div>
      <hr class="thermal-hr"/>
      <div class="thermal-row"><span>Receipt:</span><strong>${esc(r.receipt_no)}</strong></div>
      <div class="thermal-row"><span>Date:</span><span>${esc(r.payment_date)}</span></div>
      <div class="thermal-row"><span>Student:</span><span>${esc(stu)}</span></div>
      <div class="thermal-row"><span>GR / Class:</span><span>${esc(v.pid || '')} ${esc(v.class_name || '')}</span></div>
      <div class="thermal-row"><span>Voucher:</span><span>${esc(v.voucher_display || '')}</span></div>
      <div class="thermal-row"><span>Mode:</span><span>${esc((r.payment_mode || 'cash').toUpperCase())}</span></div>
      <hr class="thermal-hr"/>
      <div class="thermal-row" style="font-weight:700; font-size:12px;">
        <span>PAID:</span><span>${esc(formatPaisa(r.amount_paisa))}</span>
      </div>
      <div class="thermal-row"><span>Voucher Total:</span><span>${esc(formatPaisa(v.total_paisa))}</span></div>
      <div class="thermal-row"><span>Balance Due:</span><span>${esc(formatPaisa(v.due_paisa))}</span></div>
      <hr class="thermal-hr"/>
      <div style="text-align:center; font-size:9.5px;">Cashier: ${esc(r.received_by || 'Staff')}</div>
      <div style="text-align:center; font-size:9.5px;">Thank you — Computer Generated Slip</div>
    </div>`;
}

function _buildFamilyReceiptHtml(famReceipt, mode) {
  const sch = get('currentSchool') || famReceipt.school || {};
  const schName = sch.name || get('schoolName') || 'School ERP';
  const rows = famReceipt.student_receipts || [];
  if (mode === 'thermal') {
    return `
      <div class="receipt-thermal">
        <div style="text-align:center; font-weight:700; font-size:12.5px;">${esc(schName)}</div>
        <div style="text-align:center; font-size:10px;">COMBINED FAMILY RECEIPT</div>
        <hr class="thermal-hr"/>
        <div class="thermal-row"><span>Ref:</span><strong>${esc(famReceipt.combined_receipt_no)}</strong></div>
        <div class="thermal-row"><span>Date:</span><span>${esc(famReceipt.payment_date)}</span></div>
        <div class="thermal-row"><span>Guardian:</span><span>${esc(famReceipt.guardian?.name || 'Guardian')}</span></div>
        <div class="thermal-row"><span>Mode:</span><span>${esc((famReceipt.payment_mode || 'cash').toUpperCase())}</span></div>
        <hr class="thermal-hr"/>
        ${rows.map(it => `
          <div>${esc(it.student_name)} (${esc(it.pid || '')})</div>
          <div class="thermal-row"><span>  ${esc(it.receipt_no)}</span><span>${esc(formatPaisa(it.allocated_paisa))}</span></div>
        `).join('')}
        <hr class="thermal-hr"/>
        <div class="thermal-row" style="font-weight:700; font-size:12px;">
          <span>TOTAL PAID:</span><span>${esc(formatPaisa(famReceipt.total_paid_paisa))}</span>
        </div>
        <div class="thermal-row"><span>Family Balance:</span><span>${esc(formatPaisa(famReceipt.remaining_family_due_paisa || 0))}</span></div>
      </div>`;
  }

  return `
    <div class="receipt-a4">
      <div style="display:flex; justify-content:space-between; border-bottom:2px solid #18181B; padding-bottom:10px; margin-bottom:14px;">
        <div>
          <div style="font-size:18px; font-weight:700;">${esc(schName)}</div>
          <div style="font-size:12px; color:#52525B;">Consolidated Family Fee Receipt</div>
        </div>
        <div style="text-align:right;">
          <div class="num" style="font-size:15px; font-weight:700;">${esc(famReceipt.combined_receipt_no)}</div>
          <div class="num" style="font-size:12px;">Date: ${esc(formatDate(famReceipt.payment_date))}</div>
        </div>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px 16px; margin-bottom:12px; font-size:12.5px;">
        <div><span style="color:#52525B;">Guardian:</span> <strong>${esc(famReceipt.guardian?.name || 'Guardian')}</strong></div>
        <div><span style="color:#52525B;">Phone / CNIC:</span> <strong class="num">${esc(famReceipt.guardian?.phone || '—')} ${famReceipt.guardian?.cnic ? `• ${esc(famReceipt.guardian.cnic)}` : ''}</strong></div>
        <div><span style="color:#52525B;">Payment Mode:</span> <strong style="text-transform:uppercase;">${esc(famReceipt.payment_mode || 'cash')}</strong></div>
        <div><span style="color:#52525B;">Received By:</span> <strong>${esc(famReceipt.received_by || 'Cashier')}</strong></div>
      </div>
      <table class="vch-lines-table" style="font-size:12.5px; margin-bottom:14px;">
        <thead><tr><th>Receipt #</th><th>Student</th><th>Voucher #</th><th style="text-align:right;">Allocated</th><th style="text-align:right;">Remaining</th></tr></thead>
        <tbody>
          ${rows.map(it => `
            <tr>
              <td class="num">${esc(it.receipt_no)}</td>
              <td><strong>${esc(it.student_name)}</strong> (${esc(it.pid || '')})</td>
              <td class="num">${esc(it.voucher_no)}</td>
              <td class="num" style="text-align:right; font-weight:600;">${esc(formatPaisa(it.allocated_paisa))}</td>
              <td class="num" style="text-align:right;">${esc(formatPaisa(it.remaining_due_paisa))}</td>
            </tr>`).join('')}
        </tbody>
      </table>
      <div style="display:flex; justify-content:flex-end;">
        <div style="width:260px;">
          <div class="vch-total-row strong"><span>Total Family Receipt:</span><span>${esc(formatPaisa(famReceipt.total_paid_paisa))}</span></div>
          <div class="vch-total-row"><span>Remaining Family Due:</span><span>${esc(formatPaisa(famReceipt.remaining_family_due_paisa || 0))}</span></div>
        </div>
      </div>
    </div>`;
}

function _openFormatSwitchablePreview(title, renderFn) {
  let fmt = get('preferences')?.thermal_receipt_default ? 'thermal' : 'a4';
  const renderModalBody = () => `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
      <span style="font-size:12.5px; color:var(--siyahi-soft);">Choose paper size before printing:</span>
      <div style="display:flex; gap:6px;">
        <button type="button" class="btn btn-xs ${fmt === 'a4' ? 'btn-primary' : 'btn-secondary'}" data-rcp-fmt="a4">A4 Official Slip</button>
        <button type="button" class="btn btn-xs ${fmt === 'thermal' ? 'btn-primary' : 'btn-secondary'}" data-rcp-fmt="thermal">80mm Thermal Roll</button>
      </div>
    </div>
    <div class="print-preview-stage" id="rcp-preview-stage">${renderFn(fmt)}</div>
  `;

  const bindSwitch = () => {
    document.querySelectorAll('[data-rcp-fmt]').forEach(b => {
      b.onclick = () => {
        fmt = b.getAttribute('data-rcp-fmt');
        const body = document.getElementById('modal-body');
        if (body) { body.innerHTML = renderModalBody(); bindSwitch(); }
      };
    });
  };

  openModal(title, renderModalBody(), async () => {
    const html = renderFn(fmt);
    closeModal();
    triggerIsolatedPrint(html);
  }, { submitLabel: 'Print Receipt', wide: true });
  setTimeout(bindSwitch, 20);
}

export async function openSingleReceiptPrint(paymentId) {
  try {
    const data = await apiGet(`/api/fees/print/receipt/${paymentId}`);
    _openFormatSwitchablePreview(
      `Fee Receipt — ${data.receipt?.receipt_no || paymentId}`,
      fmt => (fmt === 'thermal' ? _buildSingleReceiptThermal(data) : _buildSingleReceiptA4(data))
    );
  } catch (err) {
    toast(err.message, 'error');
  }
}

export function openFamilyReceiptPrint(familyPaymentResult) {
  const fr = familyPaymentResult?.family_receipt || familyPaymentResult;
  const rem = familyPaymentResult?.ledger?.summary?.total_due_paisa ?? fr?.remaining_family_due_paisa ?? 0;
  const enriched = { ...fr, remaining_family_due_paisa: rem };
  _openFormatSwitchablePreview(
    `Combined Family Receipt — ${enriched.combined_receipt_no || ''}`,
    fmt => _buildFamilyReceiptHtml(enriched, fmt)
  );
}

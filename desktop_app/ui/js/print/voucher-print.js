/**
 * print/voucher-print.js — 3-Part Bank Fee Voucher Renderer & Print Controller (S1)
 *
 * Produces Pakistani standard 3-copy horizontal bank vouchers (`Bank Copy`,
 * `School Copy`, `Parent Copy`) with itemized lines, due/after-due totals,
 * and a deterministic offline SVG verification barcode. Pure English UI.
 */

import { apiGet } from '../core/api.js';
import { esc, openModal, closeModal, toast } from '../core/dom.js';
import { formatPaisa, formatPKR, formatDate } from '../core/format.js';
import { icon } from '../core/icons.js';

/**
 * Deterministic inline SVG code-bar pattern for offline bank-slip verification.
 * @param {string} code
 * @returns {string}
 */
export function renderVerificationBarsSvg(code) {
  const str = String(code || 'VCH0000');
  const bars = [];
  let x = 2;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    const w1 = (ch % 3) + 1;
    const g1 = ((ch >> 2) % 2) + 1;
    const w2 = ((ch >> 4) % 2) + 1;
    bars.push(`<rect x="${x}" y="2" width="${w1}" height="20" fill="#18181B"/>`);
    x += w1 + g1;
    bars.push(`<rect x="${x}" y="2" width="${w2}" height="20" fill="#18181B"/>`);
    x += w2 + 2;
  }
  return `<svg width="${Math.min(x + 2, 130)}" height="24" viewBox="0 0 ${x + 2} 24" aria-hidden="true">${bars.join('')}</svg>`;
}

function _renderSingleCopyHtml(v, copyTitle, school, prefs) {
  const bankLine = prefs?.bank_name
    ? `${esc(prefs.bank_name)}${prefs.bank_account_no ? ` • A/C: ${esc(prefs.bank_account_no)}` : ''}`
    : 'Payable at School Fee Counter / Designated Bank Branch';

  const linesHtml = (v.lines || []).map(ln => `
    <tr>
      <td>${esc(ln.name)}</td>
      <td class="num" style="text-align:right;">${esc(formatPKR(ln.amount))}</td>
    </tr>
  `).join('');

  const fullStudent = [v.student_name, v.middle, v.last].filter(Boolean).join(' ');

  return `
    <div class="voucher-copy">
      <div>
        <div class="vch-head">
          <div>
            <div class="vch-school-title">${esc(school?.name || 'School ERP')}</div>
            <div style="font-size:9.5px; color:#52525B;">${esc(school?.city || '')}${school?.phone ? ` • Tel: ${esc(school.phone)}` : ''}</div>
          </div>
          <span class="vch-copy-tag">${esc(copyTitle)}</span>
        </div>

        <div class="vch-bank-box">
          <strong>Deposit Channel:</strong> ${bankLine}
        </div>

        <div class="vch-meta-grid">
          <div><span style="color:#52525B;">Voucher #:</span> <strong class="num">${esc(v.voucher_display)}</strong></div>
          <div><span style="color:#52525B;">Billing Month:</span> <strong>${esc(v.billing_month || formatDate(v.date))}</strong></div>
          <div><span style="color:#52525B;">Student:</span> <strong>${esc(fullStudent)}</strong></div>
          <div><span style="color:#52525B;">GR / Roll:</span> <strong class="num">${esc(v.pid || '—')}${v.roll_no ? ` / #${esc(v.roll_no)}` : ''}</strong></div>
          <div><span style="color:#52525B;">Class:</span> <strong>${esc(v.class_name || '—')}</strong></div>
          <div><span style="color:#52525B;">Due Date:</span> <strong class="num">${esc(formatDate(v.due_date || v.date))}</strong></div>
        </div>

        <table class="vch-lines-table">
          <thead>
            <tr><th>Fee Particular</th><th style="text-align:right;">Amount</th></tr>
          </thead>
          <tbody>
            ${linesHtml || `<tr><td>Tuition &amp; Monthly Charges</td><td class="num" style="text-align:right;">${esc(formatPaisa(v.total_paisa))}</td></tr>`}
          </tbody>
        </table>
      </div>

      <div>
        <div class="vch-totals-box">
          <div class="vch-total-row">
            <span>Voucher Total:</span>
            <span>${esc(formatPaisa(v.total_paisa))}</span>
          </div>
          ${v.paid_paisa > 0 ? `
          <div class="vch-total-row">
            <span>Less Already Paid:</span>
            <span>- ${esc(formatPaisa(v.paid_paisa))}</span>
          </div>` : ''}
          <div class="vch-total-row strong">
            <span>Payable Within Due Date:</span>
            <span>${esc(formatPaisa(v.due_paisa))}</span>
          </div>
          <div class="vch-total-row">
            <span>Payable After Due Date:</span>
            <span>${esc(formatPaisa(v.after_due_paisa ?? v.due_paisa))}</span>
          </div>
        </div>

        <div class="vch-footer-bar">
          <div>
            ${renderVerificationBarsSvg(v.verification_code || v.voucher_display)}
            <div class="num" style="font-size:8.5px;">Ref: ${esc(v.verification_code || v.voucher_display)}</div>
          </div>
          <div style="text-align:right;">
            <div style="border-top:1px solid #52525B; padding-top:2px; min-width:95px;">Cashier Stamp &amp; Sign</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

export function buildThreePartVouchersHtml(bundle) {
  const school   = bundle.school || {};
  const prefs    = bundle.preferences || {};
  const vouchers = bundle.vouchers || [];

  return vouchers.map(v => {
    const copies = v.copies || ['Bank Copy', 'School Copy', 'Parent Copy'];
    return `
      <section class="voucher-sheet-3up">
        ${copies.map(cp => _renderSingleCopyHtml(v, cp, school, prefs)).join('')}
      </section>
    `;
  }).join('');
}

export function triggerIsolatedPrint(htmlMarkup) {
  const mount = document.getElementById('print-mount');
  if (!mount) {
    window.print();
    return;
  }
  mount.innerHTML = htmlMarkup;
  document.body.classList.add('print-mode-active');

  const cleanup = () => {
    document.body.classList.remove('print-mode-active');
    window.removeEventListener('afterprint', cleanup);
  };
  window.addEventListener('afterprint', cleanup);
  setTimeout(() => {
    window.print();
    setTimeout(cleanup, 800);
  }, 60);
}

export async function openVoucherPrintPreview({ payslipIds = null, billingMonth = '', classId = '' } = {}) {
  try {
    const params = {};
    if (payslipIds && payslipIds.length) params.ids = payslipIds.join(',');
    if (billingMonth) params.billing_month = billingMonth;
    if (classId) params.class_id = classId;

    const bundle = await apiGet('/api/fees/print/vouchers', params);
    if (!bundle.vouchers || !bundle.vouchers.length) {
      toast('No fee vouchers matched the print selection.', 'warn');
      return;
    }

    const sheetsHtml = buildThreePartVouchersHtml(bundle);
    openModal(
      `3-Part Bank Fee Vouchers (${bundle.vouchers.length} Sheet${bundle.vouchers.length > 1 ? 's' : ''})`,
      `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; font-size:12.5px; color:var(--siyahi-soft);">
          <span>${icon('printer', 14)} Recommended paper: <strong>A4 Landscape</strong> (3 copies per sheet with dashed cut lines)</span>
          <span class="badge badge-info">${bundle.vouchers.length} Voucher(s)</span>
        </div>
        <div class="print-preview-stage">${sheetsHtml}</div>
      `,
      async () => {
        closeModal();
        triggerIsolatedPrint(sheetsHtml);
      },
      { submitLabel: 'Print Vouchers', wide: true }
    );
  } catch (err) {
    toast(err.message, 'error');
  }
}


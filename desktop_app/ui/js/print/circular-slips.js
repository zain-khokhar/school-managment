/**
 * print/circular-slips.js — 4-slips-per-A4 Print Fallback Generator (Phase 5)
 */

import { apiGet } from '../core/api.js';
import { esc } from '../core/dom.js';
import { getBootstrap } from '../core/state.js';

export async function openCircularSlipsPreview() {
  const data = getBootstrap();
  const schoolName = data?.preferences?.school_name || 'School ERP Offline';

  let messages = [];
  try {
    const res = await apiGet('/api/outbox/messages?category=circular&status=ready&per_page=50');
    messages = res?.items || [];
  } catch (err) {
    alert('Failed to load circular slips: ' + err.message);
    return;
  }

  if (messages.length === 0) {
    alert('No ready circular notices in outbox to print.');
    return;
  }

  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    alert('Please allow popups to print slips.');
    return;
  }

  const slipsHtml = messages.map(m => `
    <div class="circular-slip">
      <div class="slip-header">
        <div class="slip-school">${esc(schoolName)}</div>
        <div class="slip-title">Official Circular Notice</div>
      </div>
      <div class="slip-meta">
        <div><strong>Student:</strong> ${esc(m.to_name)} (${esc(m.class_name || 'Class')})</div>
        <div><strong>Date:</strong> ${esc(m.dedupe_date || m.created_at?.slice(0, 10))}</div>
      </div>
      <div class="slip-body">
        ${esc(m.body_text)}
      </div>
      <div class="slip-footer">
        <div>Received by: ____________________</div>
        <div>Principal Stamp: ____________________</div>
      </div>
    </div>
  `).join('');

  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Circular Notice Slips — Print</title>
      <style>
        @page { size: A4 portrait; margin: 10mm; }
        body { font-family: "Segoe UI", Tahoma, sans-serif; margin: 0; padding: 0; color: #111; }
        .slips-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          grid-gap: 15mm;
        }
        .circular-slip {
          border: 1px dashed #666;
          padding: 12px;
          border-radius: 4px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          height: 125mm;
          box-sizing: border-box;
        }
        .slip-header { border-bottom: 1px solid #333; padding-bottom: 6px; margin-bottom: 8px; text-align: center; }
        .slip-school { font-size: 14px; font-weight: bold; text-transform: uppercase; }
        .slip-title { font-size: 11px; color: #555; }
        .slip-meta { font-size: 11px; display: flex; justify-content: space-between; margin-bottom: 8px; }
        .slip-body { font-size: 12px; line-height: 1.5; flex-grow: 1; border: 1px solid #eee; padding: 8px; background: #fafafa; }
        .slip-footer { font-size: 10px; display: flex; justify-content: space-between; margin-top: 10px; border-top: 1px dotted #ccc; padding-top: 6px; }
        @media print {
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="no-print" style="padding:10px; background:#f0f0f0; margin-bottom:10px;">
        <button onclick="window.print()" style="padding:6px 16px; font-weight:bold; cursor:pointer;">Print All Slips</button>
      </div>
      <div class="slips-grid">
        ${slipsHtml}
      </div>
    </body>
    </html>
  `);
  printWindow.document.close();
}


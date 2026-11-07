/**
 * print/academic-print.js — Report Cards (S5), PTM 1-Pager (S7) & Student ID Cards (G11)
 *
 * Uses `#print-mount` via `triggerIsolatedPrint()` from `voucher-print.js`.
 * Pure English UI & print labels; zero Unicode emojis.
 */

import { apiGet } from '../core/api.js';
import { esc, openModal, closeModal, toast } from '../core/dom.js';
import { formatPKR, formatDate } from '../core/format.js';
import { icon } from '../core/icons.js';
import { triggerIsolatedPrint, renderVerificationBarsSvg } from './voucher-print.js';

export function buildReportCardsHtml(bundle) {
  const school = bundle.school || {};
  const cards  = bundle.report_cards || [];

  return cards.map(rc => {
    const fullStudent = [rc.student_name, rc.middle, rc.last].filter(Boolean).join(' ');
    const subjectsHtml = (rc.subjects || []).map(sub => {
      const isAbs = Boolean(sub.is_absent);
      const obt   = isAbs ? 'ABS' : Number(sub.obtain_marks || 0).toFixed(1).replace(/\.0$/, '');
      const maxM  = Number(sub.maximum_marks || 100);
      const minM  = Number(sub.minimum_marks || 35);
      const pass  = !isAbs && Number(sub.obtain_marks || 0) >= minM;
      return `
        <tr>
          <td style="font-weight:500;">${esc(sub.subject_name)} (${esc(sub.subject_code)})</td>
          <td class="num" style="text-align:right;">${esc(maxM)}</td>
          <td class="num" style="text-align:right;">${esc(minM)}</td>
          <td class="num" style="text-align:right; font-weight:600;">${esc(obt)}</td>
          <td style="text-align:center;">${esc(sub.subject_grade || '—')}</td>
          <td style="text-align:center; font-weight:600;">${isAbs ? 'Absent' : (pass ? 'Pass' : 'Fail')}</td>
        </tr>`;
    }).join('');

    return `
      <section class="report-card-sheet">
        <div class="rc-header">
          <div>
            <div class="rc-school-name">${esc(school.name || 'School ERP')}</div>
            <div style="font-size:11px; color:#52525B;">${esc(school.city || '')}${school.phone ? ` • Tel: ${esc(school.phone)}` : ''}</div>
          </div>
          <div style="text-align:right;">
            <div class="rc-doc-tag">OFFICIAL REPORT CARD</div>
            <div style="font-size:11px; margin-top:3px;"><strong>${esc(rc.exam_name)}</strong> (${esc(rc.year_name || '')})</div>
          </div>
        </div>

        <div class="rc-meta-grid">
          <div><span>Student Name:</span> <strong>${esc(fullStudent)}</strong></div>
          <div><span>GR / Admission No:</span> <strong class="num">${esc(rc.pid || '—')}</strong></div>
          <div><span>Class &amp; Roll No:</span> <strong>${esc(rc.class_name || '—')} (Roll #${esc(rc.roll_no || '—')})</strong></div>
          <div><span>Term Attendance:</span> <strong class="num">${esc(rc.attendance_pct ?? 100)}% (${esc(rc.attendance_detail || 'Full')})</strong></div>
        </div>

        <table class="rc-table">
          <thead>
            <tr>
              <th>Subject</th>
              <th style="text-align:right;">Max Marks</th>
              <th style="text-align:right;">Passing</th>
              <th style="text-align:right;">Obtained</th>
              <th style="text-align:center;">Grade</th>
              <th style="text-align:center;">Status</th>
            </tr>
          </thead>
          <tbody>${subjectsHtml}</tbody>
          <tfoot>
            <tr>
              <th>Aggregate Total</th>
              <th class="num" style="text-align:right;">${esc(rc.max_total || 0)}</th>
              <th></th>
              <th class="num" style="text-align:right;">${esc(rc.total || 0)}</th>
              <th style="text-align:center;">${esc(rc.grade || '—')}</th>
              <th style="text-align:center;">${esc(rc.result || 'Pass')}</th>
            </tr>
          </tfoot>
        </table>

        <div class="rc-summary-strip">
          <div><span>Percentage:</span> <strong class="num">${esc(rc.percentage || 0)}%</strong></div>
          <div><span>Overall Grade:</span> <strong>${esc(rc.grade || '—')}</strong></div>
          <div><span>Class Position / Rank:</span> <strong class="num">${rc.rank ? `#${esc(rc.rank)}` : '—'}</strong></div>
          <div><span>Final Outcome:</span> <strong>${esc(rc.result || 'Pass')}</strong></div>
        </div>

        <div class="rc-remarks-box">
          <strong>Class Teacher Remarks:</strong> ${esc(rc.remarks || 'Consistent effort demonstrated across subjects. Keep up regular study habits.')}
        </div>

        <div class="rc-signatures">
          <div>Class Teacher Signature</div>
          <div>Examination Controller</div>
          <div>Principal Stamp &amp; Signature</div>
        </div>
      </section>`;
  }).join('');
}

export async function openReportCardsPrintPreview({ examId, classId = '', studentId = '' }) {
  try {
    const params = { exam_id: examId };
    if (classId) params.class_id = classId;
    if (studentId) params.student_id = studentId;
    const bundle = await apiGet('/api/exams/print/report-cards', params);
    if (!bundle.report_cards?.length) {
      toast('No marksheets found for the selected exam criteria.', 'warn');
      return;
    }
    const html = buildReportCardsHtml(bundle);
    openModal(
      `Official Report Cards (${bundle.report_cards.length} Student${bundle.report_cards.length > 1 ? 's' : ''})`,
      `<div style="margin-bottom:10px; font-size:12.5px; color:var(--siyahi-soft);">
        ${icon('printer', 14)} A4 Portrait Report Card with Olympic Tie-Aware Class Rank &amp; Attendance Summary
      </div>
      <div class="print-preview-stage">${html}</div>`,
      async () => {
        closeModal();
        triggerIsolatedPrint(html);
      },
      { submitLabel: 'Print Report Cards', wide: true }
    );
  } catch (err) {
    toast(err.message, 'error');
  }
}

export function buildPtmSheetsHtml(bundle) {
  const school = bundle.school || {};
  return (bundle.sheets || []).map(item => {
    const s = item.student || {};
    const ex = item.latest_exam;
    const fullStudent = [s.student_name, s.middle, s.last].filter(Boolean).join(' ');
    return `
      <section class="ptm-sheet-card">
        <div class="rc-header">
          <div>
            <div class="rc-school-name">${esc(school.name || 'School ERP')} — PTM 1-PagerSummary</div>
            <div style="font-size:11px; color:#52525B;">Parent-Teacher Meeting Progress &amp; Account Snapshot</div>
          </div>
          <span class="rc-doc-tag">PTM SUMMARY SHEET</span>
        </div>

        <div class="rc-meta-grid">
          <div><span>Student:</span> <strong>${esc(fullStudent)}</strong></div>
          <div><span>GR No / Class:</span> <strong class="num">${esc(s.pid)} • ${esc(s.class_name || '—')} (Roll #${esc(s.roll_no || '—')})</strong></div>
          <div><span>Attendance Rate:</span> <strong class="num">${esc(item.attendance_pct)}% (${esc(item.attendance_detail)})</strong></div>
          <div><span>Fee Balance Due:</span> <strong class="num">${esc(formatPKR(item.fee_due || 0))}</strong></div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:10px 0; font-size:11.5px;">
          <div style="border:1px solid #D4D4D8; padding:8px 10px;">
            <div style="font-weight:700; margin-bottom:4px;">Latest Examination Standing</div>
            ${ex
              ? `<div>Exam: <strong>${esc(ex.exam_name)}</strong></div>
                 <div>Score: <strong class="num">${esc(ex.percentage)}% (${esc(ex.grade || ex.result)})</strong> • Rank: <strong class="num">${ex.rank ? `#${esc(ex.rank)}` : '—'}</strong></div>
                 <div>Focus Area: <strong>${esc(item.weak_subject)}</strong></div>`
              : `<div>No examination marksheets recorded yet.</div>`}
          </div>
          <div style="border:1px solid #D4D4D8; padding:8px 10px;">
            <div style="font-weight:700; margin-bottom:4px;">Teacher Discussion Note</div>
            <div>${esc(item.teacher_remark)}</div>
          </div>
        </div>

        <div class="rc-signatures" style="margin-top:14px;">
          <div>Class Teacher Signature</div>
          <div>Parent / Guardian Signature</div>
        </div>
      </section>`;
  }).join('');
}

export async function openPtmSheetPrintPreview({ studentIds = null, classId = '' } = {}) {
  try {
    const params = {};
    if (studentIds?.length) params.ids = studentIds.join(',');
    if (classId) params.class_id = classId;
    const bundle = await apiGet('/api/students/print/ptm-sheets', params);
    if (!bundle.sheets?.length) {
      toast('No student records found for PTM sheet print.', 'warn');
      return;
    }
    const html = buildPtmSheetsHtml(bundle);
    openModal(
      `PTM 1-Pager Summary (${bundle.sheets.length} Sheet${bundle.sheets.length > 1 ? 's' : ''})`,
      `<div class="print-preview-stage">${html}</div>`,
      async () => {
        closeModal();
        triggerIsolatedPrint(html);
      },
      { submitLabel: 'Print PTM Sheets', wide: true }
    );
  } catch (err) {
    toast(err.message, 'error');
  }
}

export function buildIdCardsHtml(bundle) {
  const school = bundle.school || {};
  const cardsHtml = (bundle.cards || []).map(c => {
    const fullStudent = [c.student_name, c.middle, c.last].filter(Boolean).join(' ');
    const initials = (c.student_name || 'S').slice(0, 1).toUpperCase();
    return `
      <div class="id-card-badge">
        <div class="id-card-top">
          <div style="font-weight:700; font-size:12px;">${esc(school.name || 'School ERP')}</div>
          <div style="font-size:9.5px; opacity:0.85;">STUDENT IDENTITY CARD • ${esc(c.year_name || '')}</div>
        </div>
        <div class="id-card-body">
          <div class="id-card-avatar">${esc(initials)}</div>
          <div style="flex:1; min-width:0;">
            <div style="font-weight:700; font-size:13px;">${esc(fullStudent)}</div>
            <div class="num" style="font-size:11px; color:#52525B;">GR: <strong>${esc(c.pid)}</strong> • Roll #${esc(c.roll_no || '—')}</div>
            <div style="font-size:11px; margin-top:3px;">Class: <strong>${esc(c.class_name || '—')}</strong></div>
            <div class="num" style="font-size:10.5px;">DOB: ${esc(formatDate(c.date_of_birth))} • Blood: ${esc(c.blood_group || 'O+')}</div>
            <div class="num" style="font-size:10.5px;">Emergency: ${esc(c.contact_mobile || school.phone || '—')}</div>
          </div>
        </div>
        <div class="id-card-foot">
          <div>${renderVerificationBarsSvg(c.pid)}</div>
          <div style="font-size:9px; text-align:right;">Principal Sign</div>
        </div>
      </div>`;
  }).join('');
  return `<div class="id-cards-grid">${cardsHtml}</div>`;
}

export async function openIdCardsPrintPreview({ studentIds = null, classId = '' } = {}) {
  try {
    const params = {};
    if (studentIds?.length) params.ids = studentIds.join(',');
    if (classId) params.class_id = classId;
    const bundle = await apiGet('/api/students/print/id-cards', params);
    if (!bundle.cards?.length) {
      toast('No students matched for ID card printing.', 'warn');
      return;
    }
    const html = buildIdCardsHtml(bundle);
    openModal(
      `Student Identity Cards (${bundle.cards.length})`,
      `<div class="print-preview-stage">${html}</div>`,
      async () => {
        closeModal();
        triggerIsolatedPrint(html);
      },
      { submitLabel: 'Print ID Cards', wide: true }
    );
  } catch (err) {
    toast(err.message, 'error');
  }
}

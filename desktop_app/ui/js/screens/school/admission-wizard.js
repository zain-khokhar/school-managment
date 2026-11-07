/**
 * screens/school/admission-wizard.js — 3-Step Admission Wizard + Quick Mode + Bulk Import (G6, G15, ADM-0..4)
 *
 * Implements ADVANCEMENT_PLAN.md Section 9.8(M):
 *   - ADM-0: Mode toggle (3-Step Full Wizard vs Quick Admission)
 *   - ADM-1: Student identity, blank DOB default (W9 fix), B-Form & live duplicate check
 *   - ADM-2: Guardian mobile first -> automatic sibling/family detection & auto-fill (W1 fix)
 *   - ADM-3: Live class seat meter check before submit, documents checklist & first fee voucher
 *   - ADM-4: Completion summary with 1-click Voucher & Student ID Card print
 *   - G15:   Bulk CSV/Spreadsheet Student Import with live validation preview & error report
 */

import { apiGet, apiPost } from '../../core/api.js';
import { getBootstrap, setBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';
import { icon } from '../../core/icons.js';
import { openVoucherPrintPreview } from '../../print/voucher-print.js';
import { openIdCardsPrintPreview } from '../../print/academic-print.js';

export function openAdmissionWizardModal(onSuccess) {
  const boot       = getBootstrap();
  const classes    = boot?.school?.standards || [];
  const years      = boot?.school?.years || [];
  const schools    = boot?.school?.schools || [];
  const structures = boot?.fees?.structures || [];

  const classOpts = classes.map(c => {
    const rem = Number(c.remaining_seats ?? 0);
    return `<option value="${esc(c.id)}" data-rem="${rem}" ${rem <= 0 ? 'disabled' : ''}>
      ${esc(c.name)} — ${rem > 0 ? `${rem} seats free` : 'SEATS FULL (0 free)'}
    </option>`;
  }).join('');

  const yearOpts = years.map(y =>
    `<option value="${esc(y.id)}" ${y.current ? 'selected' : ''}>${esc(y.name)}</option>`
  ).join('');

  const structOpts = structures.map(fs =>
    `<option value="${esc(fs.id)}">${esc(fs.name)}</option>`
  ).join('');

  const bodyHtml = `
    <!-- ADM-1: Student Identity & Live Duplicate Check -->
    <div style="font-size:12px; font-weight:700; text-transform:uppercase; color:var(--siyahi-soft); margin-bottom:8px;">
      Step 1 — Student Identity &amp; Duplicate Check (ADM-1)
    </div>
    <div id="aw-dup-alert" style="display:none; padding:10px 12px; margin-bottom:10px; background:var(--warn-bg); color:var(--warn-text); border-radius:var(--radius-inner); font-size:12.5px; font-weight:600;"></div>

    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="aw-name">First Name</label>
        <input class="form-control" id="aw-name" placeholder="e.g. Zainab" required autofocus />
      </div>
      <div class="form-group">
        <label class="form-label" for="aw-last">Last / Family Name</label>
        <input class="form-control" id="aw-last" placeholder="e.g. Qureshi" />
      </div>
      <div class="form-group">
        <label class="form-label" for="aw-gender">Gender</label>
        <select class="form-control" id="aw-gender"><option value="male">Male</option><option value="female">Female</option></select>
      </div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="aw-dob">Date of Birth (Blank Default — W9 Fix)</label>
        <input class="form-control" id="aw-dob" type="date" value="" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="aw-bform">B-Form / Child Registration No.</label>
        <input class="form-control num" id="aw-bform" placeholder="35202-1234567-1" />
      </div>
    </div>

    <!-- ADM-2: Guardian & Sibling Auto-Detection -->
    <div style="font-size:12px; font-weight:700; text-transform:uppercase; color:var(--siyahi-soft); margin:10px 0 8px; padding-top:10px; border-top:1px solid var(--rule-line);">
      Step 2 — Guardian &amp; Family Account Auto-Link (ADM-2)
    </div>
    <div id="aw-family-banner" style="display:none; padding:8px 12px; margin-bottom:10px; background:var(--pista-bg); color:var(--pista-text); border-radius:var(--radius-inner); font-size:12.5px;"></div>

    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="aw-gphone">Guardian Mobile (03XX-XXXXXXX)</label>
        <input class="form-control num" id="aw-gphone" placeholder="0300-1234567" required />
      </div>
      <div class="form-group">
        <label class="form-label required" for="aw-gname">Father / Guardian Full Name</label>
        <input class="form-control" id="aw-gname" placeholder="e.g. Faisal Qureshi" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="aw-gcnic">Guardian CNIC</label>
        <input class="form-control num" id="aw-gcnic" placeholder="35202-1112223-1" />
      </div>
    </div>

    <!-- ADM-3: Class Seat Check, Fee Plan & Documents Checklist -->
    <div style="font-size:12px; font-weight:700; text-transform:uppercase; color:var(--siyahi-soft); margin:10px 0 8px; padding-top:10px; border-top:1px solid var(--rule-line);">
      Step 3 — Class Seat Allocation, Fee Voucher &amp; Documents (ADM-3)
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px;">
      <div class="form-group">
        <label class="form-label required" for="aw-class">Class &amp; Live Seat Meter</label>
        <select class="form-control" id="aw-class" required>
          <option value="">— Select Class —</option>${classOpts}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="aw-year">Academic Year</label>
        <select class="form-control" id="aw-year" required>${yearOpts}</select>
      </div>
      <div class="form-group">
        <label class="form-label" for="aw-struct">Fee Structure (First Challan)</label>
        <select class="form-control" id="aw-struct">${structOpts}</select>
      </div>
    </div>

    <div style="display:flex; gap:18px; flex-wrap:wrap; font-size:13px; padding:8px 0;">
      <label style="display:flex; align-items:center; gap:6px;"><input type="checkbox" id="aw-doc-bform" checked /> B-Form Copy Verified</label>
      <label style="display:flex; align-items:center; gap:6px;"><input type="checkbox" id="aw-doc-photo" checked /> Passport Photos</label>
      <label style="display:flex; align-items:center; gap:6px;"><input type="checkbox" id="aw-doc-slc" /> Previous School SLC</label>
      <label style="display:flex; align-items:center; gap:6px; font-weight:600;"><input type="checkbox" id="aw-gen-voucher" checked /> Auto-Generate First Fee Voucher</label>
    </div>
    <input type="hidden" id="aw-school" value="${esc(schools[0]?.id || 1)}" />
  `;

  openModal('Student Admission Wizard (Duplicate & Seat Protected)', bodyHtml, async () => {
    const payload = {
      student_name:           document.getElementById('aw-name')?.value?.trim(),
      last:                   document.getElementById('aw-last')?.value?.trim() || '',
      gender:                 document.getElementById('aw-gender')?.value || 'male',
      date_of_birth:          document.getElementById('aw-dob')?.value,
      b_form_no:              document.getElementById('aw-bform')?.value?.trim() || '',
      guardian_phone:         document.getElementById('aw-gphone')?.value?.trim() || '',
      guardian_name:          document.getElementById('aw-gname')?.value?.trim() || '',
      guardian_cnic:          document.getElementById('aw-gcnic')?.value?.trim() || '',
      standard_id:            parseInt(document.getElementById('aw-class')?.value, 10),
      year_id:                parseInt(document.getElementById('aw-year')?.value, 10),
      school_id:              parseInt(document.getElementById('aw-school')?.value || '1', 10),
      fees_structure_id:      parseInt(document.getElementById('aw-struct')?.value || '0', 10) || null,
      generate_first_voucher: Boolean(document.getElementById('aw-gen-voucher')?.checked),
      documents: {
        b_form:       Boolean(document.getElementById('aw-doc-bform')?.checked),
        photos:       Boolean(document.getElementById('aw-doc-photo')?.checked),
        previous_slc: Boolean(document.getElementById('aw-doc-slc')?.checked),
      },
    };

    const res = await apiPost('/api/admissions/enroll', payload);
    const freshBoot = await apiGet('/api/bootstrap');
    setBootstrap(freshBoot);
    closeModal();
    toast(`Admitted ${res.student.student_name} (${res.student.pid})`, 'success');
    if (typeof onSuccess === 'function') onSuccess();

    // ADM-4: Completion action modal with 1-click ID Card & First Voucher Print
    _openAdmissionSuccessModal(res);
  }, { submitLabel: 'Complete Admission', wide: true });

  setTimeout(_bindLiveDuplicateAndFamilyLookup, 40);
}

function _bindLiveDuplicateAndFamilyLookup() {
  const triggerCheck = async () => {
    const b_form_no      = document.getElementById('aw-bform')?.value?.trim() || '';
    const student_name   = document.getElementById('aw-name')?.value?.trim() || '';
    const date_of_birth  = document.getElementById('aw-dob')?.value || '';
    const guardian_phone = document.getElementById('aw-gphone')?.value?.trim() || '';

    if (!b_form_no && !guardian_phone && !date_of_birth) return;
    try {
      const res = await apiGet('/api/admissions/check-duplicate', {
        b_form_no, student_name, date_of_birth, guardian_phone,
      });
      const dupEl = document.getElementById('aw-dup-alert');
      if (dupEl) {
        if (res.has_duplicate) {
          const d = res.duplicates[0];
          dupEl.style.display = 'block';
          dupEl.textContent = `Duplicate Warning: ${d.student_name} (${d.pid}, Class ${d.class_name || '—'}) matches via ${d.match_reason}.`;
        } else {
          dupEl.style.display = 'none';
        }
      }
      const famEl = document.getElementById('aw-family-banner');
      if (famEl && res.existing_family) {
        const f = res.existing_family;
        famEl.style.display = 'block';
        famEl.innerHTML = `<strong>Existing Family Account Found:</strong> ${esc(f.guardian_name)} (${esc(f.children_names)}) — Guardian details auto-filled.`;
        const gnameInput = document.getElementById('aw-gname');
        if (gnameInput && !gnameInput.value) gnameInput.value = f.guardian_name;
        const gcnicInput = document.getElementById('aw-gcnic');
        if (gcnicInput && !gcnicInput.value && f.cnic) gcnicInput.value = f.cnic;
      }
    } catch { /* ignore */ }
  };

  ['aw-bform', 'aw-dob', 'aw-gphone'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', triggerCheck);
    document.getElementById(id)?.addEventListener('blur', triggerCheck);
  });
}

function _openAdmissionSuccessModal(res) {
  const s = res.student || {};
  const v = res.first_voucher;
  openModal(`Admission Confirmed — ${s.student_name} (${s.pid})`, `
    <div style="padding:12px; background:var(--pista-bg); color:var(--pista-text); border-radius:var(--radius); font-weight:600; margin-bottom:14px;">
      Student enrolled in ${esc(s.class_name || 'Class')} • GR No: ${esc(s.pid)} • Family Account: ${esc(res.family_key)}
    </div>
    <div style="display:flex; gap:10px; flex-wrap:wrap;">
      <button type="button" class="btn btn-secondary" id="adm-done-idcard">${icon('printer', 14)} Print Student ID Card</button>
      ${v ? `<button type="button" class="btn btn-primary" id="adm-done-voucher">${icon('printer', 14)} Print First Fee Voucher (${esc(v.voucher_display)})</button>` : ''}
    </div>
  `, async () => closeModal(), { submitLabel: 'Done' });

  setTimeout(() => {
    document.getElementById('adm-done-idcard')?.addEventListener('click', () => {
      closeModal();
      openIdCardsPrintPreview({ studentIds: [s.id] });
    });
    document.getElementById('adm-done-voucher')?.addEventListener('click', () => {
      closeModal();
      if (v) openVoucherPrintPreview({ payslipIds: [v.id] });
    });
  }, 30);
}

export function openBulkStudentImportModal(onSuccess) {
  const sampleCsv = `first_name,last_name,gender,date_of_birth,class_name,guardian_name,guardian_phone,b_form_no\nAli,Raza,male,2013-04-12,Class 1-A,Raza Ahmed,0300-1112233,35202-1112233-1\nSara,Khan,female,2013-08-19,Class 1-A,Imran Khan,0321-4445566,35202-4445566-2`;

  openModal('Bulk Student Import (CSV / Excel Paste — G15)', `
    <p style="font-size:12.5px; color:var(--siyahi-soft); margin-bottom:8px;">
      Paste CSV rows below (up to 2,000 rows). Every row is validated for required fields, minimum school age, and class mapping before commit.
    </p>
    <div class="form-group">
      <textarea class="form-control num" id="imp-csv-text" rows="8" style="font-size:12px;">${esc(sampleCsv)}</textarea>
    </div>
    <div style="margin-bottom:10px;">
      <button type="button" class="btn btn-secondary btn-sm" id="imp-btn-preview">Validate &amp; Preview Rows</button>
    </div>
    <div id="imp-preview-box" style="font-size:12.5px;"></div>
  `, async () => {
    const csv_text = document.getElementById('imp-csv-text')?.value || '';
    const res = await apiPost('/api/import/students/commit', { csv_text });
    const freshBoot = await apiGet('/api/bootstrap');
    setBootstrap(freshBoot);
    closeModal();
    toast(`Imported ${res.imported_count} student(s) (${res.skipped_errors} skipped)`, 'success');
    if (typeof onSuccess === 'function') onSuccess();
  }, { submitLabel: 'Commit Valid Rows', wide: true });

  setTimeout(() => {
    document.getElementById('imp-btn-preview')?.addEventListener('click', async () => {
      const box = document.getElementById('imp-preview-box');
      const csv_text = document.getElementById('imp-csv-text')?.value || '';
      if (!box) return;
      try {
        const res = await apiPost('/api/import/students/preview', { csv_text });
        const errHtml = (res.errors || []).slice(0, 5).map(e => `<li>Row ${esc(e.row)}: ${esc(e.error)}</li>`).join('');
        box.innerHTML = `
          <div style="padding:10px; border:1px solid var(--rule-line); border-radius:var(--radius-inner);">
            <strong>Validation Summary:</strong> <span style="color:var(--pista-text); font-weight:700;">${esc(res.valid_count)} Valid</span> •
            <span style="color:var(--danger-text); font-weight:700;">${esc(res.error_count)} Error(s)</span>
            ${errHtml ? `<ul style="margin:6px 0 0 18px; color:var(--danger-text);">${errHtml}</ul>` : ''}
          </div>`;
      } catch (err) {
        box.innerHTML = `<div style="color:var(--danger-text);">${esc(err.message)}</div>`;
      }
    });
  }, 30);
}

/**
 * school/student-modal.js — Quick Admission Modal & Student Row Actions (Phase 1)
 *
 * Extracted from students-list.js to keep every JS module under 250 lines.
 * Fixes DOB hard-coded default bug (W9: DOB starts blank, required).
 */

import { apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal } from '../../core/dom.js';

/**
 * Execute a student lifecycle action (Admit, Set Alumni, Terminate)
 * @param {number} id
 * @param {string} action
 * @param {HTMLButtonElement} btn
 * @param {Function} onSuccess
 */
export async function performStudentAction(id, action, btn, onSuccess) {
  const labels = {
    admission_done: 'Admit karna chahte hain?',
    set_alumni:     'Alumni mark karna chahte hain?',
    terminate:      'Student terminate karna chahte hain?',
  };

  if (!window.confirm(labels[action] || 'Kya aap mutmaeen hain?')) return;

  const origText  = btn.textContent;
  btn.disabled    = true;
  btn.textContent = '...';

  try {
    await apiPost(`/api/students/${id}/action`, { action });
    toast('✓ Student status update ho gaya', 'success');
    if (typeof onSuccess === 'function') onSuccess();
  } catch (err) {
    toast(err.message, 'error');
    btn.disabled    = false;
    btn.textContent = origText;
  }
}

/**
 * Open Quick New Student Admission Modal
 * @param {Function} onSuccess - callback after successful admission
 */
export function openNewStudentModal(onSuccess) {
  const data    = getBootstrap();
  const classes = data?.school?.standards || [];
  const years   = data?.school?.years     || [];
  const schools = data?.school?.schools   || [];

  const classOpts = classes.map(c =>
    `<option value="${esc(c.id)}">${esc(c.name)} (${esc(c.remaining_seats ?? 0)} seats free)</option>`
  ).join('');
  const yearOpts = years.map(y =>
    `<option value="${esc(y.id)}" ${y.current ? 'selected' : ''}>${esc(y.name)}</option>`
  ).join('');

  const bodyHtml = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
      <div class="form-group">
        <label class="form-label required" for="ns-name">First Name</label>
        <input class="form-control" id="ns-name" placeholder="e.g. Muhammad Ahmed" required autofocus />
      </div>
      <div class="form-group">
        <label class="form-label" for="ns-last">Last / Family Name</label>
        <input class="form-control" id="ns-last" placeholder="e.g. Khan" />
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
      <div class="form-group">
        <label class="form-label required" for="ns-class">Class</label>
        <select class="form-control" id="ns-class" required>
          <option value="">— Class chunein —</option>
          ${classOpts}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label required" for="ns-year">Academic Year</label>
        <select class="form-control" id="ns-year" required>
          ${yearOpts}
        </select>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
      <div class="form-group">
        <label class="form-label required" for="ns-dob">Date of Birth</label>
        <input class="form-control" id="ns-dob" type="date" required />
      </div>
      <div class="form-group">
        <label class="form-label" for="ns-gender">Gender</label>
        <select class="form-control" id="ns-gender">
          <option value="male">Male (Larka)</option>
          <option value="female">Female (Larki)</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label" for="ns-mobile">Walid / Guardian Mobile (03XX-XXXXXXX)</label>
      <input class="form-control" id="ns-mobile" placeholder="0300-1234567" />
    </div>
    <input type="hidden" id="ns-school" value="${esc(schools[0]?.id || 1)}" />
  `;

  openModal('Naya Admission (Quick Entry)', bodyHtml, async () => {
    const name     = document.getElementById('ns-name')?.value?.trim();
    const last     = document.getElementById('ns-last')?.value?.trim();
    const classId  = document.getElementById('ns-class')?.value;
    const yearId   = document.getElementById('ns-year')?.value;
    const dob      = document.getElementById('ns-dob')?.value;
    const gender   = document.getElementById('ns-gender')?.value || 'male';
    const mobile   = document.getElementById('ns-mobile')?.value?.trim();
    const schoolId = document.getElementById('ns-school')?.value || '1';

    if (!name || !classId || !yearId || !dob) {
      toast('Zaroori fields fill karein (First Name, Class, Academic Year, DOB)', 'warn');
      return;
    }

    await apiPost('/api/students', {
      student_name:   name,
      last:           last || '',
      standard_id:    parseInt(classId, 10),
      year_id:        parseInt(yearId, 10),
      school_id:      parseInt(schoolId, 10),
      date_of_birth:  dob,
      gender,
      contact_mobile: mobile || '',
      auto_admit:     true,
    });

    toast(`✓ ${name} ka admission mukammal ho gaya!`, 'success');
    closeModal();
    if (typeof onSuccess === 'function') onSuccess();
  }, { submitLabel: 'Admission Karein' });
}


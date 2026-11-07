/**
 * school/student-modal.js — Quick Admission Modal & Student Row Actions (Phase 1/2)
 *
 * Uses styled `confirm()` dialog and clean text/SVG feedback (zero Unicode emojis).
 */

import { apiPost } from '../../core/api.js';
import { getBootstrap } from '../../core/state.js';
import { esc, toast, openModal, closeModal, confirm } from '../../core/dom.js';

export async function performStudentAction(id, action, btn, onSuccess) {
  const prompts = {
    admission_done: ['Confirm Admission', 'Enroll this student as an active student in the selected class?', 'btn-primary'],
    set_alumni:     ['Mark as Alumni', 'Move this student record to Alumni status?', 'btn-secondary'],
    terminate:      ['Terminate Enrollment', 'Terminate this student enrollment record?', 'btn-danger'],
  };
  const [title, desc, cls] = prompts[action] || ['Confirm Action', 'Proceed with this status update?', 'btn-primary'];

  const ok = await confirm(title, desc, { confirmLabel: 'Confirm', confirmClass: cls });
  if (!ok) return;

  const origText  = btn.textContent;
  btn.disabled    = true;
  btn.textContent = '...';

  try {
    await apiPost(`/api/students/${id}/action`, { action });
    toast('Student status updated', 'success');
    if (typeof onSuccess === 'function') onSuccess();
  } catch (err) {
    toast(err.message, 'error');
    btn.disabled    = false;
    btn.textContent = origText;
  }
}

export function openNewStudentModal(onSuccess) {
  const data    = getBootstrap();
  const classes = data?.school?.standards || [];
  const years   = data?.school?.years     || [];
  const schools = data?.school?.schools   || [];

  const classOpts = classes.map(c =>
    `<option value="${esc(c.id)}">${esc(c.name)} (${esc(c.remaining_seats ?? 0)} seats available)</option>`
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
          <option value="">— Select Class —</option>
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
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label class="form-label" for="ns-mobile">Guardian Mobile (03XX-XXXXXXX)</label>
      <input class="form-control" id="ns-mobile" placeholder="0300-1234567" />
    </div>
    <input type="hidden" id="ns-school" value="${esc(schools[0]?.id || 1)}" />
  `;

  openModal('New Student Admission (Quick Entry)', bodyHtml, async () => {
    const name     = document.getElementById('ns-name')?.value?.trim();
    const last     = document.getElementById('ns-last')?.value?.trim();
    const classId  = document.getElementById('ns-class')?.value;
    const yearId   = document.getElementById('ns-year')?.value;
    const dob      = document.getElementById('ns-dob')?.value;
    const gender   = document.getElementById('ns-gender')?.value || 'male';
    const mobile   = document.getElementById('ns-mobile')?.value?.trim();
    const schoolId = document.getElementById('ns-school')?.value || '1';

    if (!name || !classId || !yearId || !dob) {
      throw new Error('Please fill all required fields (First Name, Class, Academic Year, Date of Birth).');
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

    toast(`Admission completed for ${name}`, 'success');
    closeModal();
    if (typeof onSuccess === 'function') onSuccess();
  }, { submitLabel: 'Complete Admission' });
}
